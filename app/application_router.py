"""
APPLICATION ROUTER
Stores uploaded documents in PostgreSQL (BYTEA)
with filename and mimetype.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import random
from .models import User
from app.models_extended import CoApplicant
import cloudinary.uploader
from app.services.cloudinary_service import upload_file

from .database import get_db
from .models import LoanRecord
from .dependencies import get_current_user
from .models_extended import (
    BankSelection,
    KYCDocuments,
    IncomeDocuments,
    CoApplicant,
    ApplicationSubmission,
    ContactMaster,
    LPSContact  
)

from .schemas_extended import (
    BankSelectionRequest,
    BankSelectionResponse,
    ApplicantSummary,
    KYCSubmitResponse,
    IncomeDocsSubmitResponse,
    CoApplicantResponse,
    FinalSubmitRequest,
    FinalSubmitResponse,
    ContactCreate,
    ContactCreateResponse,
     LoanCreateRequest
)
from .schemas_extended import BankSelectionRequest, BankSelectionResponse
# FROM models_extended.py
from app.models_extended import (
    ApplicationProgress,
    ApplicationUpdate,
    ApplicationAdvisor
)




# FROM models.py
from app.models import ApplicationDocument

def generate_contact_group_id(db: Session):
    count = db.query(ContactMaster).count()
    return f"USR-{str(count + 1).zfill(5)}-{str(uuid.uuid4())[:4]}"


def generate_contact_id(service_type: str, db: Session):
    service_type = service_type.lower()

    prefix_map = {
        "home_loan": "HL",
        "personal_loan": "PL",
        "emi": "EMI",
        "balance_transfer": "BT",
        "lap": "LAP"
    }

    prefix = prefix_map.get(service_type, "GEN")

    count = db.query(LPSContact).filter(
        LPSContact.service_type == service_type
    ).count()

    return f"LPS-{prefix}-{str(count + 1).zfill(5)}"

def generate_loan_id(service_type: str):
    prefix_map = {
        "home_loan": "HL",
        "personal_loan": "PL",
        "lap": "LAP"
    }

    prefix = prefix_map.get(service_type.lower(), "GEN")
    random_part = str(uuid.uuid4())[:6].upper()

    return f"LP-{prefix}-{random_part}"


def generate_bank_selection_id(bank_name: str, db: Session):
    prefix = bank_name.upper()

    count = db.query(BankSelection).filter(
        BankSelection.bank_name == bank_name
    ).count()

    return f"{prefix}-{str(count + 1).zfill(4)}"



router = APIRouter(prefix="/applications", tags=["Applications"])

# ============================================================
# ✅ FIXED MODELS
# ============================================================

class LoanDetail(BaseModel):
    emi: float
    outstanding_amount: float
    tenure_left: float


class LoanRequest(BaseModel):
    age: int
    employment_type: str
    net_monthly_income: float   # ✅ FIXED
    loan_type: str
    loan_amount: float
    existing_loans: int         # ✅ FIXED
    cibil_score: int
    tenure: int
    active_loan_details: List[LoanDetail] = []


# ============================================================
# ✅ PREDICT API
# ============================================================
def predict(data: LoanRequest):

    # Simple scoring logic
    score = int((data.cibil_score / 900) * 100)

    if score > 75:
        status = "APPROVED"
    elif score > 50:
        status = "PARTIALLY APPROVED"
    else:
        status = "REJECTED"

    approved_amount = int(data.loan_amount * (score / 100))

    return {
        "score": score,
        "status": status,
        "probability": score,
        "loanId": f"LN{random.randint(1000,9999)}",
        "approvedAmount": approved_amount,
        "message": "Eligibility calculated successfully"
    }


# ============================================================
# FILE READER
# ============================================================

async def read_file(file: UploadFile):
    if file is None:
        return None, None, None

    content = await file.read()

    if content is None:
        return None, None, None

    return content, file.filename, file.content_type


@router.post("/contact/create", response_model=ContactCreateResponse)
def create_contact(data: ContactCreate, db: Session = Depends(get_db)):

    try:
        service_type = data.service_type.lower()

        # Step 1: Check existing user
        master = db.query(ContactMaster).filter(
            ContactMaster.phone == data.phone,
            ContactMaster.email == data.email
        ).first()

        if not master:
            contact_group_id = generate_contact_group_id(db)

            master = ContactMaster(
                contact_group_id=contact_group_id,
                name=data.name,
                phone=data.phone,
                email=data.email,
                created_at=datetime.utcnow()
            )

            db.add(master)
            db.commit()
            db.refresh(master)
        else:
            contact_group_id = master.contact_group_id

        # Step 2: Generate IDs
        

        # Step 2: Generate IDs
        loan_id = generate_loan_id(service_type)
        contact_id = generate_contact_id(service_type, db)

        # Step 3: Create application entry
        contact = LPSContact(
            contact_id=contact_id,
            contact_group_id=contact_group_id,
            service_type=service_type,
            loan_id=loan_id,
            created_at=datetime.utcnow()
        )

        db.add(contact)

        
        db.commit()
        db.refresh(contact)
        

        return {
        "contact_group_id": contact_group_id,
        "contact_id": contact.contact_id,
        "loan_id": loan_id,
        
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    



@router.post("/loan/create")
def create_loan(
    payload: LoanCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models_dashboard import EMISchedule, Notification

    print("🔥 CURRENT USER OBJECT:", current_user)
    print("🔥 CURRENT USER ID:", getattr(current_user, "id", None))

    existing = db.query(LoanRecord).filter(
        LoanRecord.loan_id == payload.loan_id
    ).first()

    if existing:
        # 🔥 update user_id if missing
        if not existing.user_id:
            existing.user_id = current_user.id
            db.commit()
            db.refresh(existing)
            print("🔥 UPDATED USER ID:", existing.user_id)

        # ✅ Always sync EMI and notifications to current user
        db.query(EMISchedule).filter(
            EMISchedule.loan_id == payload.loan_id
        ).update({"user_id": current_user.id})

        db.query(Notification).filter(
            Notification.loan_id == payload.loan_id
        ).update({"user_id": current_user.id})

        db.commit()

        return {
            "message": "Loan already exists (updated user_id)",
            "application_id": existing.id,
            "loan_id": existing.loan_id
        }

    # ✅ CREATE NEW LOAN
    loan = LoanRecord(
        loan_id=payload.loan_id,
        user_id=current_user.id,
        reference_id=f"REF-{str(uuid.uuid4()).replace('-', '')[:10].upper()}",
        age=payload.age,
        employment_type=payload.employment_type,
        income=payload.income,
        loan_type=payload.loan_type,
        loan_amount=payload.loan_amount,
        tenure=payload.tenure,
        cibil=payload.cibil,
        created_at=datetime.utcnow()
    )

    db.add(loan)
    db.commit()
    db.refresh(loan)

    # ✅ Sync EMI and notifications to current user
    db.query(EMISchedule).filter(
        EMISchedule.loan_id == payload.loan_id
    ).update({"user_id": current_user.id})

    db.query(Notification).filter(
        Notification.loan_id == payload.loan_id
    ).update({"user_id": current_user.id})

    db.commit()

    print("🔥 SAVED USER ID IN DB:", loan.user_id)
    print("🔥 SAVED LOAN ID:", loan.loan_id)

    return {
        "message": "Loan created successfully",
        "application_id": loan.id,
        "loan_id": loan.loan_id
    }

# ============================================================
# STEP 1 — BANK SELECTION
# ============================================================

@router.post("/select-bank", response_model=BankSelectionResponse)
def select_bank(payload: BankSelectionRequest, db: Session = Depends(get_db)):

    record = db.query(LoanRecord).filter(
        LoanRecord.loan_id == payload.loan_id
    ).first()

    if not record:
        raise HTTPException(404, "Loan ID not found")
    bank_id = generate_bank_selection_id(payload.bank_name, db)

    selection = BankSelection(
        bank_selection_id=bank_id, 
        loan_id=payload.loan_id,
        bank_name=payload.bank_name,
        interest_rate=payload.interest_rate,
        monthly_emi=payload.monthly_emi,
    )

    db.add(selection)
    db.commit()
    db.refresh(selection)

    summary = ApplicantSummary(
        loan_id=record.loan_id,
        name=record.name,
        mobile_number=record.phone,
        email=record.email,
        employment_type=record.employment_type,
        loan_type=record.loan_type,
        loan_amount=record.loan_amount,
        tenure=record.tenure,
        selected_bank=selection.bank_name,
        monthly_emi=selection.monthly_emi,
        interest_rate=selection.interest_rate,
    )

    return BankSelectionResponse(
        message="Bank selected successfully",
        bank_selection_id=selection.bank_selection_id,
        applicant_summary=summary,
    )


@router.post("/submit-kyc", response_model=KYCSubmitResponse)
async def submit_kyc(
    loan_id: str = Form(...),
    bank_selection_id: str = Form(...),   # ✅ FIXED
    aadhaar_number: str = Form(...),
    pan_number: str = Form(...),
    aadhaar_card: UploadFile = File(...),
    pan_card: UploadFile = File(...),
    passport_photo: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    record = db.query(LoanRecord).filter(
        LoanRecord.loan_id == loan_id
    ).first()

    if not record:
        raise HTTPException(404, "Loan record not found")

    # 🔥 Upload to Cloudinary
    aadhaar_upload = upload_file(aadhaar_card.file, f"thome_docs/{loan_id}/kyc")
    pan_upload = upload_file(pan_card.file, f"thome_docs/{loan_id}/kyc")
    photo_upload = upload_file(passport_photo.file, f"thome_docs/{loan_id}/kyc")

    # 🔥 Store in DB
    kyc = KYCDocuments(
        loan_id=loan_id,
        bank_selection_id=bank_selection_id,
        aadhaar_number=aadhaar_number,
        pan_number=pan_number,

        aadhaar_url=aadhaar_upload["url"],
        aadhaar_public_id=aadhaar_upload["public_id"],

        pan_url=pan_upload["url"],
        pan_public_id=pan_upload["public_id"],

        photo_url=photo_upload["url"],
        photo_public_id=photo_upload["public_id"],
    )

    db.add(kyc)
    db.commit()

    return KYCSubmitResponse(
        message="KYC submitted successfully",
        loan_id=loan_id,
        employment_type=record.employment_type,
        required_documents=[]
    )

@router.post("/submit-income-docs")
async def submit_income_docs(
    loan_id: str = Form(...),
    bank_selection_id: str = Form(...),

    # SALARIED
    payslip_1: Optional[UploadFile] = File(None),
    payslip_2: Optional[UploadFile] = File(None),
    payslip_3: Optional[UploadFile] = File(None),
    payslip_4: Optional[UploadFile] = File(None),
    payslip_5: Optional[UploadFile] = File(None),
    payslip_6: Optional[UploadFile] = File(None),
    bank_statement: Optional[UploadFile] = File(None),
    form_16: Optional[UploadFile] = File(None),

    # SELF EMPLOYED
    itr_year1: Optional[UploadFile] = File(None),
    itr_year2: Optional[UploadFile] = File(None),
    msme_certificate: Optional[UploadFile] = File(None),
    labour_license: Optional[UploadFile] = File(None),
    gst_certificate: Optional[UploadFile] = File(None),
    gstr_statement: Optional[UploadFile] = File(None),

    # PROFESSIONAL
    prof_itr_year1: Optional[UploadFile] = File(None),
    prof_itr_year2: Optional[UploadFile] = File(None),
    degree_certificate: Optional[UploadFile] = File(None),
    registration_cert: Optional[UploadFile] = File(None),
    practice_bank_stmt: Optional[UploadFile] = File(None),
    office_address_proof: Optional[UploadFile] = File(None),
    prof_gst_reg: Optional[UploadFile] = File(None),

    # FREELANCER
    fl_itr_year1: Optional[UploadFile] = File(None),
    fl_itr_year2: Optional[UploadFile] = File(None),
    fl_bank_statement: Optional[UploadFile] = File(None),
    fl_contracts: Optional[UploadFile] = File(None),
    fl_invoices: Optional[UploadFile] = File(None),
    fl_gst_reg: Optional[UploadFile] = File(None),
    fl_portfolio: Optional[UploadFile] = File(None),

    db: Session = Depends(get_db),
):
    # 🔍 get loan
    record = db.query(LoanRecord).filter(
        LoanRecord.loan_id == loan_id
    ).first()

    if not record:
        raise HTTPException(404, "Loan not found")

    emp = record.employment_type.lower()

    # 🔥 VALIDATION BASED ON EMPLOYMENT TYPE

    if emp == "salaried":
        if not payslip_1 or not bank_statement:
            raise HTTPException(400, "Salaried requires payslip & bank statement")

    elif emp == "self-employed":
        if not itr_year1 or not itr_year2:
            raise HTTPException(400, "Self-employed requires ITRs")

    elif emp == "professional":
        if not prof_itr_year1 or not degree_certificate or not registration_cert:
            raise HTTPException(400, "Professional requires ITR + degree + registration")

    elif emp == "freelancer":
        if not fl_itr_year1 or not fl_bank_statement:
            raise HTTPException(400, "Freelancer requires ITR + bank statement")

    # 🔥 create row
    doc = IncomeDocuments(
        loan_id=loan_id,
        bank_selection_id=bank_selection_id,
        employment_type=record.employment_type,
    )

    # 🔥 helper
    def upload(file):
        return upload_file(file.file, f"thome_docs/{loan_id}/income")

    # 🔥 ALL FIELD MAPPING (VERY IMPORTANT)
    file_map = {
        # salaried
        "payslip_1": payslip_1,
        "payslip_2": payslip_2,
        "payslip_3": payslip_3,
        "payslip_4": payslip_4,
        "payslip_5": payslip_5,
        "payslip_6": payslip_6,
        "bank_statement": bank_statement,
        "form_16": form_16,

        # self-employed
        "itr_year1": itr_year1,
        "itr_year2": itr_year2,
        "msme_certificate": msme_certificate,
        "labour_license": labour_license,
        "gst_certificate": gst_certificate,
        "gstr_statement": gstr_statement,

        # professional
        "prof_itr_year1": prof_itr_year1,
        "prof_itr_year2": prof_itr_year2,
        "degree_certificate": degree_certificate,
        "registration_cert": registration_cert,
        "practice_bank_stmt": practice_bank_stmt,
        "office_address_proof": office_address_proof,
        "prof_gst_reg": prof_gst_reg,

        # freelancer
        "fl_itr_year1": fl_itr_year1,
        "fl_itr_year2": fl_itr_year2,
        "fl_bank_statement": fl_bank_statement,
        "fl_contracts": fl_contracts,
        "fl_invoices": fl_invoices,
        "fl_gst_reg": fl_gst_reg,
        "fl_portfolio": fl_portfolio,
    }

    # 🔥 dynamic upload
    for field, file in file_map.items():
        if file:
            res = upload(file)

            setattr(doc, f"{field}_url", res["url"])
            setattr(doc, f"{field}_public_id", res["public_id"])

    db.add(doc)
    db.commit()

    return {
        "message": f"{emp} income documents uploaded successfully",
        "loan_id": loan_id
    }



# ============================================================
# STEP 5 — CO APPLICANT
# ============================================================

@router.post("/add-co-applicant", response_model=CoApplicantResponse)
async def add_co_applicant(
    # 🔹 Linking IDs
    loan_id: str = Form(...),
    bank_selection_id: str = Form(...),

    # 🔹 Basic details
    name: str = Form(...),
    phone: str = Form(...),
    email: Optional[str] = Form(None),
    relation: str = Form(...),

    # 🔹 KYC numbers
    aadhaar_number: Optional[str] = Form(None),
    pan_number: Optional[str] = Form(None),

    # 🔹 File uploads
    aadhaar_file: Optional[UploadFile] = File(None),
    pan_file: Optional[UploadFile] = File(None),
    passport_photo: Optional[UploadFile] = File(None),

    db: Session = Depends(get_db),
):
    try:
        # ─────────────────────────────────────────
        # 1. Initialize variables
        # ─────────────────────────────────────────
        aadhaar_url = None
        aadhaar_public_id = None

        pan_url = None
        pan_public_id = None

        photo_url = None
        photo_public_id = None

        # ─────────────────────────────────────────
        # 2. Upload Aadhaar
        # ─────────────────────────────────────────
        if aadhaar_file:
            file_bytes = await aadhaar_file.read()
            result = upload_file(file_bytes, f"thome_docs/{loan_id}/coapp")

            aadhaar_url = result["url"]
            aadhaar_public_id = result["public_id"]

        # ─────────────────────────────────────────
        # 3. Upload PAN
        # ─────────────────────────────────────────
        if pan_file:
            file_bytes = await pan_file.read()
            result = upload_file(file_bytes, f"thome_docs/{loan_id}/coapp")

            pan_url = result["url"]
            pan_public_id = result["public_id"]

        # ─────────────────────────────────────────
        # 4. Upload Photo
        # ─────────────────────────────────────────
        if passport_photo:
            file_bytes = await passport_photo.read()
            result = upload_file(file_bytes, f"thome_docs/{loan_id}/coapp")

            photo_url = result["url"]
            photo_public_id = result["public_id"]

        # ─────────────────────────────────────────
        # 5. Save to DB
        # ─────────────────────────────────────────
        co_applicant = CoApplicant(
            loan_id=loan_id,
            bank_selection_id=bank_selection_id,

            name=name,
            phone=phone,
            email=email,
            relation=relation,

            aadhaar_number=aadhaar_number,
            pan_number=pan_number,

            aadhaar_url=aadhaar_url,
            aadhaar_public_id=aadhaar_public_id,

            pan_url=pan_url,
            pan_public_id=pan_public_id,

            photo_url=photo_url,
            photo_public_id=photo_public_id,
        )

        db.add(co_applicant)
        db.commit()
        db.refresh(co_applicant)

        # ─────────────────────────────────────────
        # 6. Response
        # ─────────────────────────────────────────
        return CoApplicantResponse(
            message="Co applicant added successfully",
            loan_id=loan_id,
            next_step="submit_application",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/submit", response_model=FinalSubmitResponse)
def submit_application(payload: FinalSubmitRequest, db: Session = Depends(get_db)):

    # 1. Prevent duplicate
    existing = db.query(ApplicationSubmission).filter(
        ApplicationSubmission.loan_id == payload.loan_id
    ).first()

    if existing:
        raise HTTPException(409, "Application already submitted")

    # 2. Get loan
    record = db.query(LoanRecord).filter(
        LoanRecord.loan_id == payload.loan_id
    ).first()

    if not record:
        raise HTTPException(404, "Loan record not found")
    
    # 🔹 GET LOAN RECORD
    record = db.query(LoanRecord).filter(
        LoanRecord.loan_id == payload.loan_id
        ).first()

    if not record:
        raise HTTPException(404, "Loan record not found")

    # 3. Get bank (IMPORTANT FIX)
    bank = db.query(BankSelection).filter_by(
        loan_id=payload.loan_id,
        bank_selection_id=payload.bank_selection_id
    ).first()

    if not bank:
        raise HTTPException(400, "Invalid bank selection")

    # 4. Validate KYC
    kyc = db.query(KYCDocuments).filter_by(
        loan_id=payload.loan_id,
        bank_selection_id=payload.bank_selection_id
    ).first()

    if not kyc:
        raise HTTPException(400, "KYC missing")

    # 5. Validate income
    income = db.query(IncomeDocuments).filter_by(
        loan_id=payload.loan_id,
        bank_selection_id=payload.bank_selection_id
    ).first()

    if not income:
        raise HTTPException(400, "Income docs missing")

    # 6. Validate co-applicant
    if payload.has_co_applicant:
        co = db.query(CoApplicant).filter_by(
            loan_id=payload.loan_id,
            bank_selection_id=payload.bank_selection_id
        ).first()

        if not co:
            raise HTTPException(400, "Co-applicant missing")

    # 7. Create submission
    submission = ApplicationSubmission(
        loan_id=payload.loan_id,
        bank_selection_id=bank.id,  # ✅ FIX
        has_co_applicant=payload.has_co_applicant,
        status="Submitted",
    )

    db.add(submission)

    # 8. Progress
    if not db.query(ApplicationProgress).filter_by(application_id=record.id).first():
        steps = [
            ("Submitted", "done", "Application submitted"),
            ("Verified", "done", "Documents verified"),
            ("Under Review", "active", "Under review"),
            ("Approved", "pending", "Approval pending"),
            ("Disbursed", "pending", "Funds disbursed"),
        ]

        for step, status, desc in steps:
            db.add(ApplicationProgress(
                application_id=record.id,
                step=step,
                status=status,
                description=desc
            ))

    # 9. Updates
    if not db.query(ApplicationUpdate).filter_by(application_id=record.id).first():
        updates = [
            "Application submitted",
            "KYC verified",
            "Under review"
        ]

        for msg in updates:
            db.add(ApplicationUpdate(
                application_id=record.id,
                message=msg
            ))

    # 10. Advisor
    if not db.query(ApplicationAdvisor).filter_by(application_id=record.id).first():
        db.add(ApplicationAdvisor(
            application_id=record.id,
            name="Bhanu Sri",
            role="Wealth Advisor"
        ))

    db.commit()

    return FinalSubmitResponse(
    message="Loan application submitted successfully",
    loan_id=payload.loan_id,
    reference_id=record.reference_id,   # ✅ correct
    status=submission.status,
    submitted_at=submission.submitted_at,
)


# ============================================================
# STEP 7 — APPLICATION STATUS TRACKING
# ============================================================

@router.get("/application/status/{loan_id}")
def track_application(loan_id: str, db: Session = Depends(get_db)):

    record = db.query(LoanRecord).filter(
        LoanRecord.loan_id == loan_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Loan record not found")

    bank_selected = db.query(BankSelection).filter(
        BankSelection.loan_id == loan_id
    ).first()

    kyc_done = db.query(KYCDocuments).filter(
        KYCDocuments.loan_id == loan_id
    ).first()

    income_done = db.query(IncomeDocuments).filter(
        IncomeDocuments.loan_id == loan_id
    ).first()

    coapp_added = db.query(CoApplicant).filter(
        CoApplicant.loan_id == loan_id
    ).first()

    submission = db.query(ApplicationSubmission).filter(
        ApplicationSubmission.loan_id == loan_id
    ).first()

    return {
        "loan_id": loan_id,
        "name": record.name,
        "bank_selected": bank_selected is not None,
        "kyc_uploaded": kyc_done is not None,
        "income_docs_uploaded": income_done is not None,
        "co_applicant_added": coapp_added is not None,
        "application_submitted": submission is not None,
        "final_status": submission.status if submission else "In Progress",
    }


@router.get("/resolve/{loan_id}")
def resolve_loan_id(loan_id: str, db: Session = Depends(get_db)):
    record = db.query(LoanRecord).filter_by(loan_id=loan_id).first()
    if not record:
        raise HTTPException(404, "Not found")
    return {"application_id": record.id}


@router.get("/{application_id}/status")
def get_status(application_id: int, db: Session = Depends(get_db)):
    app = db.query(LoanRecord).filter_by(id=application_id).first()

    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    return {
        "status": app.decision or "Under Review",
        "estimated_completion": "2-3 Days"
    }


@router.get("/{application_id}/progress")
def get_progress(application_id: int, db: Session = Depends(get_db)):
    steps = db.query(ApplicationProgress)\
        .filter(ApplicationDocument.loan_record_id == application_id)\
        .order_by(ApplicationProgress.timestamp)\
        .all()

    return [
        {
            "step": s.step,
            "status": s.status,
            "description": s.description,
            "time": s.timestamp
        }
        for s in steps
    ]


@router.get("/{application_id}/details")
def get_details(application_id: int, db: Session = Depends(get_db)):
    app = db.query(LoanRecord).filter_by(id=application_id).first()

    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    return {
        "loan_id": app.loan_id,
        "loan_type": app.loan_type,
        "loan_amount": app.loan_amount,
        "applicant_name": app.name or (app.user.name if app.user else "User"),
        "submission_date": app.created_at
    }

@router.get("/{application_id}/documents")
def get_documents(application_id: int, db: Session = Depends(get_db)):
    docs = db.query(ApplicationDocument)\
        .filter_by(application_id=application_id)\
        .all()

    return [
        {
            "name": d.name,
            "status": d.status
        }
        for d in docs
    ]

@router.get("/{application_id}/updates")
def get_updates(application_id: int, db: Session = Depends(get_db)):
    updates = db.query(ApplicationUpdate)\
        .filter_by(application_id=application_id)\
        .order_by(ApplicationUpdate.created_at.desc())\
        .all()

    return [
        {
            "message": u.message,
            "time": u.created_at
        }
        for u in updates
    ]
@router.get("/{application_id}/advisor")
def get_advisor(application_id: int, db: Session = Depends(get_db)):
    advisor = db.query(ApplicationAdvisor)\
        .filter_by(application_id=application_id)\
        .first()

    if not advisor:
        return {
            "name": "Not Assigned",
            "role": "",
            "avatar": ""
        }

    return {
        "name": advisor.name,
        "role": advisor.role,
        "avatar": advisor.avatar_url
    }


@router.get("/{application_id}/full")
def get_full(application_id: int, db: Session = Depends(get_db)):

    app = db.query(LoanRecord).filter(LoanRecord.id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    submission = (
        db.query(ApplicationSubmission)
        .filter(ApplicationSubmission.loan_id == app.loan_id)
        .first()
    )

    bank = (
        db.query(BankSelection)
        .filter(BankSelection.loan_id == app.loan_id)
        .first()
    )

    # ── Documents ──────────────────────────────────────────────────────────────
    # application_documents is empty — pull from kyc_documents + income_documents

    all_docs = []

    # 1. KYC Documents
    kyc = (
        db.query(KYCDocuments)
        .filter(KYCDocuments.loan_id == app.loan_id)
        .first()
    )
    if kyc:
        kyc_map = [
            ("Aadhaar Card", kyc.aadhaar_url),
            ("PAN Card",     kyc.pan_url),
            ("Photo",        kyc.photo_url),
        ]
        for name, url in kyc_map:
            if url:  # skip nulls
                all_docs.append({"name": name, "status": "Uploaded", "url": url})

    # 2. Income Documents (employment-type aware)
    income = (
        db.query(IncomeDocuments)
        .filter(IncomeDocuments.loan_id == app.loan_id)
        .first()
    )
    if income:
        income_map = [
            # Salaried
            ("Payslip 1",        income.payslip_1_url),
            ("Payslip 2",        income.payslip_2_url),
            ("Payslip 3",        income.payslip_3_url),
            ("Payslip 4",        income.payslip_4_url),
            ("Payslip 5",        income.payslip_5_url),
            ("Payslip 6",        income.payslip_6_url),
            ("Bank Statement",   income.bank_statement_url),
            ("Form 16",          income.form_16_url),
            # Self Employed
            ("ITR Year 1",       income.itr_year1_url),
            ("ITR Year 2",       income.itr_year2_url),
            ("MSME Certificate", income.msme_certificate_url),
            ("Labour License",   income.labour_license_url),
            ("GST Certificate",  income.gst_certificate_url),
            ("GSTR Statement",   income.gstr_statement_url),
            # Professional
            ("ITR Year 1 (Prof)",        income.prof_itr_year1_url),
            ("ITR Year 2 (Prof)",        income.prof_itr_year2_url),
            ("Degree Certificate",       income.degree_certificate_url),
            ("Registration Certificate", income.registration_cert_url),
            ("Practice Bank Statement",  income.practice_bank_stmt_url),
            ("Office Address Proof",     income.office_address_proof_url),
            ("GST Registration (Prof)",  income.prof_gst_reg_url),
            # Freelancer
            ("ITR Year 1 (FL)",   income.fl_itr_year1_url),
            ("ITR Year 2 (FL)",   income.fl_itr_year2_url),
            ("Bank Statement (FL)", income.fl_bank_statement_url),
            ("Contracts",         income.fl_contracts_url),
            ("Invoices",          income.fl_invoices_url),
            ("GST Registration (FL)", income.fl_gst_reg_url),
            ("Portfolio",         income.fl_portfolio_url),
        ]
        for name, url in income_map:
            if url:  # skip all None/empty optional fields
                all_docs.append({"name": name, "status": "Uploaded", "url": url})

    # ── Progress ───────────────────────────────────────────────────────────────
    progress_rows = (
        db.query(ApplicationProgress)
        .filter(ApplicationProgress.application_id == application_id)
        .order_by(ApplicationProgress.timestamp)
        .all()
    )

    update_rows = (
        db.query(ApplicationUpdate)
        .filter(ApplicationUpdate.application_id == application_id)
        .order_by(ApplicationUpdate.created_at.desc())
        .all()
    )

    advisor_row = (
        db.query(ApplicationAdvisor)
        .filter(ApplicationAdvisor.application_id == application_id)
        .first()
    )

    return {
        "status": {
            "status": submission.status if submission else (app.decision or "Under Review"),
            "estimated_completion": "2-3 Days",
        },
        "progress": [
            {
                "step": s.step,
                "status": s.status,
                "description": s.description,
                "time": s.timestamp,
            }
            for s in progress_rows
        ],
        "details": {
            "loan_id": app.loan_id,
            "loan_type": app.loan_type,
            "loan_amount": app.loan_amount,
            "applicant_name": app.name or (app.user.name if app.user else "User"),
            "submission_date": app.created_at,
        },
        "documents": all_docs,   # ✅ merged from kyc + income tables
        "updates": [
            {"message": u.message, "time": u.created_at}
            for u in update_rows
        ],
        "advisor": (
            {"name": advisor_row.name, "role": advisor_row.role, "avatar": advisor_row.avatar_url}
            if advisor_row
            else {"name": "Not Assigned", "role": "", "avatar": ""}
        ),
    }
from sqlalchemy import text

@router.get("/full-details/{loan_id}")
def get_full_application(loan_id: str, db: Session = Depends(get_db)):

    result = db.execute(
        text("""
            SELECT 
                lr.loan_id,

                cm.name,
                cm.phone,
                cm.email,

                lr.employment_type,
                lr.loan_type,
                lr.loan_amount,
                lr.tenure,

                bs.bank_selection_id,
                bs.bank_name,
                bs.interest_rate,
                bs.monthly_emi,

                sub.status,
                sub.submitted_at

            FROM loan_records lr

            LEFT JOIN lps_contacts lc
                ON lr.loan_id = lc.loan_id

            LEFT JOIN contact_master cm
                ON lc.contact_group_id = cm.contact_group_id

            LEFT JOIN bank_selections bs 
                ON lr.loan_id = bs.loan_id

            LEFT JOIN application_submissions sub 
                ON lr.loan_id = sub.loan_id

            WHERE lr.loan_id = :loan_id
        """),
        {"loan_id": loan_id}
    ).mappings().first()   # ✅ THIS IS THE FIX

    if not result:
        raise HTTPException(status_code=404, detail="Application not found")

    return result   # ✅ no need for dict()