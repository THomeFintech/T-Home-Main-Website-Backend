"""
dashboard_routes.py
FastAPI router for all Dashboard dynamic data.

Mount in main.py:
    from .dashboard_routes import router as dashboard_router
    app.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from .database import get_db
from .dependencies import get_current_user          # ✅ fixed import
from .models import LoanRecord, User
from .models_extended import (
    BankSelection,
    KYCDocuments,
    IncomeDocuments,
    ApplicationSubmission,
)
from .models_dashboard import EMISchedule, Notification, Advisor, UserAdvisor

router = APIRouter()


# ============================================================
# RESPONSE SCHEMAS
# ============================================================

class StatSummaryResponse(BaseModel):
    active_applications: int
    application_summary: str
    total_loan_amount: float
    total_loan_summary: str
    next_emi_amount: Optional[float]
    next_emi_due_date: Optional[str]
    cibil_score: Optional[int]
    cibil_label: str

    class Config:
        from_attributes = True


class LoanDetailResponse(BaseModel):
    loan_id: str
    loan_type: str
    account_number: str
    loan_amount: float
    monthly_emi: Optional[float]
    remaining_balance: Optional[float]
    repayment_percent: Optional[float]
    amount_paid: Optional[float]
    status: Optional[str]

    class Config:
        from_attributes = True


class DocumentStatusResponse(BaseModel):
    label: str
    status: str
    color: str

    class Config:
        from_attributes = True


class ApplicationProgressResponse(BaseModel):
    current_status: str
    steps: List[dict]
    expected_days: Optional[int]

    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    category: str
    color: str
    is_read: bool
    created_at: str

    class Config:
        from_attributes = True


class AdvisorResponse(BaseModel):
    name: str
    designation: str
    phone: Optional[str]
    photo_url: Optional[str]

    class Config:
        from_attributes = True


# ============================================================
# HELPERS
# ============================================================

def get_cibil_label(score: Optional[int]) -> str:
    if score is None:
        return "N/A"
    if score >= 750:
        return "Excellent"
    if score >= 700:
        return "Good"
    if score >= 650:
        return "Fair"
    return "Poor"


def format_loan_account(loan_id: str) -> str:
    digits = "".join(filter(str.isdigit, loan_id)).zfill(12)
    return f"{digits[:4]}-{digits[4:8]}-{digits[8:12]}"


STATUS_STEPS = ["Submitted", "Verified", "Under Review", "Approved", "Disbursed"]


def build_steps(current_status: str) -> List[dict]:
    try:
        active_index = STATUS_STEPS.index(current_status)
    except ValueError:
        active_index = 0
    steps = []
    for i, label in enumerate(STATUS_STEPS):
        if i < active_index:
            status = "done"
        elif i == active_index:
            status = "active"
        else:
            status = "pending"
        steps.append({"label": label, "status": status})
    return steps


def time_ago(dt: datetime) -> str:
    if not dt:
        return ""
    diff = datetime.utcnow() - dt
    seconds = int(diff.total_seconds())
    if seconds < 3600:
        return f"{seconds // 60} minutes ago"
    if seconds < 86400:
        return f"{seconds // 3600} hours ago"
    if seconds < 172800:
        return "Yesterday"
    return f"{seconds // 86400} days ago"


# ============================================================
# GET /dashboard/summary
# ============================================================
@router.get("/summary", response_model=StatSummaryResponse)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 🔥 Fetch submissions linked to user
    submissions = db.query(ApplicationSubmission).join(
        LoanRecord, LoanRecord.loan_id == ApplicationSubmission.loan_id
    ).filter(
        LoanRecord.user_id == current_user.id
    ).all()

    if not submissions:
        return StatSummaryResponse(
            active_applications=0,
            application_summary="No active applications",
            total_loan_amount=0,
            total_loan_summary="No active loans",
            next_emi_amount=None,
            next_emi_due_date=None,
            cibil_score=None,
            cibil_label="N/A",
        )

    # 🔥 Status calculations
    status_map = {s.loan_id: (s.status or "Submitted") for s in submissions}

    in_progress = sum(
        1 for s in status_map.values()
        if s in ["Submitted", "Under Review"]
    )

    under_review = sum(
        1 for s in status_map.values()
        if s == "Under Review"
    )

    active_count = len(submissions)

    # 🔥 SAFE total loan amount
    total_amount = sum(
        (s.loan.loan_amount or 0) for s in submissions if s.loan
    )

    
    # 🔥 FIX: Join through LoanRecord to filter by user
    next_emi = (
    db.query(EMISchedule)
    .join(LoanRecord, LoanRecord.loan_id == EMISchedule.loan_id)
    .filter(
        LoanRecord.user_id == current_user.id,
        EMISchedule.is_paid == False
    )
    .order_by(EMISchedule.due_date.asc())
    .first()
)

    # 🔥 SAFE latest loan
    loans = [s.loan for s in submissions if s.loan]

    latest_loan = max(
        loans,
        key=lambda l: l.created_at or datetime.min
    ) if loans else None

    return StatSummaryResponse(
        active_applications=active_count,
        application_summary=f"{in_progress} In Progress, {under_review} Under Review",
        total_loan_amount=total_amount,
        total_loan_summary=f"Across {active_count} active loan(s)",

        # 🔥 SAFE EMI fields
        next_emi_amount=next_emi.emi_amount if next_emi else None,
        next_emi_due_date=(
            next_emi.due_date.strftime("%d %b %Y")
            if next_emi and next_emi.due_date else None
        ),

        # 🔥 SAFE CIBIL
        cibil_score=latest_loan.cibil if latest_loan else None,
        cibil_label=get_cibil_label(latest_loan.cibil) if latest_loan else "N/A",
    )

# ============================================================
# GET /dashboard/loans
# ============================================================

@router.get("/loans", response_model=List[LoanDetailResponse])
def get_dashboard_loans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    loans = (
        db.query(LoanRecord)
        .filter(LoanRecord.user_id == current_user.id)
        .order_by(LoanRecord.created_at.desc())
        .all()
    )

    result = []
    for loan in loans:
        bank = (
            db.query(BankSelection)
            .filter(BankSelection.loan_id == loan.loan_id)
            .order_by(BankSelection.selected_at.desc())
            .first()
        )
        latest_emi = (
            db.query(EMISchedule)
            .filter(EMISchedule.loan_id == loan.loan_id)
            .order_by(EMISchedule.emi_number.desc())
            .first()
        )
        paid_emis = (
            db.query(EMISchedule)
            .filter(EMISchedule.loan_id == loan.loan_id, EMISchedule.is_paid == True)
            .all()
        )
        amount_paid   = sum(e.principal_component or 0 for e in paid_emis)
        remaining     = latest_emi.remaining_balance if latest_emi else loan.loan_amount
        repayment_pct = round((amount_paid / loan.loan_amount) * 100, 1) if loan.loan_amount else 0

        submission = (
            db.query(ApplicationSubmission)
            .filter(ApplicationSubmission.loan_id == loan.loan_id)
            .order_by(ApplicationSubmission.submitted_at.desc())
            .first()
        )

        # 🔥 ADD THIS BLOCK
        if submission and submission.status not in ["Submitted", "Verified", "Under Review", "Approved", "Disbursed"]:
            continue

        result.append(LoanDetailResponse(
            loan_id=loan.loan_id,
            loan_type=loan.loan_type or "Loan",
            account_number=format_loan_account(loan.loan_id),
            loan_amount=loan.loan_amount or 0,
            monthly_emi=bank.monthly_emi if bank else None,
            remaining_balance=remaining,
            repayment_percent=repayment_pct,
            amount_paid=amount_paid,
            status=submission.status if submission else "Submitted",
        ))

    return result


# ============================================================
# POST /dashboard/generate-emi/{loan_id}
# ============================================================
from dateutil.relativedelta import relativedelta

@router.post("/generate-emi/{loan_id}")
def generate_emi_schedule(
    loan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. Fetch loan (no user_id filter)
    loan = db.query(LoanRecord).filter(
        LoanRecord.loan_id == loan_id,
    ).first()

    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    # 2. Ownership check
    if loan.user_id and str(loan.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    if not loan.loan_amount or not loan.tenure:
        raise HTTPException(status_code=400, detail="Loan amount or tenure missing")

    # 3. Fetch bank selection
    bank = (
        db.query(BankSelection)
        .filter(BankSelection.loan_id == loan_id)
        .order_by(BankSelection.selected_at.desc())
        .first()
    )
    if not bank:
        raise HTTPException(status_code=404, detail="No bank selection found")

    # 4. tenure is in YEARS → convert to months
    tenure_months = loan.tenure * 12
    principal     = loan.loan_amount
    annual_rate   = bank.interest_rate / 100
    monthly_rate  = annual_rate / 12

    # 5. EMI formula
    if monthly_rate == 0:
        emi = round(principal / tenure_months, 2)
    else:
        emi = round(
            principal * monthly_rate * (1 + monthly_rate) ** tenure_months
            / ((1 + monthly_rate) ** tenure_months - 1),
            2,
        )

    # 6. Clear existing schedule
    db.query(EMISchedule).filter(EMISchedule.loan_id == loan_id).delete()

    # 7. Generate rows
    balance  = principal
    due_date = datetime.utcnow().replace(day=1) + relativedelta(months=1)

    for i in range(1, tenure_months + 1):
        interest_comp  = round(balance * monthly_rate, 2)
        principal_comp = round(emi - interest_comp, 2)
        balance        = round(max(balance - principal_comp, 0), 2)

        db.add(EMISchedule(
            loan_id             = loan_id,
            user_id             = current_user.id,
            emi_number          = i,
            emi_amount          = emi,
            due_date            = due_date,
            is_paid             = False,
            principal_component = principal_comp,
            interest_component  = interest_comp,
            remaining_balance   = balance,
        ))
        due_date += relativedelta(months=1)

    db.commit()

    return {
        "message"       : "EMI schedule generated successfully",
        "loan_id"       : loan_id,
        "tenure_months" : tenure_months,
        "monthly_emi"   : emi,
        "total_payable" : round(emi * tenure_months, 2),
    }
# ============================================================
# GET /dashboard/documents
# ============================================================

@router.get("/documents", response_model=List[DocumentStatusResponse])
def get_dashboard_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submissions = db.query(ApplicationSubmission).join(
        LoanRecord, LoanRecord.loan_id == ApplicationSubmission.loan_id
        ).filter(
            LoanRecord.user_id == current_user.id
        ).all()

    loan_ids = [s.loan_id for s in submissions]
    if not loan_ids:
        return [
        DocumentStatusResponse(label="KYC", status="Pending", color="orange"),
        DocumentStatusResponse(label="Income Proof", status="Pending", color="orange"),
        DocumentStatusResponse(label="Property Docs", status="Not Submitted", color="red"),
    ]

    

    kyc_count = db.query(KYCDocuments).filter(
    KYCDocuments.loan_id.in_(loan_ids)
    ).count()

    income_count = db.query(IncomeDocuments).filter(
    IncomeDocuments.loan_id.in_(loan_ids)
    ).count()

    submission_count = db.query(ApplicationSubmission).filter(
        ApplicationSubmission.loan_id.in_(loan_ids)
    ).count()

    return [
    DocumentStatusResponse(
        label="KYC",
        status="Verified" if kyc_count > 0 else "Pending",
        color="green" if kyc_count > 0 else "orange",
    ),
    DocumentStatusResponse(
        label="Income Proof",
        status="Uploaded" if income_count > 0 else "Pending",
        color="blue" if income_count > 0 else "orange",
    ),
    DocumentStatusResponse(
        label="Property Docs",
        status="Uploaded" if submission_count > 0 else "Not Submitted",
        color="blue" if submission_count > 0 else "red",
    ),
]


# ============================================================
# GET /dashboard/progress
# ============================================================

@router.get("/progress", response_model=ApplicationProgressResponse)
def get_application_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    loan = (
        db.query(LoanRecord)
        .filter(LoanRecord.user_id == current_user.id)
        .order_by(LoanRecord.created_at.desc())
        .first()
    )

    if not loan:
        return ApplicationProgressResponse(
            current_status="Submitted",
            steps=build_steps("Submitted"),
            expected_days=None,
        )

    submission = (
        db.query(ApplicationSubmission)
        .filter(ApplicationSubmission.loan_id == loan.loan_id)
        .order_by(ApplicationSubmission.submitted_at.desc())
        .first()
    )

    current_status = submission.status if submission else "Submitted"
    days_map = {"Submitted": 5, "Verified": 3, "Under Review": 2, "Approved": 1, "Disbursed": None}

    return ApplicationProgressResponse(
        current_status=current_status,
        steps=build_steps(current_status),
        expected_days=days_map.get(current_status),
    )


# ============================================================
# GET /dashboard/notifications
# ============================================================

@router.get("/notifications", response_model=List[NotificationResponse])
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(10)
        .all()
    )
    return [
        NotificationResponse(
            id=n.id,
            title=n.title,
            message=n.message,
            category=n.category,
            color=n.color,
            is_read=n.is_read,
            created_at=time_ago(n.created_at),
        )
        for n in notifications
    ]


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    n = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    db.commit()
    return {"message": "Marked as read"}


# ============================================================
# GET /dashboard/advisor
# ============================================================

@router.get("/advisor", response_model=AdvisorResponse)
def get_advisor(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignment = (
        db.query(UserAdvisor)
        .filter(UserAdvisor.user_id == current_user.id)
        .first()
    )
    if not assignment or not assignment.advisor:
        return AdvisorResponse(
        name="Not Assigned",
        designation="",
        phone=None,
        photo_url=None,
    )
    a = assignment.advisor
    return AdvisorResponse(
        name=a.name,
        designation=a.designation,
        phone=a.phone,
        photo_url=a.photo_url,
    )

# ============================================================
# POST /dashboard/sync-loan/{loan_id}
# Links loan, EMI, notifications to current logged-in user
# ============================================================

@router.post("/sync-loan/{loan_id}")
def sync_loan_to_user(
    loan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. Update loan_records
    loan = db.query(LoanRecord).filter(
        LoanRecord.loan_id == loan_id
    ).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    
    loan.user_id = current_user.id

    # 2. Update emi_schedule
    db.query(EMISchedule).filter(
        EMISchedule.loan_id == loan_id
    ).update({"user_id": current_user.id})

    # 3. Update notifications
    db.query(Notification).filter(
        Notification.loan_id == loan_id
    ).update({"user_id": current_user.id})

    db.commit()

    return {
        "message": "Loan synced to your account successfully",
        "loan_id": loan_id,
        "user_id": str(current_user.id),
    }