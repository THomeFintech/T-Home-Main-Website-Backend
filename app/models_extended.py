"""
models_extended.py
SQLAlchemy ORM models for Loan Application Workflow (Steps 1–6)

All documents are stored via Cloudinary (URL + public_id).
No binary/file data is stored directly in PostgreSQL.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from app.database import Base
import uuid


# ============================================================
# STEP 1 – BANK SELECTION
# ============================================================

class BankSelection(Base):

    __tablename__ = "bank_selections"

    id = Column(Integer, primary_key=True, index=True)
    bank_selection_id = Column(String, unique=True, index=True)

    loan_id = Column(
        String,
        ForeignKey("loan_records.loan_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    bank_name = Column(String, nullable=False)
    
    interest_rate = Column(Float, nullable=False)
    monthly_emi = Column(Float, nullable=False)

    selected_at = Column(DateTime, default=datetime.utcnow)
    


   

# ============================================================
# STEP 3 – KYC DOCUMENTS
# ============================================================

class KYCDocuments(Base):

    __tablename__ = "kyc_documents"

    id = Column(Integer, primary_key=True, index=True)

    loan_id = Column(
        String,
        ForeignKey("loan_records.loan_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    bank_selection_id = Column(String, nullable=False, index=True)

    aadhaar_number = Column(String(12), nullable=False)
    pan_number = Column(String(10), nullable=False)

    aadhaar_url = Column(String, nullable=False)
    aadhaar_public_id = Column(String)

    pan_url = Column(String, nullable=False)
    pan_public_id = Column(String)

    photo_url = Column(String, nullable=False)
    photo_public_id = Column(String)

    submitted_at = Column(DateTime, default=datetime.utcnow)

    


# ============================================================
# STEP 4 – INCOME DOCUMENTS
# ============================================================

class IncomeDocuments(Base):

    __tablename__ = "income_documents"

    id = Column(Integer, primary_key=True, index=True)

    loan_id = Column(
        String,
        ForeignKey("loan_records.loan_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    bank_selection_id = Column(String, nullable=False, index=True)

    employment_type = Column(String, nullable=False)

    # -------------------------
    # SALARIED DOCUMENTS
    # -------------------------

    payslip_1_url = Column(String, nullable=True)
    payslip_1_public_id = Column(String, nullable=True)

    payslip_2_url = Column(String, nullable=True)
    payslip_2_public_id = Column(String, nullable=True)

    payslip_3_url = Column(String, nullable=True)
    payslip_3_public_id = Column(String, nullable=True)

    payslip_4_url = Column(String, nullable=True)
    payslip_4_public_id = Column(String, nullable=True)

    payslip_5_url = Column(String, nullable=True)
    payslip_5_public_id = Column(String, nullable=True)

    payslip_6_url = Column(String, nullable=True)
    payslip_6_public_id = Column(String, nullable=True)

    bank_statement_url = Column(String, nullable=True)
    bank_statement_public_id = Column(String, nullable=True)

    form_16_url = Column(String, nullable=True)
    form_16_public_id = Column(String, nullable=True)

    # -------------------------
    # SELF EMPLOYED
    # -------------------------

    itr_year1_url = Column(String, nullable=True)
    itr_year1_public_id = Column(String, nullable=True)

    itr_year2_url = Column(String, nullable=True)
    itr_year2_public_id = Column(String, nullable=True)

    msme_certificate_url = Column(String, nullable=True)
    msme_certificate_public_id = Column(String, nullable=True)

    labour_license_url = Column(String, nullable=True)
    labour_license_public_id = Column(String, nullable=True)

    gst_certificate_url = Column(String, nullable=True)
    gst_certificate_public_id = Column(String, nullable=True)

    gstr_statement_url = Column(String, nullable=True)
    gstr_statement_public_id = Column(String, nullable=True)

    # -------------------------
    # PROFESSIONAL
    # -------------------------

    prof_itr_year1_url = Column(String, nullable=True)
    prof_itr_year1_public_id = Column(String, nullable=True)

    prof_itr_year2_url = Column(String, nullable=True)
    prof_itr_year2_public_id = Column(String, nullable=True)

    degree_certificate_url = Column(String, nullable=True)
    degree_certificate_public_id = Column(String, nullable=True)

    registration_cert_url = Column(String, nullable=True)
    registration_cert_public_id = Column(String, nullable=True)

    practice_bank_stmt_url = Column(String, nullable=True)
    practice_bank_stmt_public_id = Column(String, nullable=True)

    office_address_proof_url = Column(String, nullable=True)
    office_address_proof_public_id = Column(String, nullable=True)

    prof_gst_reg_url = Column(String, nullable=True)
    prof_gst_reg_public_id = Column(String, nullable=True)

    # -------------------------
    # FREELANCER
    # -------------------------

    fl_itr_year1_url = Column(String, nullable=True)
    fl_itr_year1_public_id = Column(String, nullable=True)

    fl_itr_year2_url = Column(String, nullable=True)
    fl_itr_year2_public_id = Column(String, nullable=True)

    fl_bank_statement_url = Column(String, nullable=True)
    fl_bank_statement_public_id = Column(String, nullable=True)

    fl_contracts_url = Column(String, nullable=True)
    fl_contracts_public_id = Column(String, nullable=True)

    fl_invoices_url = Column(String, nullable=True)
    fl_invoices_public_id = Column(String, nullable=True)

    fl_gst_reg_url = Column(String, nullable=True)
    fl_gst_reg_public_id = Column(String, nullable=True)

    fl_portfolio_url = Column(String, nullable=True)
    fl_portfolio_public_id = Column(String, nullable=True)

    submitted_at = Column(DateTime, default=datetime.utcnow)

   


# ============================================================
# STEP 5 – CO APPLICANT
# ============================================================

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base


class CoApplicant(Base):
    __tablename__ = "co_applicants"

    id = Column(Integer, primary_key=True, index=True)

    # 🔹 Business Linking IDs (STRING based)
    loan_id = Column(String, nullable=False, index=True)
    bank_selection_id = Column(String, nullable=False, index=True)

    # 🔹 Basic Details
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=True)
    relation = Column(String, nullable=False)

    # 🔹 KYC Numbers (optional)
    aadhaar_number = Column(String, nullable=True)
    pan_number = Column(String, nullable=True)

    # 🔹 Cloudinary Storage (URLs + public IDs)
    aadhaar_url = Column(String, nullable=True)
    aadhaar_public_id = Column(String, nullable=True)

    pan_url = Column(String, nullable=True)
    pan_public_id = Column(String, nullable=True)

    # 🔹 Optional future-proof field
    photo_url = Column(String, nullable=True)
    photo_public_id = Column(String, nullable=True)

    # 🔹 Metadata
    submitted_at = Column(DateTime, default=datetime.utcnow)

# ============================================================
# STEP 6 – FINAL APPLICATION SUBMISSION
# ============================================================

class ApplicationSubmission(Base):

    __tablename__ = "application_submissions"

    id = Column(Integer, primary_key=True, index=True)

    loan_id = Column(
        String,
        ForeignKey("loan_records.loan_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    bank_selection_id = Column(
        Integer,
        ForeignKey("bank_selections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    has_co_applicant = Column(Boolean, default=False)

    status = Column(String, default="Submitted")

    submitted_at = Column(DateTime, default=datetime.utcnow)
    loan = relationship("LoanRecord", foreign_keys=[loan_id], backref="submissions")
    bank = relationship("BankSelection", foreign_keys=[bank_selection_id])

    


# ============================================================
# CONTACT FORM
# ============================================================

class ContactRequest(Base):

    __tablename__ = "contact_requests"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(100), nullable=False)

    service = Column(String(100), nullable=False)
    message = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# MARKETING EMAIL SUBSCRIPTIONS
# ============================================================

class MarketingDetails(Base):

    __tablename__ = "marketing_details"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String(150), unique=True, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# JOB APPLICATION
# ============================================================

class JobApplication(Base):

    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True)

    full_name = Column(String(100))
    phone = Column(String(20))
    qualification = Column(String(200))
    experience = Column(String(20))
    cover_letter = Column(String(1000))

    resume_url = Column(String)
    resume_public_id = Column(String)
    resume_name = Column(String(200))

    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# APPLICATION PROGRESS
# ============================================================

class ApplicationProgress(Base):

    __tablename__ = "application_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    application_id = Column(Integer, ForeignKey("loan_records.id"), index=True)

    step = Column(String, nullable=False)
    status = Column(String, nullable=False)  # done, active, pending
    description = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)


# ============================================================
# APPLICATION UPDATES
# ============================================================

class ApplicationUpdate(Base):

    __tablename__ = "application_updates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    application_id = Column(Integer, ForeignKey("loan_records.id"), index=True)

    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)



# ============================================================
# APPLICATION ADVISOR
# ============================================================

class ApplicationAdvisor(Base):

    __tablename__ = "application_advisors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    application_id = Column(Integer, ForeignKey("loan_records.id"), index=True)

    name = Column(String)
    role = Column(String)

    avatar_url = Column(String)
    avatar_public_id = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# LPS CONTACT MASTER (USER IDENTITY)
# ============================================================

class ContactMaster(Base):

    __tablename__ = "contact_master"

    id = Column(Integer, primary_key=True, index=True)

    contact_group_id = Column(String, unique=True, nullable=False, index=True)

    name = Column(String)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# LPS CONTACTS (APPLICATION LEVEL)
# ============================================================

class LPSContact(Base):

    __tablename__ = "lps_contacts"

    id = Column(Integer, primary_key=True, index=True)

    contact_id = Column(String, unique=True, nullable=False, index=True)

    contact_group_id = Column(String, nullable=False, index=True)

    service_type = Column(String, nullable=False)

    # 🔥 LINK TO EXISTING SYSTEM
    loan_id = Column(String, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)


