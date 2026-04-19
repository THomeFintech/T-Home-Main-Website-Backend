"""
models_dashboard.py
New tables required for dynamic Dashboard data.

Add this file to your app/ directory and import these models
in your main.py / wherever you call Base.metadata.create_all()
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .database import Base


# ============================================================
# EMI SCHEDULE
# Tracks each monthly EMI record for an active loan.
# Created after ApplicationSubmission → status = "Approved"
# ============================================================

class EMISchedule(Base):

    __tablename__ = "emi_schedule"

    id = Column(Integer, primary_key=True, index=True)

    # Link to loan
    loan_id = Column(
        String,
        ForeignKey("loan_records.loan_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Link to user
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # EMI details
    emi_number       = Column(Integer, nullable=False)          # 1, 2, 3 … N
    emi_amount       = Column(Float, nullable=False)            # monthly EMI ₹
    due_date         = Column(DateTime, nullable=False)         # when it's due
    paid_date        = Column(DateTime, nullable=True)          # when it was paid (null = unpaid)
    is_paid          = Column(Boolean, default=False)

    # Running balance after this EMI
    principal_component  = Column(Float, nullable=True)
    interest_component   = Column(Float, nullable=True)
    remaining_balance    = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    loan   = relationship("LoanRecord",  backref="emi_schedule",  passive_deletes=True)
    user   = relationship("User",        backref="emi_schedule",  passive_deletes=True)


# ============================================================
# NOTIFICATIONS
# Per-user activity feed shown in "Recent Updates" on Dashboard.
# Created by backend whenever a significant event happens
# (application submitted, document verified, EMI reminder, etc.)
# ============================================================

class Notification(Base):

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optional loan link (null for account-level notifications)
    loan_id = Column(
        String,
        ForeignKey("loan_records.loan_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Content
    title    = Column(String(200), nullable=False)   # short heading
    message  = Column(Text, nullable=False)           # full message
    category = Column(String(50), nullable=False)     # "application" | "document" | "emi" | "general"

    # Color dot on frontend: "blue" | "green" | "orange" | "red"
    color    = Column(String(20), default="blue")

    is_read  = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User",       backref="notifications", passive_deletes=True)
    loan = relationship("LoanRecord", backref="notifications", passive_deletes=True)


# ============================================================
# ADVISOR
# One advisor can be assigned to many users.
# ============================================================

class Advisor(Base):

    __tablename__ = "advisors"

    id = Column(Integer, primary_key=True, index=True)

    name         = Column(String(100), nullable=False)
    designation  = Column(String(100), default="Wealth Advisor")
    email        = Column(String(150), unique=True, nullable=False)
    phone        = Column(String(20),  nullable=True)
    photo_url    = Column(String(300), nullable=True)   # URL or path to advisor photo
    is_active    = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Reverse: all users assigned to this advisor
    assigned_users = relationship("UserAdvisor", back_populates="advisor", cascade="all, delete-orphan")


# ============================================================
# USER ↔ ADVISOR ASSIGNMENT
# Many-to-one: many users can be assigned to one advisor.
# Kept as a separate table for flexibility (reassignment history).
# ============================================================

class UserAdvisor(Base):

    __tablename__ = "user_advisors"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,    # one active advisor per user at a time
        index=True,
    )

    advisor_id = Column(
        Integer,
        ForeignKey("advisors.id", ondelete="SET NULL"),
        nullable=True,
    )

    assigned_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user    = relationship("User",    backref="advisor_assignment", passive_deletes=True)
    advisor = relationship("Advisor", back_populates="assigned_users")