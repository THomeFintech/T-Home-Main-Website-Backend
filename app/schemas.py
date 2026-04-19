from pydantic import BaseModel, validator
from typing import List, Optional, Union
from pydantic import BaseModel, EmailStr
from pydantic import Field






from typing import List
from pydantic import BaseModel

class DocumentStatusResponse(BaseModel):
    label: str
    status: str
    color: str


class DocumentStatusWrapper(BaseModel):
    has_documents: bool
    documents: List[DocumentStatusResponse]
# ============================================================
# EXISTING LOANS
# ============================================================

class ExistingLoan(BaseModel):
    monthly_emi: float
    outstanding_amount: float
    tenure_left: float

    @validator("monthly_emi", "outstanding_amount")
    def must_be_non_negative(cls, v):
        if v < 0:
            raise ValueError("must be non-negative")
        return v

    @validator("tenure_left")
    def tenure_left_non_negative(cls, v):
        if v < 0:
            raise ValueError("tenure_left must be 0 or more")
        return v


# ============================================================
# LOAN REQUEST
# ============================================================

class LoanRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    age: int
    employment_type: str
    net_monthly_income: float
    loan_type: str
    loan_amount: float
    tenure: int
    cibil_score: int

    existing_loans: List[ExistingLoan] = Field(default_factory=list)


    @validator("cibil_score")
    def valid_cibil(cls, v):
        if not (0 <= v <= 900):
            raise ValueError("CIBIL score must be between 0 and 900")
        return v

    @validator("net_monthly_income", "loan_amount")
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("must be greater than 0")
        return v

    @validator("age")
    def valid_age(cls, v):
        if not (18 <= v <= 75):
            raise ValueError("Age must be between 18 and 75")
        return v

    @validator("tenure")
    def valid_tenure(cls, v):
        if v <= 0:
            raise ValueError("Tenure must be greater than 0")
        return v


# ============================================================
# CONTACT FORM
# ============================================================

class ContactCreate(BaseModel):
    name: str
    phone: str
    email: str
    service: str
    message: Optional[str] = None  
    
    @validator("name")
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v

    @validator("phone")
    def phone_valid(cls, v):
        if len(v) < 8:
            raise ValueError("Invalid phone number")
        return v

    @validator("email")
    def email_valid(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email")
        return v

    @validator("message")
    def message_not_empty(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Message cannot be empty")
        return v
class AmortizationEntry(BaseModel):
    month:     int
    emi:       float
    principal: float
    interest:  float
    balance:   float


class BankRecommendation(BaseModel):
    bank:                  str
    interest_rate:         float
    emi:                   float
    amortization_schedule: List[AmortizationEntry]

class LoanResponse(BaseModel):
    decision:             str
    approval_probability: float
    approved_amount:      float
    reasons:              List[str]
    guidance:             List[str]
    recommended_banks:    List[BankRecommendation]

# ============================================================
# MARKETING EMAIL
# ============================================================

class MarketingCreate(BaseModel):
    email: str

    @validator("email")
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email")
        return v


# ============================================================
# JOB APPLICATION (WITHOUT FILE)
# ============================================================

class JobApplicationCreate(BaseModel):
    full_name: str
    phone: str
    qualification: Optional[str] = None
    experience: Optional[str] = None
    cover_letter: Optional[str] = None

    @validator("full_name")
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Full name required")
        return v

    @validator("phone")
    def phone_valid(cls, v):
        if len(v) < 8:
            raise ValueError("Invalid phone number")
        return v
    

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str 
    password: str


from typing import Optional
from pydantic import BaseModel, EmailStr, root_validator

class LoginRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: str

    @root_validator(pre=True)
    def check_email_or_phone(cls, values):
        email = values.get("email")
        phone = values.get("phone")

        if not email and not phone:
            raise ValueError("Either email or phone is required")

        return values



class UpdateProfileRequest(BaseModel):
    first_name: str
    last_name: str
    dob: str
    pan: str
    address: str


class UpdateContactRequest(BaseModel):
    email: EmailStr
    phone: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str



from pydantic import BaseModel

class VerifyOTPRequest(BaseModel):
    email: str
    otp: str

class ResendOTPRequest(BaseModel):
    email: str



