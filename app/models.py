"""
models.py
Main Loan Record Table

Stores core loan application details and links to the
workflow tables such as bank selection, KYC, income docs,
co-applicant, and final submission.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

from sqlalchemy import Boolean
import uuid



class LoanRecord(Base):

    __tablename__ = "loan_records"

    # ─────────────────────────────────────
    # PRIMARY KEY
    # ─────────────────────────────────────

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # ─────────────────────────────────────
    # UNIQUE IDENTIFIERS
    # ─────────────────────────────────────

    loan_id = Column(String, unique=True, nullable=False, index=True)

    reference_id = Column(String, unique=True, nullable=False, index=True)

    # ─────────────────────────────────────
    # PERSONAL DETAILS
    # ─────────────────────────────────────

    name = Column(String, nullable=True)

    phone = Column(String, nullable=True)

    email = Column(String, nullable=True)

    # ─────────────────────────────────────
    # LOAN DETAILS
    # ─────────────────────────────────────

    age = Column(Integer, nullable=True)

    employment_type = Column(String, nullable=True)

    income = Column(Float, nullable=True)

    loan_type = Column(String, nullable=True)

    loan_amount = Column(Float, nullable=True)

    tenure = Column(Integer, nullable=True)

    cibil = Column(Integer, nullable=True)

    # ─────────────────────────────────────
    # ML DECISION OUTPUT
    # ─────────────────────────────────────

    decision = Column(String, nullable=True)

    probability = Column(Float, nullable=True)

    # ─────────────────────────────────────
    # TIMESTAMP
    # ─────────────────────────────────────

    created_at = Column(DateTime, default=datetime.utcnow)

    
# ─────────────────────────────────────
# USER AUTHENTICATION TABLE
# ─────────────────────────────────────


from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

class User(Base):

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String, nullable=False)

    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)

    dob = Column(String, nullable=True)
    pan = Column(String, nullable=True)
    address = Column(String, nullable=True)

    password = Column(String, nullable=True)

    google_id = Column(String, nullable=True)
    facebook_id = Column(String, nullable=True)
    auth_provider = Column(String, default="email")

    otp = Column(String, nullable=True)
    otp_expiry = Column(DateTime, nullable=True)   # ✅ NEW
    is_verified = Column(Boolean, default=False)

    role = Column(String, default="customer")
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    loan_records = relationship("LoanRecord", backref="user")

class ApplicationDocument(Base):

    __tablename__ = "application_documents"

    id = Column(Integer, primary_key=True, index=True)

    loan_record_id = Column(Integer, ForeignKey("loan_records.id", ondelete="CASCADE"))

    file_url = Column(String, nullable=False)
    public_id = Column(String, nullable=False)

    document_type = Column(String, nullable=True)  # optional (PAN, Aadhaar, etc.)

    uploaded_at = Column(DateTime, default=datetime.utcnow)

