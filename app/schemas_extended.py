"""
schemas_extended.py  –  Pydantic request / response schemas for the
6-step loan-application workflow.

Merge with your existing schemas.py  OR  import from here.
"""

from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime


# ─────────────────────────────────────────────────────────────
# Shared
# ─────────────────────────────────────────────────────────────
class ApplicantSummary(BaseModel):
    """Returned in Step 2 – display applicant details."""
    loan_id:            str
    name:               Optional[str]
    mobile_number:      Optional[str]
    email:              Optional[str]
    employment_type:    Optional[str]
    loan_type:          Optional[str]
    loan_amount:        float
    tenure:             int
    # from bank selection
    selected_bank:      str
    monthly_emi:        float
    interest_rate:      float


# ─────────────────────────────────────────────────────────────
# STEP 1  –  Bank Selection
# ─────────────────────────────────────────────────────────────
class BankSelectionRequest(BaseModel):
    loan_id:        str
    bank_name:      str
    interest_rate:  float
    monthly_emi:    float


class BankSelectionResponse(BaseModel):
    message:            str
    bank_selection_id:  str
    applicant_summary:  ApplicantSummary


# ─────────────────────────────────────────────────────────────
# STEP 3  –  KYC Submission
# (file bytes are handled as UploadFile in the router;
#  this schema covers the non-file fields)
# ─────────────────────────────────────────────────────────────
class KYCSubmitResponse(BaseModel):
    message:            str
    loan_id:            str
    employment_type:    str       # echoed so frontend knows which docs to ask for next
    required_documents: List[str] # list of human-readable doc names


# ─────────────────────────────────────────────────────────────
# STEP 4  –  Income Documents
# ─────────────────────────────────────────────────────────────
class IncomeDocsSubmitResponse(BaseModel):
    message:    str
    loan_id:    str
    next_step:  str     # "co_applicant_check"


# ─────────────────────────────────────────────────────────────
# STEP 5  –  Co-Applicant
# ─────────────────────────────────────────────────────────────
class CoApplicantRequest(BaseModel):
    loan_id: str
    bank_selection_id: str

    name: str
    phone: str
    email: Optional[str] = None
    relation: str

    aadhaar_number: Optional[str] = None
    pan_number: Optional[str] = None

class CoApplicantResponse(BaseModel):
    message: str
    loan_id: str
    next_step: str  # "submit_application"


# ─────────────────────────────────────────────────────────────
# STEP 6  –  Final Submission
# ─────────────────────────────────────────────────────────────
class FinalSubmitRequest(BaseModel):
    loan_id:            str
    bank_selection_id:  str
    has_co_applicant:   bool = False


class FinalSubmitResponse(BaseModel):
    message:            str
    loan_id:            str
    status:             str
    reference_id: str 
    submitted_at:       datetime

from pydantic import BaseModel, EmailStr


class ContactCreate(BaseModel):
    name: str
    phone: str
    email: EmailStr
    service_type: str

class ContactMasterResponse(BaseModel):
    contact_group_id: str
    name: str
    phone: str
    email: str

    class Config:
        from_attributes = True

class ContactResponse(BaseModel):
    contact_id: str
    contact_group_id: str
    service_type: str
    loan_id: str

    class Config:
        from_attributes = True

class ContactCreateResponse(BaseModel):
    contact_group_id: str
    contact_id: str
    loan_id: str

from pydantic import BaseModel

class LoanCreateRequest(BaseModel):
    loan_id: str
    age: int
    employment_type: str
    income: float
    loan_type: str
    loan_amount: float
    tenure: int
    cibil: int 

from pydantic import BaseModel

class BankSelectionRequest(BaseModel):
    loan_id: str
    bank_name: str
    interest_rate: float
    monthly_emi: float

class BankSelectionResponse(BaseModel):
    message: str
    bank_selection_id: str