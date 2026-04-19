from .schemas_dashboard import (
    StatSummaryResponse,
    LoanDetailResponse,
    DocumentStatusResponse,
    DocumentStatusWrapper,
    ApplicationProgressResponse,
    NotificationResponse,
    AdvisorResponse,
)
from typing import List, Optional


class StatSummaryResponse(BaseModel):
    active_applications: int
    application_summary: str
    total_loan_amount: float
    total_loan_summary: str
    next_emi_amount: Optional[float]
    next_emi_due_date: Optional[str]
    cibil_score: Optional[int]
    cibil_label: str


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


class DocumentStatusResponse(BaseModel):
    label: str
    status: str
    color: str


class DocumentStatusWrapper(BaseModel):
    has_documents: bool
    documents: List[DocumentStatusResponse]


class ApplicationProgressResponse(BaseModel):
    current_status: str
    steps: List[dict]
    expected_days: Optional[int]


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    category: str
    color: str
    is_read: bool
    created_at: str


class AdvisorResponse(BaseModel):
    name: str
    designation: str
    phone: Optional[str]
    photo_url: Optional[str]