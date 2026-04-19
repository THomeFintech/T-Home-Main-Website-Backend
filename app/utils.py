import uuid
from datetime import datetime

from .database import SessionLocal
from .models import LoanRecord


# =====================================================
# EMI CALCULATION
# =====================================================

def calculate_emi(principal, annual_rate, tenure_years):

    r = annual_rate / (12 * 100)
    n = tenure_years * 12

    if r == 0:
        return principal / n

    emi = (principal * r * (1 + r) ** n) / ((1 + r) ** n - 1)

    return emi


# =====================================================
# INTEREST RANGE (USED BY BANK ENGINE)
# =====================================================

INTEREST_RANGE = {

    "Home": [7.0, 9.5],

    "Personal": [10.5, 15.0],

    "LAP": [9.0, 12.0],

    "Mortgage": [8.5, 11.0]

}


# =====================================================
# AMORTIZATION SCHEDULE
# =====================================================

def generate_amortization_schedule(principal, annual_interest_rate, tenure_years):

    r = (annual_interest_rate / 12) / 100
    n = tenure_years * 12

    emi = calculate_emi(principal, annual_interest_rate, tenure_years)

    schedule = []

    balance = principal

    for month in range(1, n + 1):

        interest = balance * r
        principal_component = emi - interest

        balance -= principal_component

        schedule.append({

            "month": month,
            "emi": round(emi, 2),
            "principal": round(principal_component, 2),
            "interest": round(interest, 2),
            "balance": max(0, round(balance, 2))

        })

    return schedule


# =====================================================
# LOAN ID GENERATOR
# =====================================================

def generate_loan_id(loan_type: str):

    prefix_map = {

        "Personal": "PL",
        "Home": "HL",
        "Mortgage": "ML",
        "LAP": "LAP"

    }

    prefix = prefix_map.get(loan_type, "LN")

    unique = uuid.uuid4().hex[:6].upper()

    return f"LP-{prefix}-{unique}"


# =====================================================
# REFERENCE ID GENERATOR
# =====================================================

def generate_reference_id():

    return f"REF-{uuid.uuid4().hex[:10].upper()}"


# =====================================================
# SAVE LOAN RECORD TO POSTGRESQL
# =====================================================

def save_to_postgresql(data: dict):

    db = SessionLocal()

    try:

        # -------------------------------------------------
        # Ensure IDs exist
        # -------------------------------------------------

        loan_id = data.get("loan_id")

        if not loan_id:
            loan_id = generate_loan_id(data.get("loan_type"))

        reference_id = data.get("reference_id")

        if not reference_id:
            reference_id = generate_reference_id()


        # -------------------------------------------------
        # Create Loan Record
        # -------------------------------------------------

        record = LoanRecord(

            loan_id=loan_id,
            reference_id=reference_id,

            name=data.get("name"),
            phone=data.get("phone"),
            email=data.get("email"),

            age=data.get("age"),
            employment_type=data.get("employment_type"),
            income=data.get("income"),

            loan_type=data.get("loan_type"),
            loan_amount=data.get("loan_amount"),
            tenure=data.get("tenure"),

            cibil=data.get("cibil"),

            decision=data.get("decision"),
            probability=data.get("probability")

        )


        db.add(record)

        db.commit()

        db.refresh(record)

        print(f"✅ Loan saved → LoanID: {record.loan_id} | ReferenceID: {record.reference_id}")


    except Exception as e:

        db.rollback()

        print(f"❌ DB Save Error: {e}")


    finally:

        db.close()


import random

def generate_otp():
    return str(random.randint(100000, 999999))