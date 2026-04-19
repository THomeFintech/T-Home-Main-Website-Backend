"""
app/documents_router.py

Mount in main.py:
    from app.documents_router import router as documents_router
    app.include_router(documents_router, prefix="/documents", tags=["documents"])

Endpoints:
    GET  /documents/{application_id}                      — grouped document list
    POST /documents/{application_id}/upload               — upload / replace a document
    GET  /documents/{application_id}/verification-status  — overall progress + next steps
    GET  /documents/{application_id}/{document_id}/download — redirect to Cloudinary URL
"""
from __future__ import annotations

import io
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional
from app.models_extended import KYCDocuments, IncomeDocuments

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LoanRecord
from app.user_document import UserDocument, DocumentStatus, infer_category
from app.services.cloudinary_service import upload_file, delete_file

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024   # 10 MB
ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/svg+xml",
}

CLOUDINARY_FOLDER = "thome_docs"

# ─── Pydantic response schemas ────────────────────────────────────────────────

class DocumentOut(BaseModel):
    id:            int
    document_name: str
    category:      str
    status:        str
    filename:      Optional[str]
    file_size:     Optional[int]      # raw bytes
    size_display:  Optional[str]      # e.g. "1.2 MB"
    file_url:      Optional[str]      # Cloudinary URL for direct access
    uploaded_at:   Optional[datetime]
    notes:         Optional[str]

    class Config:
        from_attributes = True


class CategoryGroup(BaseModel):
    category:  str
    documents: List[DocumentOut]


class DocumentsListResponse(BaseModel):
    application_id: int
    groups:         List[CategoryGroup]
    total:          int


class VerificationStatusResponse(BaseModel):
    application_id:        int
    overall_progress:      int        # 0–100
    verified_count:        int
    pending_count:         int
    action_required_count: int
    total:                 int
    next_steps:            List[str]


class UploadResponse(BaseModel):
    id:            int
    document_name: str
    category:      str
    status:        str
    filename:      str
    file_size:     int
    size_display:  str
    file_url:      str
    uploaded_at:   datetime


# ─── Helpers ─────────────────────────────────────────────────────────────────

CATEGORY_ORDER = [
    "Identity & KYC",
    "Income Proof",
    "Property Documents",
    "Bank Statements",
    "Other",
]


def _get_application_or_404(application_id: int, db: Session):
    """Fetch LoanRecord or raise 404."""
    record = db.query(LoanRecord).filter(LoanRecord.id == application_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found.",
        )
    return record


def _doc_to_out(doc: UserDocument) -> DocumentOut:
    return DocumentOut(
        id            = doc.id,
        document_name = doc.document_name,
        category      = doc.category,
        status        = doc.status.value if hasattr(doc.status, "value") else doc.status,
        filename      = doc.filename,
        file_size     = doc.file_size,
        size_display  = doc.size_display(),
        file_url      = doc.file_url,
        uploaded_at   = doc.uploaded_at,
        notes         = doc.notes,
    )


def _build_next_steps(docs: list[UserDocument]) -> List[str]:
    """Generate actionable next-step messages for the sidebar."""
    steps = []
    action_docs  = [d for d in docs if d.status == DocumentStatus.action_required]
    pending_docs = [d for d in docs if d.status == DocumentStatus.pending_review]

    if action_docs:
        names  = ", ".join(d.document_name for d in action_docs[:2])
        suffix = f" and {len(action_docs) - 2} more" if len(action_docs) > 2 else ""
        steps.append(f"Upload missing document(s): {names}{suffix}.")

    if pending_docs:
        steps.append(
            f"{len(pending_docs)} document(s) are under review — "
            "our team will verify them within 2–3 business days."
        )

    if not steps:
        steps.append("All documents verified. Your application is progressing smoothly!")

    return steps


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get(
    "/{application_id}",
    summary="List all documents grouped by category",
)
def list_documents(application_id: int, db: Session = Depends(get_db)):
    loan = _get_application_or_404(application_id, db)

    groups = []

    # ── 1. KYC Documents (from kyc_documents table) ───────────────────────────
    kyc = db.query(KYCDocuments).filter(KYCDocuments.loan_id == loan.loan_id).first()
    kyc_docs = []
    if kyc:
        for name, url in [
            ("Aadhaar Card", kyc.aadhaar_url),
            ("PAN Card",     kyc.pan_url),
            ("Photo",        kyc.photo_url),
        ]:
            if url:
                kyc_docs.append({
                    "id":            f"kyc-{name.lower().replace(' ', '-')}",
                    "document_name": name,
                    "category":      "KYC Documents",
                    "status":        "Uploaded",
                    "filename":      None,
                    "file_size":     None,
                    "size_display":  None,
                    "file_url":      url,
                    "uploaded_at":   kyc.submitted_at,
                    "notes":         None,
                })
    if kyc_docs:
        groups.append({"category": "KYC Documents", "documents": kyc_docs})

    # ── 2. Income Documents (from income_documents table) ─────────────────────
    income = db.query(IncomeDocuments).filter(IncomeDocuments.loan_id == loan.loan_id).first()
    income_docs = []
    if income:
        income_map = [
            ("Payslip 1",                income.payslip_1_url),
            ("Payslip 2",                income.payslip_2_url),
            ("Payslip 3",                income.payslip_3_url),
            ("Payslip 4",                income.payslip_4_url),
            ("Payslip 5",                income.payslip_5_url),
            ("Payslip 6",                income.payslip_6_url),
            ("Bank Statement",           income.bank_statement_url),
            ("Form 16",                  income.form_16_url),
            ("ITR Year 1",               income.itr_year1_url),
            ("ITR Year 2",               income.itr_year2_url),
            ("MSME Certificate",         income.msme_certificate_url),
            ("Labour License",           income.labour_license_url),
            ("GST Certificate",          income.gst_certificate_url),
            ("GSTR Statement",           income.gstr_statement_url),
            ("ITR Year 1 (Prof)",        income.prof_itr_year1_url),
            ("ITR Year 2 (Prof)",        income.prof_itr_year2_url),
            ("Degree Certificate",       income.degree_certificate_url),
            ("Registration Certificate", income.registration_cert_url),
            ("Practice Bank Statement",  income.practice_bank_stmt_url),
            ("Office Address Proof",     income.office_address_proof_url),
            ("GST Registration (Prof)",  income.prof_gst_reg_url),
            ("ITR Year 1 (FL)",          income.fl_itr_year1_url),
            ("ITR Year 2 (FL)",          income.fl_itr_year2_url),
            ("Bank Statement (FL)",      income.fl_bank_statement_url),
            ("Contracts",                income.fl_contracts_url),
            ("Invoices",                 income.fl_invoices_url),
            ("GST Registration (FL)",    income.fl_gst_reg_url),
            ("Portfolio",                income.fl_portfolio_url),
        ]
        for name, url in income_map:
            if url:
                income_docs.append({
                    "id":            f"income-{name.lower().replace(' ', '-').replace('(', '').replace(')', '')}",
                    "document_name": name,
                    "category":      "Income Documents",
                    "status":        "Uploaded",
                    "filename":      None,
                    "file_size":     None,
                    "size_display":  None,
                    "file_url":      url,
                    "uploaded_at":   income.submitted_at,
                    "notes":         None,
                })
    if income_docs:
        groups.append({"category": "Income Documents", "documents": income_docs})

    # ── 3. User-uploaded docs (from user_documents table) ─────────────────────
    rows: list[UserDocument] = (
        db.query(UserDocument)
        .filter(UserDocument.application_id == application_id)
        .order_by(UserDocument.uploaded_at.asc())
        .all()
    )
    grouped: dict[str, list] = defaultdict(list)
    for doc in rows:
        grouped[doc.category].append({
            "id":            doc.id,
            "document_name": doc.document_name,
            "category":      doc.category,
            "status":        doc.status.value if hasattr(doc.status, "value") else doc.status,
            "filename":      doc.filename,
            "file_size":     doc.file_size,
            "size_display":  doc.size_display(),
            "file_url":      doc.file_url,
            "uploaded_at":   doc.uploaded_at,
            "notes":         doc.notes,
        })
    for cat in CATEGORY_ORDER:
        if cat in grouped:
            groups.append({"category": cat, "documents": grouped[cat]})
    for cat, docs in grouped.items():
        if cat not in CATEGORY_ORDER:
            groups.append({"category": cat, "documents": docs})

    total = len(kyc_docs) + len(income_docs) + len(rows)
    return {"application_id": application_id, "groups": groups, "total": total}


@router.post(
    "/{application_id}/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload or replace a document",
)
async def upload_document(
    application_id: int,
    file:           UploadFile    = File(...),
    document_name:  str           = Form(...),
    category:       Optional[str] = Form(None),
    document_id:    Optional[str] = Form(None),  # str — can be int-like "5" or "kyc-photo"
    db:             Session       = Depends(get_db),
):
    _get_application_or_404(application_id, db)

    # ── Validate MIME ─────────────────────────────────────────────────────────
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File type '{file.content_type}' is not allowed. Accepted: PDF, JPG, PNG, SVG.",
        )

    # ── Read & size-check ─────────────────────────────────────────────────────
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 10 MB limit.",
        )

    # ── Upload to Cloudinary ──────────────────────────────────────────────────
    try:
        result    = upload_file(io.BytesIO(file_bytes), folder=CLOUDINARY_FOLDER)
        file_url  = result["url"]
        public_id = result["public_id"]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cloudinary upload failed: {str(exc)}",
        )

    resolved_category = category or infer_category(document_name)

    # ── Resolve numeric ID (only real user_documents rows have integer IDs) ───
    numeric_id = None
    if document_id:
        try:
            numeric_id = int(document_id)
        except (ValueError, TypeError):
            numeric_id = None  # KYC/Income string IDs like "kyc-photo" → always new row

    # ── Replace existing user_documents row ───────────────────────────────────
    if numeric_id is not None:
        doc = (
            db.query(UserDocument)
            .filter(
                UserDocument.id == numeric_id,
                UserDocument.application_id == application_id,
            )
            .first()
        )
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {numeric_id} not found for this application.",
            )
        if doc.public_id:
            try:
                delete_file(doc.public_id)
            except Exception:
                pass

        doc.file_url      = file_url
        doc.public_id     = public_id
        doc.filename      = file.filename
        doc.mimetype      = file.content_type
        doc.file_size     = len(file_bytes)
        doc.status        = DocumentStatus.pending_review
        doc.document_name = document_name
        doc.category      = resolved_category
        doc.uploaded_at   = datetime.now(timezone.utc)

    # ── New row (no ID, or KYC/Income string ID) ──────────────────────────────
    else:
        doc = UserDocument(
            application_id = application_id,
            document_name  = document_name,
            category       = resolved_category,
            file_url       = file_url,
            public_id      = public_id,
            filename       = file.filename,
            mimetype       = file.content_type,
            file_size      = len(file_bytes),
            status         = DocumentStatus.pending_review,
        )
        db.add(doc)

    db.commit()
    db.refresh(doc)

    return UploadResponse(
        id            = doc.id,
        document_name = doc.document_name,
        category      = doc.category,
        status        = doc.status.value,
        filename      = doc.filename,
        file_size     = doc.file_size,
        size_display  = doc.size_display(),
        file_url      = doc.file_url,
        uploaded_at   = doc.uploaded_at,
    )

@router.get("/{application_id}/verification-status")
def verification_status(application_id: int, db: Session = Depends(get_db)):
    loan = _get_application_or_404(application_id, db)

    kyc    = db.query(KYCDocuments).filter(KYCDocuments.loan_id == loan.loan_id).first()
    income = db.query(IncomeDocuments).filter(IncomeDocuments.loan_id == loan.loan_id).first()

    kyc_uploaded    = 0
    income_uploaded = 0
    total_count     = 4  # aadhaar + pan + photo + 1 income slot

    if kyc:
        if kyc.aadhaar_url: kyc_uploaded += 1
        if kyc.pan_url:     kyc_uploaded += 1
        if kyc.photo_url:   kyc_uploaded += 1

    if income:
        income_urls = [
            income.payslip_1_url, income.bank_statement_url, income.form_16_url,
            income.itr_year1_url, income.itr_year2_url,
            income.prof_itr_year1_url, income.degree_certificate_url,
            income.fl_itr_year1_url,  income.fl_bank_statement_url,
        ]
        if any(income_urls):
            income_uploaded += 1

    # These docs are uploaded but not yet verified by admin — they're PENDING
    pending_count  = kyc_uploaded + income_uploaded
    verified_count = 0   # only admin can mark as verified
    missing_count  = total_count - pending_count
    progress       = round((pending_count / total_count) * 100)

    return {
        "application_id":        application_id,
        "overall_progress":      progress,
        "verified_count":        verified_count,
        "pending_count":         pending_count,
        "action_required_count": max(missing_count, 0),
        "total":                 total_count,
        "next_steps": (
            ["All documents uploaded. Our team will verify them within 2–3 business days."]
            if missing_count <= 0
            else [f"Upload {missing_count} more document(s) to complete your application."]
        ),
    }

@router.get(
    "/{application_id}/{document_id}/download",
    summary="Redirect to Cloudinary URL for a document",
)
def download_document(
    application_id: int,
    document_id:    str,        # ← str not int
    db:             Session = Depends(get_db),
):
    loan = _get_application_or_404(application_id, db)

    # ── Numeric ID → user_documents table ────────────────────────────────────
    try:
        numeric_id = int(document_id)
        doc = (
            db.query(UserDocument)
            .filter(
                UserDocument.id == numeric_id,
                UserDocument.application_id == application_id,
            )
            .first()
        )
        if doc and doc.file_url:
            return RedirectResponse(url=doc.file_url)
    except (ValueError, TypeError):
        pass

    # ── KYC string IDs ────────────────────────────────────────────────────────
    if document_id.startswith("kyc-"):
        kyc = db.query(KYCDocuments).filter(KYCDocuments.loan_id == loan.loan_id).first()
        if kyc:
            url = {
                "kyc-aadhaar-card": kyc.aadhaar_url,
                "kyc-pan-card":     kyc.pan_url,
                "kyc-photo":        kyc.photo_url,
            }.get(document_id)
            if url:
                return RedirectResponse(url=url)

    # ── Income string IDs ─────────────────────────────────────────────────────
    if document_id.startswith("income-"):
        income = db.query(IncomeDocuments).filter(IncomeDocuments.loan_id == loan.loan_id).first()
        if income:
            url = {
                "income-payslip-1":                income.payslip_1_url,
                "income-payslip-2":                income.payslip_2_url,
                "income-payslip-3":                income.payslip_3_url,
                "income-payslip-4":                income.payslip_4_url,
                "income-payslip-5":                income.payslip_5_url,
                "income-payslip-6":                income.payslip_6_url,
                "income-bank-statement":           income.bank_statement_url,
                "income-form-16":                  income.form_16_url,
                "income-itr-year-1":               income.itr_year1_url,
                "income-itr-year-2":               income.itr_year2_url,
                "income-msme-certificate":         income.msme_certificate_url,
                "income-labour-license":           income.labour_license_url,
                "income-gst-certificate":          income.gst_certificate_url,
                "income-gstr-statement":           income.gstr_statement_url,
                "income-itr-year-1-prof":          income.prof_itr_year1_url,
                "income-itr-year-2-prof":          income.prof_itr_year2_url,
                "income-degree-certificate":       income.degree_certificate_url,
                "income-registration-certificate": income.registration_cert_url,
                "income-practice-bank-statement":  income.practice_bank_stmt_url,
                "income-office-address-proof":     income.office_address_proof_url,
                "income-gst-registration-prof":    income.prof_gst_reg_url,
                "income-itr-year-1-fl":            income.fl_itr_year1_url,
                "income-itr-year-2-fl":            income.fl_itr_year2_url,
                "income-bank-statement-fl":        income.fl_bank_statement_url,
                "income-contracts":                income.fl_contracts_url,
                "income-invoices":                 income.fl_invoices_url,
                "income-gst-registration-fl":      income.fl_gst_reg_url,
                "income-portfolio":                income.fl_portfolio_url,
            }.get(document_id)
            if url:
                return RedirectResponse(url=url)

    raise HTTPException(status_code=404, detail="Document not found.")