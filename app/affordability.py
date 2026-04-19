import numpy as np
from .utils import INTEREST_RANGE

def suggest_approved_amount(user_data):
    annual_income = user_data["Annual_income"]
    loan_type = user_data["Loan_type"]
    tenure_years = user_data["Tenure"]
    existing_emi = user_data["Existing_Total_EMI"]
    monthly_income = annual_income / 12

    # Match Colab Caps
    EMI_CAP = {"Personal": 0.50, "Home": 0.65, "LAP": 0.60, "Mortgage": 0.60}
    MULTIPLE_CAP = {"Personal": 5, "Home": 20, "LAP": 15, "Mortgage": 18}

    # Use mean interest rate like Colab
    ir_range = INTEREST_RANGE.get(loan_type, [10, 12])
    avg_interest = (ir_range[0] + ir_range[1]) / 2

    max_foir = EMI_CAP.get(loan_type, 0.50)
    max_total_emi = monthly_income * max_foir
    eligible_new_emi = max_total_emi - existing_emi

    if eligible_new_emi <= 0:
        return 0

    # EMI Inversion
    r = avg_interest / (12 * 100)
    n = tenure_years * 12
    max_loan_by_emi = (eligible_new_emi * ((1 + r)**n - 1)) / (r * (1 + r)**n)

    # Income Multiplier
    max_by_multiplier = annual_income * MULTIPLE_CAP.get(loan_type, 5)

    return round(min(max_loan_by_emi, max_by_multiplier), 2)