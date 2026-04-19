"""
app/user_document.py

SQLAlchemy model for user-uploaded documents.
Files are stored in Cloudinary; only URL + public_id are saved in the DB.
No binary/LargeBinary data is stored in PostgreSQL.
"""
import enum

from sqlalchemy import (
    Column, Integer, String,
    DateTime, ForeignKey, Enum as SAEnum, Text,
)
from sqlalchemy.sql import func

from app.database import Base


class DocumentStatus(str, enum.Enum):
    verified        = "Verified"
    pending_review  = "Pending Review"
    action_required = "Action Required"


class DocumentCategory(str, enum.Enum):
    identity_kyc    = "Identity & KYC"
    income_proof    = "Income Proof"
    property_docs   = "Property Documents"
    bank_statements = "Bank Statements"
    other           = "Other"


CATEGORY_HINTS: dict[str, str] = {
    "aadhaar":        "Identity & KYC",
    "aadhar":         "Identity & KYC",
    "pan card":       "Identity & KYC",
    "pan":            "Identity & KYC",
    "passport":       "Identity & KYC",
    "voter":          "Identity & KYC",
    "driving":        "Identity & KYC",
    "salary":         "Income Proof",
    "form 16":        "Income Proof",
    "itr":            "Income Proof",
    "income tax":     "Income Proof",
    "bank statement": "Bank Statements",
    "bank stmt":      "Bank Statements",
    "property":       "Property Documents",
    "sale deed":      "Property Documents",
    "noc":            "Property Documents",
}


def infer_category(document_name: str) -> str:
    """Infer a category from the document name using keyword hints."""
    lower = document_name.lower()
    for keyword, category in CATEGORY_HINTS.items():
        if keyword in lower:
            return category
    return "Other"


class UserDocument(Base):
    """
    Stores every document uploaded through the Documents page.
    Linked to LoanRecord via application_id (= LoanRecord.id).
    Files live in Cloudinary — only file_url and public_id are stored here.
    """
    __tablename__ = "user_documents"

    id             = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer,
        ForeignKey("loan_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Document metadata
    document_name = Column(String(255), nullable=False)
    category      = Column(String(100), nullable=False, default="Other")
    status        = Column(
        SAEnum(DocumentStatus, name="documentstatus"),
        nullable=False,
        default=DocumentStatus.pending_review,
    )

    # Cloudinary storage (replaces file_data LargeBinary)
    file_url  = Column(String, nullable=True)   # Cloudinary secure HTTPS URL
    public_id = Column(String, nullable=True)   # Cloudinary public_id for deletion/replace

    # File metadata
    filename  = Column(String(255), nullable=True)   # original filename from user
    mimetype  = Column(String(100), nullable=True)
    file_size = Column(Integer,     nullable=True)   # size in bytes

    # Optional reviewer note shown to applicant
    notes = Column(Text, nullable=True)

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    def size_display(self) -> str:
        """Human-readable file size string."""
        if self.file_size is None:
            return "—"
        if self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        return f"{self.file_size / (1024 * 1024):.1f} MB"