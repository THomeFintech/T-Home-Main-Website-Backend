"""
app/loan_application_router.py

Handles document uploads for the loan application portal (Proceed.jsx).
Stores files in Cloudinary, saves URLs + metadata in PostgreSQL.

Endpoint:
    POST /loan-application/{application_id}/submit-documents
    POST /loan-application/{application_id}/upload-kyc
    POST /loan-application/{application_id}/upload-income
    GET  /loan-application/{application_id}/documents

All Cloudinary uploads use access_mode="public" via cloudinary_service.py
"""

import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.cloudinary_service import delete_file, upload_file
from app.user_document import UserDocument

router = APIRouter(prefix="/loan-application", tags=["Loan Application Documents"])

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_FILE_SIZE = 5 * 1024 * 1024   # 5 MB general
MAX_PHOTO_SIZE = 2 * 1024 * 1024  # 2 MB passport photo

ALLOWED_MIME = {"image/jpeg", "image/png", "image/jpg", "application/pdf"}
PHOTO_MIME   = {"image/jpeg", "image/png"}

# Maps frontend field name → (document_name, category, max_size, allowed_mime)
DOCUMENT_CONFIG = {
    # KYC
    "aadhaar":          ("Aadhaar Card",                        "kyc",    MAX_FILE_SIZE, ALLOWED_MIME),
    "pan":              ("PAN Card",                             "kyc",    MAX_FILE_SIZE, ALLOWED_MIME),
    "passportPhoto":    ("Passport Size Photo",                  "kyc",    MAX_PHOTO_SIZE, PHOTO_MIME),
    # Income
    "itr1":             ("ITR – Year 1",                         "income", MAX_FILE_SIZE, ALLOWED_MIME),
    "itr2":             ("ITR – Year 2",                         "income", MAX_FILE_SIZE, ALLOWED_MIME),
    "degree":           ("Degree Certificate",                   "income", MAX_FILE_SIZE, ALLOWED_MIME),
    "professionalReg":  ("Professional Registration Certificate","income", MAX_FILE_SIZE, ALLOWED_MIME),
    "bankStatement":    ("Bank Statement (12 Months)",           "income", MAX_FILE_SIZE, {"application/pdf"}),
    "addressProof":     ("Office / Clinic Address Proof",        "income", MAX_FILE_SIZE, ALLOWED_MIME),
    "gst":              ("GST Registration",                     "income", MAX_FILE_SIZE, ALLOWED_MIME),
}

REQUIRED_DOCUMENTS = {
    "aadhaar", "pan", "passportPhoto",
    "itr1", "itr2", "degree", "professionalReg", "bankStatement", "addressProof",
}
# gst is optional


# ── Pydantic Schemas ──────────────────────────────────────────────────────────
class DocumentResult(BaseModel):
    field_name: str
    document_name: str
    category: str
    file_url: str
    public_id: str
    filename: str
    file_size: int
    status: str

    class Config:
        from_attributes = True


class SubmitDocumentsResponse(BaseModel):
    application_id: int
    message: str
    uploaded: list[DocumentResult]
    skipped: list[str]       # optional fields that were not provided
    failed: list[str]        # fields that errored


class DocumentListResponse(BaseModel):
    application_id: int
    documents: list[dict]


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _validate_and_upload(
    field_name: str,
    file: Optional[UploadFile],
    application_id: int,
    db: Session,
) -> Optional[DocumentResult]:
    """
    Validate file size + mime, upload to Cloudinary, save to DB.
    Returns DocumentResult on success, raises HTTPException on hard failure.
    Returns None if file is None (optional field not provided).
    """
    if file is None or not file.filename:
        return None

    doc_name, category, max_size, allowed_mime = DOCUMENT_CONFIG[field_name]

    # Read bytes (safe size check — never use file.size)
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{doc_name}: file is empty.",
        )

    if file_size > max_size:
        limit_mb = max_size / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{doc_name}: exceeds {limit_mb:.0f} MB limit ({file_size / 1024 / 1024:.1f} MB received).",
        )

    mime = file.content_type or ""
    if mime not in allowed_mime:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"{doc_name}: unsupported file type '{mime}'. Allowed: {', '.join(allowed_mime)}",
        )

    # Delete existing document for this field + application (replace flow)
    existing = (
        db.query(UserDocument)
        .filter(
            UserDocument.application_id == application_id,
            UserDocument.document_name == doc_name,
        )
        .first()
    )
    if existing and existing.public_id:
        resource_type = "raw" if mime == "application/pdf" else "image"
        delete_file(existing.public_id, resource_type=resource_type)
        db.delete(existing)
        db.flush()

    # Upload to Cloudinary
    folder = f"thome_docs/{category}/{application_id}"
    result = upload_file(io.BytesIO(file_bytes), folder=folder)

    # Save to DB
    doc = UserDocument(
        application_id=application_id,
        document_name=doc_name,
        category=category,
        status="pending_review",
        file_url=result["url"],
        public_id=result["public_id"],
        filename=file.filename,
        mimetype=mime,
        file_size=file_size,
    )
    db.add(doc)
    db.flush()   # get id without committing yet

    return DocumentResult(
        field_name=field_name,
        document_name=doc_name,
        category=category,
        file_url=result["url"],
        public_id=result["public_id"],
        filename=file.filename,
        file_size=file_size,
        status="pending_review",
    )


# ── Route 1: Submit ALL documents in one call (matches Proceed.jsx submit) ───
@router.post(
    "/{application_id}/submit-documents",
    response_model=SubmitDocumentsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload all loan application documents at once",
)
async def submit_documents(
    application_id: int,
    # KYC
    aadhaar:         UploadFile = File(...),
    pan:             UploadFile = File(...),
    passportPhoto:   UploadFile = File(...),
    # Income — required
    itr1:            UploadFile = File(...),
    itr2:            UploadFile = File(...),
    degree:          UploadFile = File(...),
    professionalReg: UploadFile = File(...),
    bankStatement:   UploadFile = File(...),
    addressProof:    UploadFile = File(...),
    # Income — optional
    gst:             Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    uploaded = []
    skipped  = []
    failed   = []

    all_files = {
        "aadhaar":         aadhaar,
        "pan":             pan,
        "passportPhoto":   passportPhoto,
        "itr1":            itr1,
        "itr2":            itr2,
        "degree":          degree,
        "professionalReg": professionalReg,
        "bankStatement":   bankStatement,
        "addressProof":    addressProof,
        "gst":             gst,
    }

    try:
        for field_name, file in all_files.items():
            if file is None or not file.filename:
                if field_name in REQUIRED_DOCUMENTS:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"'{field_name}' is required but was not provided.",
                    )
                skipped.append(field_name)
                continue

            result = await _validate_and_upload(field_name, file, application_id, db)
            if result:
                uploaded.append(result)

        db.commit()

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document submission failed: {str(e)}",
        )

    return SubmitDocumentsResponse(
        application_id=application_id,
        message=f"Successfully uploaded {len(uploaded)} document(s).",
        uploaded=uploaded,
        skipped=skipped,
        failed=failed,
    )


# ── Route 2: Upload only KYC documents ───────────────────────────────────────
@router.post(
    "/{application_id}/upload-kyc",
    response_model=SubmitDocumentsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload KYC documents (Aadhaar, PAN, Passport Photo)",
)
async def upload_kyc(
    application_id: int,
    aadhaar:       UploadFile = File(...),
    pan:           UploadFile = File(...),
    passportPhoto: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    uploaded = []

    try:
        for field_name, file in {
            "aadhaar": aadhaar,
            "pan": pan,
            "passportPhoto": passportPhoto,
        }.items():
            result = await _validate_and_upload(field_name, file, application_id, db)
            if result:
                uploaded.append(result)

        db.commit()

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"KYC upload failed: {str(e)}",
        )

    return SubmitDocumentsResponse(
        application_id=application_id,
        message=f"KYC documents uploaded ({len(uploaded)} files).",
        uploaded=uploaded,
        skipped=[],
        failed=[],
    )


# ── Route 3: Upload only income documents ────────────────────────────────────
@router.post(
    "/{application_id}/upload-income",
    response_model=SubmitDocumentsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload income documents",
)
async def upload_income(
    application_id: int,
    itr1:            UploadFile = File(...),
    itr2:            UploadFile = File(...),
    degree:          UploadFile = File(...),
    professionalReg: UploadFile = File(...),
    bankStatement:   UploadFile = File(...),
    addressProof:    UploadFile = File(...),
    gst:             Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    uploaded = []
    skipped  = []

    all_income = {
        "itr1":            itr1,
        "itr2":            itr2,
        "degree":          degree,
        "professionalReg": professionalReg,
        "bankStatement":   bankStatement,
        "addressProof":    addressProof,
        "gst":             gst,
    }

    try:
        for field_name, file in all_income.items():
            if file is None or not file.filename:
                skipped.append(field_name)
                continue
            result = await _validate_and_upload(field_name, file, application_id, db)
            if result:
                uploaded.append(result)

        db.commit()

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Income document upload failed: {str(e)}",
        )

    return SubmitDocumentsResponse(
        application_id=application_id,
        message=f"Income documents uploaded ({len(uploaded)} files).",
        uploaded=uploaded,
        skipped=skipped,
        failed=[],
    )


# ── Route 4: Get all documents for an application ────────────────────────────
@router.get(
    "/{application_id}/documents",
    response_model=DocumentListResponse,
    summary="Get all uploaded documents for a loan application",
)
def get_application_documents(
    application_id: int,
    db: Session = Depends(get_db),
):
    docs = (
        db.query(UserDocument)
        .filter(UserDocument.application_id == application_id)
        .order_by(UserDocument.uploaded_at.desc())
        .all()
    )

    return DocumentListResponse(
        application_id=application_id,
        documents=[
            {
                "id":            doc.id,
                "document_name": doc.document_name,
                "category":      doc.category,
                "status":        doc.status,
                "file_url":      doc.file_url,
                "filename":      doc.filename,
                "file_size":     doc.file_size,
                "size_display":  f"{doc.file_size / 1024:.1f} KB" if doc.file_size else None,
                "uploaded_at":   doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            }
            for doc in docs
        ],
    )