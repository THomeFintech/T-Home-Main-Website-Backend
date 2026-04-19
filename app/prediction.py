import pandas as pd
import numpy as np
from .model_loader import loan_model, le_emp, le_type, explainer, feature_names
from .utils import calculate_emi, generate_loan_id, generate_reference_id, save_to_postgresql, INTEREST_RANGE
from .bank_engine import recommend_banks, get_bank_limits, get_bank_list
from .affordability import suggest_approved_amount


# ─────────────────────────────────────────────────────────────────────────────
# REPAYMENT RATIO ESTIMATOR
# ─────────────────────────────────────────────────────────────────────────────
def estimate_repayment_ratio(cibil: int) -> float:
    if cibil >= 750:   return 0.96
    elif cibil >= 720: return 0.92
    elif cibil >= 700: return 0.88
    elif cibil >= 680: return 0.84
    elif cibil >= 650: return 0.79
    elif cibil >= 620: return 0.74
    else:              return 0.70


# ─────────────────────────────────────────────────────────────────────────────
# INPUT VALIDATION
# ─────────────────────────────────────────────────────────────────────────────
VALID_EMPLOYMENT = {"Salaried", "Self-employed", "Professional", "Freelancer"}
VALID_LOAN_TYPES = {"Personal", "Home", "LAP", "Mortgage"}


def validate_inputs(request):
    errors = []
    if request.employment_type not in VALID_EMPLOYMENT:
        errors.append(
            f"Invalid employment_type '{request.employment_type}'. "
            f"Must be one of: {sorted(VALID_EMPLOYMENT)}"
        )
    if request.loan_type not in VALID_LOAN_TYPES:
        errors.append(
            f"Invalid loan_type '{request.loan_type}'. "
            f"Must be one of: {sorted(VALID_LOAN_TYPES)}"
        )
    return errors


def validate_interest_rate(loan_type: str, interest_rate: float):
    rate_range = INTEREST_RANGE.get(loan_type)
    if rate_range is None:
        return True, None, None
    min_r, max_r = rate_range
    return (min_r <= interest_rate <= max_r), min_r, max_r


# ─────────────────────────────────────────────────────────────────────────────
# HARD RULES
# ─────────────────────────────────────────────────────────────────────────────
def bank_hard_rejection(user):
    reasons = []

    if user["age"] < 18 or user["age"] > 75:
        return ["Applicant age must be between 18 and 75 years"]

    # ── CIBIL 0 → no credit history ──────────────────────────────────────────
    if user["cibil_score"] == 0:
        return ["no_credit_history"]

    # ── CIBIL 1–100 → critically low, hard reject ────────────────────────────
    if 1 <= user["cibil_score"] <= 100:
        return ["cibil_critically_low"]

    l_type = user["loan_type"]
    income = user["annual_income"]
    cibil  = user["cibil_score"]
    tenure = user["tenure"]

    MAX_TENURE = {
        "Home": 30, "Personal": 7, "LAP": 30, "Mortgage": 20
    }
    max_allowed = MAX_TENURE.get(l_type, 30)
    if tenure > max_allowed:
        return [f"tenure_exceeded:{max_allowed}"]

    CIBIL_MINIMUMS = {
        "Home":     101,
        "Personal": 101,
        "LAP":      101,
        "Mortgage": 101,
    }
    cibil_min    = CIBIL_MINIMUMS.get(l_type, 101)
    cibil_failed = cibil < cibil_min

    INCOME_MINIMUMS = {
        "Home": 300_000, "Personal": 180_000, "LAP": 250_000, "Mortgage": 0
    }
    income_min    = INCOME_MINIMUMS.get(l_type, 0)
    income_failed = income < income_min

    age_tenure_failed = (l_type == "Home" and user["age"] + tenure > 70)

    # FOIR CALCULATION
    ir_range     = INTEREST_RANGE.get(l_type, [9.0, 10.0])
    avg_interest = (ir_range[0] + ir_range[1]) / 2
    proposed_emi = calculate_emi(user["loan_amount"], avg_interest, tenure)
    total_emi    = user.get("existing_emi", 0) + proposed_emi
    foir         = total_emi / (income / 12)

    FOIR_LIMITS = {
        "Salaried":      0.60,
        "Self-employed": 0.60,
        "Professional":  0.65,
        "Freelancer":    0.45,
    }
    foir_limit  = FOIR_LIMITS.get(user.get("employment_type", "Salaried"), 0.60)
    foir_failed = foir > foir_limit

    # Priority order
    if cibil_failed and foir_failed:
        return [
            f"cibil_and_foir_exceeded:"
            f"{cibil}:{cibil_min}:"
            f"{round(foir * 100, 1)}:{round(foir_limit * 100)}"
        ]
    if cibil_failed:
        reason_text = {
            "Home":     "CIBIL score too low for home loan",
            "Personal": "Low CIBIL score for unsecured loan",
            "LAP":      "CIBIL score below LAP requirement",
            "Mortgage": "CIBIL score too low for mortgage loan",
        }.get(l_type, "CIBIL score below minimum requirement")
        return [reason_text]
    if foir_failed:
        return [f"foir_exceeded:{round(foir * 100, 1)}:{round(foir_limit * 100)}"]
    if income_failed:
        reasons.append({
            "Home":     "Home loan requires stable higher income",
            "Personal": "Personal loan requires minimum income",
            "LAP":      "Insufficient income for LAP",
        }.get(l_type, "Income below minimum requirement"))
    if age_tenure_failed:
        reasons.append("Loan tenure exceeds retirement age")

    return reasons


# ─────────────────────────────────────────────────────────────────────────────
# REJECTION GUIDANCE
# ─────────────────────────────────────────────────────────────────────────────
def generate_rejection_guidance(user):
    guidance    = []
    loan_type   = user["loan_type"]
    cibil       = user["cibil_score"]
    age         = user["age"]
    tenure      = user["tenure"]
    loan_amount = user["loan_amount"]

    if age < 18 or age > 75:
        return []

    CIBIL_MINIMUMS = {
        "Home": 101, "Personal": 101, "LAP": 101, "Mortgage": 101,
    }
    required_cibil = CIBIL_MINIMUMS.get(loan_type, 101)

    if cibil < required_cibil:
        gap = required_cibil - cibil
        guidance.append(
            f"Improve your CIBIL score by at least {gap} points "
            f"(current: {cibil}, required: {required_cibil}+)."
        )
        guidance.append("Pay all existing EMIs on time for the next 6–12 months.")
        guidance.append("Reduce your credit card utilization below 30%.")
        guidance.append("Avoid applying for new loans or credit cards in the near term.")

    reduced_amount = None
    if 101 <= cibil < 200:
        reduced_amount = round(loan_amount * 0.25, 2)
    elif 200 <= cibil < 400:
        reduced_amount = round(loan_amount * 0.35, 2)
    elif 400 <= cibil < 600:
        reduced_amount = round(loan_amount * 0.50, 2)
    elif 600 <= cibil < 650:
        reduced_amount = round(loan_amount * 0.60, 2)
    elif 650 <= cibil < 680:
        reduced_amount = round(loan_amount * 0.75, 2)
    elif 680 <= cibil < 700:
        reduced_amount = round(loan_amount * 0.85, 2)

    if reduced_amount:
        guidance.append(
            f"Alternatively, you may be eligible for a reduced loan amount of "
            f"₹{reduced_amount:,.0f} based on your current credit profile."
        )

    if (age + tenure) > 70:
        MAX_TENURE  = {"Home": 30, "Personal": 7, "LAP": 30, "Mortgage": 20}
        max_allowed = MAX_TENURE.get(loan_type, 30)
        safe_tenure = min(70 - age, max_allowed)
        guidance.append(
            f"Reduce your loan tenure to {safe_tenure} years "
            "to stay within the retirement age limit of 70."
        )

    return guidance


# ─────────────────────────────────────────────────────────────────────────────
# SHAP REASON CODES
# ─────────────────────────────────────────────────────────────────────────────
REASON_MAP = {
    "FOIR_Percentage":   "FOIR exceeds usable income limit",
    "CIBIL_Score":       "Credit score below threshold",
    "Total_Outstanding": "High total debt exposure",
    "Repayment_Ratio":   "History of delayed payments",
    "Age":               "Loan maturity exceeds retirement age",
    "Existing_EMI":      "Existing monthly obligations too high",
    "Proposed_Amount":   "Requested loan amount too high for income",
    "Net_Monthly_Income": "Monthly income insufficient for loan size",
    "Active_Loans_Count": "Too many active loans reducing eligibility",
    "Proposed_Tenure":   "Loan tenure too short to keep EMI affordable",
}


def get_shap_reasons(input_df: pd.DataFrame) -> list:
    try:
        underlying_xgb = loan_model.calibrated_classifiers_[0].estimator
        shap_vals      = explainer.shap_values(input_df)
        if shap_vals.ndim == 2:
            vals = shap_vals[0]
        else:
            vals = shap_vals
        sorted_indices = np.argsort(vals)
        reasons = []
        for idx in sorted_indices:
            feat = input_df.columns[idx]
            if feat in REASON_MAP:
                reasons.append(REASON_MAP[feat])
            if len(reasons) == 2:
                break
        return reasons if reasons else ["General credit risk factors"]
    except Exception:
        return ["General credit risk factors"]


# ─────────────────────────────────────────────────────────────────────────────
# PROBABILITY DISPLAY SCALING
# ─────────────────────────────────────────────────────────────────────────────
def scale_probability(prob: float) -> float:
    if prob > 0.70:
        display = 71.0 + (prob - 0.70) / 0.30 * 24.0
    elif prob >= 0.40:
        display = prob * 100.0
    else:
        display = 5.0 + (prob / 0.40) * 34.0
    return round(display, 2)


def generate_amortization_schedule(principal, annual_rate, tenure_years):
    months       = tenure_years * 12
    monthly_rate = annual_rate / 100 / 12
    emi          = calculate_emi(principal, annual_rate, tenure_years)
    balance      = principal
    schedule     = []
    for m in range(1, months + 1):
        interest            = balance * monthly_rate
        principal_component = emi - interest
        balance            -= principal_component
        schedule.append({
            "month":     m,
            "emi":       round(emi, 2),
            "principal": round(principal_component, 2),
            "interest":  round(interest, 2),
            "balance":   max(0, round(balance, 2)),
        })
    return schedule


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PREDICTION FUNCTION
# ─────────────────────────────────────────────────────────────────────────────
def predict_loan(request):

    # ── INPUT VALIDATION ──────────────────────────────────────────────────────
    validation_errors = validate_inputs(request)
    if validation_errors:
        return {
            "decision":             "Error",
            "approval_probability": 0.0,
            "approved_amount":      0,
            "reasons":              validation_errors,
            "guidance":             [],
            "recommended_banks":    [],
        }

    # ── INTEREST RATE VALIDATION ──────────────────────────────────────────────
    requested_rate = getattr(request, "interest_rate", None)
    if requested_rate is not None:
        rate_valid, min_r, max_r = validate_interest_rate(request.loan_type, requested_rate)
        if not rate_valid:
            return {
                "decision":             "Rejected",
                "approval_probability": 0.0,
                "approved_amount":      0,
                "reasons": [
                    f"Interest rate {requested_rate}% is outside the market range for "
                    f"{request.loan_type} loans ({min_r}% – {max_r}%)."
                ],
                "guidance": [
                    f"Please choose an interest rate between {min_r}% and {max_r}% "
                    f"for a {request.loan_type} loan.",
                    "Banks set their own rates within this range based on your credit profile.",
                    "A lower CIBIL score typically results in a higher offered rate within this band.",
                ],
                "recommended_banks": [],
            }

    # ── BANK AMOUNT PRE-CHECK ─────────────────────────────────────────────────
    bank_limits = get_bank_limits(request.loan_type)
    global_max  = bank_limits["global_max"]
    global_min  = bank_limits["global_min"]

    if global_max > 0 and request.loan_amount > global_max:
        alternates = bank_limits["alternates"]
        alt_text   = (
            f" You may also consider loan types such as "
            f"{' or '.join(alternates)} which may accommodate larger amounts."
            if alternates else ""
        )
        loan_id      = generate_loan_id(request.loan_type)
        reference_id = generate_reference_id()
        save_to_postgresql({
            "loan_id": loan_id, "reference_id": reference_id,
            "name": getattr(request, "name", ""), "phone": getattr(request, "phone", ""),
            "email": getattr(request, "email", ""), "age": request.age,
            "employment_type": request.employment_type, "income": request.net_monthly_income,
            "loan_type": request.loan_type, "loan_amount": float(request.loan_amount),
            "tenure": request.tenure, "cibil": request.cibil_score,
            "decision": "Rejected (Exceeds Bank Limit)", "probability": 0.0,
        })
        return {
            "decision":             "Rejected",
            "approval_probability": 0.0,
            "approved_amount":      0,
            "reasons": [
                f"Requested loan amount ₹{request.loan_amount:,.0f} exceeds the maximum "
                f"₹{global_max:,.0f} offered by any bank for a {request.loan_type} loan."
            ],
            "guidance": [
                f"Your credit profile is noted (CIBIL {request.cibil_score}), "
                f"but no bank offers a {request.loan_type} loan above ₹{global_max:,.0f}.",
                f"Consider reducing your loan amount to ₹{global_max:,.0f} or below "
                "to match available bank products.",
                "You may split your funding need across multiple loan products or use "
                "personal savings to cover the gap above the bank limit." + alt_text,
                "Alternatively, a co-applicant (e.g., spouse or family member) can "
                "increase your combined eligibility for a higher sanctioned amount.",
            ],
            "recommended_banks": [],
        }

    if global_min > 0 and request.loan_amount < global_min:
        loan_id      = generate_loan_id(request.loan_type)
        reference_id = generate_reference_id()
        save_to_postgresql({
            "loan_id": loan_id, "reference_id": reference_id,
            "name": getattr(request, "name", ""), "phone": getattr(request, "phone", ""),
            "email": getattr(request, "email", ""), "age": request.age,
            "employment_type": request.employment_type, "income": request.net_monthly_income,
            "loan_type": request.loan_type, "loan_amount": float(request.loan_amount),
            "tenure": request.tenure, "cibil": request.cibil_score,
            "decision": "Rejected (Below Bank Minimum)", "probability": 0.0,
        })
        return {
            "decision":             "Rejected",
            "approval_probability": 0.0,
            "approved_amount":      0,
            "reasons": [
                f"Requested loan amount ₹{request.loan_amount:,.0f} is below the minimum "
                f"₹{global_min:,.0f} offered by any bank for a {request.loan_type} loan."
            ],
            "guidance": [
                f"The minimum loan amount for a {request.loan_type} loan is ₹{global_min:,.0f}.",
                f"Consider requesting at least ₹{global_min:,.0f} to qualify for bank products.",
                "For smaller loan needs, a Personal loan or credit card may be more appropriate.",
            ],
            "recommended_banks": [],
        }

    # ── DERIVED FIELDS ────────────────────────────────────────────────────────
    existing_total_emi = sum(loan.monthly_emi for loan in request.existing_loans)
    total_outstanding  = sum(loan.outstanding_amount for loan in request.existing_loans)
    annual_income      = request.net_monthly_income * 12
    ir_range           = INTEREST_RANGE.get(request.loan_type, [9.0, 10.0])
    avg_interest       = (ir_range[0] + ir_range[1]) / 2

    # ── FIX: tenure_left is now received in MONTHS directly — no * 12 needed ──
    tenure_lefts           = [l.tenure_left for l in request.existing_loans if l.tenure_left > 0]
    avg_tenure_left_months = int(np.mean(tenure_lefts)) if tenure_lefts else 0

    # ── HARD RULE CHECK ───────────────────────────────────────────────────────
    hard_reasons = bank_hard_rejection({
        "age":             request.age,
        "loan_type":       request.loan_type,
        "tenure":          request.tenure,
        "annual_income":   annual_income,
        "cibil_score":     request.cibil_score,
        "loan_amount":     request.loan_amount,
        "existing_emi":    existing_total_emi,
        "employment_type": request.employment_type,
    })

    # ── NO CREDIT HISTORY ─────────────────────────────────────────────────────
    if hard_reasons == ["no_credit_history"]:
        loan_id      = generate_loan_id(request.loan_type)
        reference_id = generate_reference_id()
        save_to_postgresql({
            "loan_id": loan_id, "reference_id": reference_id,
            "name": getattr(request, "name", ""), "phone": getattr(request, "phone", ""),
            "email": getattr(request, "email", ""), "age": request.age,
            "employment_type": request.employment_type, "income": request.net_monthly_income,
            "loan_type": request.loan_type, "loan_amount": float(request.loan_amount),
            "tenure": request.tenure, "cibil": request.cibil_score,
            "decision": "Rejected (No Credit History)", "probability": 0.0,
        })
        return {
            "decision":             "Rejected",
            "approval_probability": 0.0,
            "approved_amount":      0,
            "reasons": ["No credit history found (CIBIL score: 0)"],
            "guidance": [
                "You currently have no credit history — you are new to credit.",
                "Start with a secured credit card against a fixed deposit (FD) of ₹10,000–₹25,000.",
                "Use the card lightly and pay the full bill every month for 6–12 months.",
                "This will establish a CIBIL score and make you eligible for small personal loans.",
                "Once your CIBIL crosses 650, you can re-apply for a higher loan amount.",
            ],
            "recommended_banks": [],
        }

    # ── CIBIL 1–100: CRITICALLY LOW ───────────────────────────────────────────
    if hard_reasons == ["cibil_critically_low"]:
        loan_id      = generate_loan_id(request.loan_type)
        reference_id = generate_reference_id()
        save_to_postgresql({
            "loan_id": loan_id, "reference_id": reference_id,
            "name": getattr(request, "name", ""), "phone": getattr(request, "phone", ""),
            "email": getattr(request, "email", ""), "age": request.age,
            "employment_type": request.employment_type, "income": request.net_monthly_income,
            "loan_type": request.loan_type, "loan_amount": float(request.loan_amount),
            "tenure": request.tenure, "cibil": request.cibil_score,
            "decision": "Rejected (Critically Low CIBIL)", "probability": 0.0,
        })
        cibil = request.cibil_score
        gap   = 101 - cibil
        return {
            "decision":             "Rejected",
            "approval_probability": 0.0,
            "approved_amount":      0,
            "reasons": [
                f"CIBIL score {cibil} is critically low (1–100). "
                "No bank offers any loan product to applicants in this range."
            ],
            "guidance": [
                f"Your CIBIL score needs to improve by at least {gap} points to reach "
                "the absolute minimum threshold of 101.",
                "A score of 1–100 typically results from severe loan defaults, "
                "written-off accounts, or major derogatory marks on your credit report.",
                "Obtain a free copy of your CIBIL report from www.cibil.com and "
                "identify all negative entries.",
                "Settle or close any outstanding defaulted accounts or write-offs immediately.",
                "Open a secured credit card against a Fixed Deposit (₹10,000–₹25,000) and "
                "maintain zero default for 12–18 months to rebuild your score.",
                "After consistent on-time repayment, your score can recover to the 400–500 "
                "range within 18 months, and 600+ within 3 years.",
                "Re-apply once your CIBIL crosses 600 for standard loan products, or "
                "600+ for competitive interest rates.",
            ],
            "recommended_banks": [],
        }

    # ── TENURE EXCEEDED ───────────────────────────────────────────────────────
    if hard_reasons and hard_reasons[0].startswith("tenure_exceeded:"):
        max_tenure   = int(hard_reasons[0].split(":")[1])
        loan_id      = generate_loan_id(request.loan_type)
        reference_id = generate_reference_id()
        save_to_postgresql({
            "loan_id": loan_id, "reference_id": reference_id,
            "name": getattr(request, "name", ""), "phone": getattr(request, "phone", ""),
            "email": getattr(request, "email", ""), "age": request.age,
            "employment_type": request.employment_type, "income": request.net_monthly_income,
            "loan_type": request.loan_type, "loan_amount": float(request.loan_amount),
            "tenure": request.tenure, "cibil": request.cibil_score,
            "decision": "Rejected (Unrealistic Tenure)", "probability": 0.0,
        })
        return {
            "decision":             "Rejected",
            "approval_probability": 0.0,
            "approved_amount":      0,
            "reasons": [
                f"Requested tenure of {request.tenure} years exceeds the maximum "
                f"allowed limit for {request.loan_type} loan."
            ],
            "guidance": [
                f"Maximum allowed tenure for {request.loan_type} loan is {max_tenure} years.",
                f"Please reduce your tenure to {max_tenure} years or less to proceed.",
                "Reducing tenure will increase your monthly EMI but your application becomes eligible.",
                "Tip: Use a shorter tenure only if the resulting EMI fits within 50–60% of your monthly income.",
            ],
            "recommended_banks": [],
        }

    # ── CIBIL + FOIR BOTH EXCEEDED ────────────────────────────────────────────
    if hard_reasons and hard_reasons[0].startswith("cibil_and_foir_exceeded:"):
        parts      = hard_reasons[0].split(":")
        cibil_curr = int(parts[1])
        cibil_req  = int(parts[2])
        act_foir   = float(parts[3])
        lim_foir   = float(parts[4])
        cibil_gap  = cibil_req - cibil_curr
        reduced_amount = None
        if 101 <= cibil_curr < 200:
            reduced_amount = round(request.loan_amount * 0.25, 2)
        elif 200 <= cibil_curr < 400:
            reduced_amount = round(request.loan_amount * 0.35, 2)
        elif 400 <= cibil_curr < 600:
            reduced_amount = round(request.loan_amount * 0.50, 2)
        elif 600 <= cibil_curr < 650:
            reduced_amount = round(request.loan_amount * 0.60, 2)
        elif 650 <= cibil_curr < 680:
            reduced_amount = round(request.loan_amount * 0.75, 2)
        loan_id      = generate_loan_id(request.loan_type)
        reference_id = generate_reference_id()
        save_to_postgresql({
            "loan_id": loan_id, "reference_id": reference_id,
            "name": getattr(request, "name", ""), "phone": getattr(request, "phone", ""),
            "email": getattr(request, "email", ""), "age": request.age,
            "employment_type": request.employment_type, "income": request.net_monthly_income,
            "loan_type": request.loan_type, "loan_amount": float(request.loan_amount),
            "tenure": request.tenure, "cibil": request.cibil_score,
            "decision": "Rejected (CIBIL + High FOIR)", "probability": 0.0,
        })
        guidance = [
            f"Your application was rejected due to two combined issues: "
            f"low credit score (CIBIL {cibil_curr}) and high debt burden (FOIR {act_foir}%).",
            f"Primary blocker — Improve your CIBIL score by at least {cibil_gap} points "
            f"(current: {cibil_curr}, required: {cibil_req}+).",
            "Pay all existing EMIs on time for the next 6–12 months to build your score.",
            "Reduce credit card utilization below 30% and avoid new credit applications.",
            f"Secondary blocker — Your FOIR of {act_foir}% exceeds the allowed limit of {lim_foir}%. "
            f"Reduce your loan amount or extend your tenure to lower the monthly EMI.",
        ]
        if reduced_amount:
            guidance.append(
                f"With your current CIBIL of {cibil_curr}, you may be eligible for a "
                f"reduced loan amount of ₹{reduced_amount:,.0f} — provided you also "
                f"reduce your loan size to bring FOIR within limits."
            )
        return {
            "decision":             "Rejected",
            "approval_probability": 0.0,
            "approved_amount":      0,
            "reasons": [
                f"CIBIL score {cibil_curr} is below the minimum required {cibil_req} "
                f"for {request.loan_type} loan, and FOIR of {act_foir}% exceeds the "
                f"allowed limit of {lim_foir}%."
            ],
            "guidance":          guidance,
            "recommended_banks": [],
        }

    # ── FOIR EXCEEDED ─────────────────────────────────────────────────────────
    if hard_reasons and hard_reasons[0].startswith("foir_exceeded:"):
        parts       = hard_reasons[0].split(":")
        actual_foir = float(parts[1])
        limit_foir  = float(parts[2])
        loan_id      = generate_loan_id(request.loan_type)
        reference_id = generate_reference_id()
        save_to_postgresql({
            "loan_id": loan_id, "reference_id": reference_id,
            "name": getattr(request, "name", ""), "phone": getattr(request, "phone", ""),
            "email": getattr(request, "email", ""), "age": request.age,
            "employment_type": request.employment_type, "income": request.net_monthly_income,
            "loan_type": request.loan_type, "loan_amount": float(request.loan_amount),
            "tenure": request.tenure, "cibil": request.cibil_score,
            "decision": "Rejected (High FOIR)", "probability": 0.0,
        })
        has_existing_loans     = any(loan.monthly_emi > 0 for loan in request.existing_loans)
        is_unstable_employment = request.employment_type in ["Freelancer"]
        if has_existing_loans:
            guidance = [
                "Your rejection is not due to your CIBIL score but due to high existing loan burden.",
                f"Your current FOIR is {actual_foir}%, which is "
                f"{round(actual_foir - limit_foir, 1)}% above the allowed limit of {limit_foir}%.",
                "Close or prepay at least 1–2 existing loans before applying.",
                "Consider applying for a smaller loan amount to reduce the proposed EMI.",
                "Extending the tenure will lower your monthly EMI and improve your FOIR.",
            ]
        elif is_unstable_employment:
            guidance = [
                f"Banks apply a stricter FOIR limit of {limit_foir}% for Freelancer "
                "employment due to income variability.",
                f"Your current FOIR is {actual_foir}%, which is "
                f"{round(actual_foir - limit_foir, 1)}% above the allowed limit.",
                "Consider adding a co-applicant with stable salaried income to improve eligibility.",
                "Offering a property as collateral can significantly improve your approval chances.",
                "Alternatively, apply for a smaller loan amount to bring FOIR within the allowed limit.",
                "Extending the tenure will also reduce your monthly EMI and lower your FOIR.",
            ]
        else:
            guidance = [
                "Your rejection is because the requested loan amount is too high for your current income.",
                f"Your current FOIR is {actual_foir}%, which is "
                f"{round(actual_foir - limit_foir, 1)}% above the allowed limit of {limit_foir}%.",
                f"The monthly EMI for this loan exceeds your repayment capacity based on "
                f"your income of ₹{request.net_monthly_income:,.0f}.",
                "Consider applying for a lower loan amount that keeps your EMI within 60% of monthly income.",
                "Increasing your tenure can reduce the monthly EMI and improve affordability.",
            ]
        return {
            "decision":             "Rejected",
            "approval_probability": 0.0,
            "approved_amount":      0,
            "reasons": [
                f"Your debt obligations consume {actual_foir}% of your monthly income, "
                f"exceeding the maximum allowed limit of {limit_foir}%."
            ],
            "guidance":          guidance,
            "recommended_banks": [],
        }

    # ── HARD REJECTION (other rules) ──────────────────────────────────────────
    if hard_reasons:
        loan_id      = generate_loan_id(request.loan_type)
        reference_id = generate_reference_id()
        save_to_postgresql({
            "loan_id": loan_id, "reference_id": reference_id,
            "name": getattr(request, "name", ""), "phone": getattr(request, "phone", ""),
            "email": getattr(request, "email", ""), "age": request.age,
            "employment_type": request.employment_type, "income": request.net_monthly_income,
            "loan_type": request.loan_type, "loan_amount": float(request.loan_amount),
            "tenure": request.tenure, "cibil": request.cibil_score,
            "decision": "Rejected (Hard Rule)", "probability": 0.0,
        })
        guidance = generate_rejection_guidance({
            "loan_type":   request.loan_type,
            "cibil_score": request.cibil_score,
            "age":         request.age,
            "tenure":      request.tenure,
            "loan_amount": request.loan_amount,
        })
        return {
            "decision":             "Rejected",
            "approval_probability": 0.0,
            "approved_amount":      0,
            "reasons":           hard_reasons,
            "guidance":          guidance,
            "recommended_banks": [],
        }

    # ── ML PATH ───────────────────────────────────────────────────────────────
    proposed_emi    = calculate_emi(request.loan_amount, avg_interest, request.tenure)
    foir            = ((existing_total_emi + proposed_emi) / request.net_monthly_income) * 100
    repayment_ratio = estimate_repayment_ratio(request.cibil_score)

    input_dict = {
        "Age":                request.age,
        "Employment_Type":    request.employment_type,
        "Net_Monthly_Income": request.net_monthly_income,
        "Active_Loans_Count": len(request.existing_loans),
        "Existing_EMI":       existing_total_emi,
        "Total_Outstanding":  total_outstanding,
        "Tenure_Left":        avg_tenure_left_months,
        "Proposed_Loan_Type": request.loan_type,
        "Proposed_Amount":    request.loan_amount,
        "Proposed_EMI":       proposed_emi,
        "Proposed_Tenure":    request.tenure,
        "FOIR_Percentage":    foir,
        "CIBIL_Score":        request.cibil_score,
        "Repayment_Ratio":    repayment_ratio,
    }

    input_df = pd.DataFrame([input_dict])
    input_df["Employment_Type"]    = le_emp.transform(input_df["Employment_Type"])
    input_df["Proposed_Loan_Type"] = le_type.transform(input_df["Proposed_Loan_Type"])

    prob     = loan_model.predict_proba(input_df)[0][1]
    reasons  = []
    guidance = []

    shap_reasons = get_shap_reasons(input_df)

    if prob > 0.70:
        decision        = "Approved"
        approved_amount = request.loan_amount

    elif prob >= 0.40:
        decision  = "Partially Approved"

        # ── FIX: suggested is an affordability CEILING, not a target amount.
        # We must cap it at the requested loan_amount so we never suggest MORE
        # than the user asked for. Then take the lower of:
        #   • what they can actually afford  (suggested, already ≤ loan_amount)
        #   • 80% of what they asked          (partial_cap — risk-based haircut)
        suggested   = suggest_approved_amount({
            "Annual_income":      annual_income,
            "Loan_type":          request.loan_type,
            "Tenure":             request.tenure,
            "Existing_Total_EMI": existing_total_emi,
        })
        # Never suggest more than what was requested
        affordability_cap = min(suggested, request.loan_amount)
        # Risk-based haircut: 80% of requested
        partial_cap       = round(request.loan_amount * 0.80)
        # Final approved amount = lower of affordability ceiling and risk cap
        approved_amount   = min(affordability_cap, partial_cap)

        reasons.append("Credit risk acceptable but requested amount exceeds affordability threshold")
        reasons.extend(shap_reasons)

    else:
        decision        = "Rejected"
        approved_amount = 0
        reasons.append("Loan application does not meet the minimum eligibility criteria")
        reasons.extend(shap_reasons)

    # ── IDS & SAVE ────────────────────────────────────────────────────────────
    loan_id      = generate_loan_id(request.loan_type)
    reference_id = generate_reference_id()
    save_to_postgresql({
        "loan_id": loan_id, "reference_id": reference_id,
        "name": getattr(request, "name", ""), "phone": getattr(request, "phone", ""),
        "email": getattr(request, "email", ""), "age": request.age,
        "employment_type": request.employment_type, "income": request.net_monthly_income,
        "loan_type": request.loan_type, "loan_amount": float(request.loan_amount),
        "tenure": request.tenure, "cibil": request.cibil_score,
        "decision": decision, "probability": float(scale_probability(prob)),
    })

    # ── BANK RECOMMENDATION ───────────────────────────────────────────────────
    bank_input = request.dict()
    bank_input["approved_amount"] = approved_amount

    if decision == "Rejected":
        bank_result = {
            "no_banks_found": False, "reason": None, "suggestion": None, "banks": [],
        }
    else:
        bank_result = recommend_banks(bank_input)
        if bank_result["no_banks_found"] and decision == "Approved":
            reason_text     = bank_result["reason"]
            suggestion_text = bank_result["suggestion"]
            banks_list  = get_bank_list(request.loan_type)
            global_max  = max((b["maximum_loan_amount"] for b in banks_list), default=0)
            global_min  = min((b["minimum_loan_amount"] for b in banks_list), default=0)
            retry_amount = None
            if approved_amount > global_max and global_max > 0:
                retry_amount = global_max
            elif approved_amount < global_min and global_min > 0:
                retry_amount = global_min
            if retry_amount:
                retry_input = dict(bank_input)
                retry_input["approved_amount"] = retry_amount
                retry_result = recommend_banks(retry_input)
                if not retry_result["no_banks_found"]:
                    decision        = "Partially Approved"
                    approved_amount = retry_amount
                    bank_result     = retry_result
                    guidance.append(
                        f"Your credit profile qualifies for approval, but the requested "
                        f"loan amount of ₹{request.loan_amount:,.0f} exceeds the maximum "
                        f"offered by banks for {request.loan_type} loans."
                    )
                    guidance.append(
                        f"We have matched you with banks for a reduced amount of "
                        f"₹{retry_amount:,.0f}. You may apply for the difference separately "
                        "or renegotiate with the bank directly."
                    )
                else:
                    decision        = "Partially Approved"
                    approved_amount = retry_amount
                    guidance.append(reason_text)
                    guidance.append(suggestion_text)
            else:
                decision = "Partially Approved"
                guidance.append(reason_text)
                guidance.append(suggestion_text)
        elif bank_result["no_banks_found"]:
            guidance.append(bank_result["reason"])
            guidance.append(bank_result["suggestion"])

    # ── ADD AMORTIZATION SCHEDULE TO EACH BANK ────────────────────────────────
    banks_with_schedule = []
    for bank in bank_result["banks"]:
        interest_rate = bank.get("interest_rate", avg_interest)
        schedule      = generate_amortization_schedule(approved_amount, interest_rate, request.tenure)
        bank["amortization_schedule"] = schedule
        banks_with_schedule.append(bank)

    # ── FINAL API RESPONSE ────────────────────────────────────────────────────
    return {
        "loan_id":              loan_id,
        "reference_id":         reference_id,
        "decision":             decision,
        "approval_probability": scale_probability(prob),
        "approved_amount":      approved_amount,
        "reasons":              reasons,
        "guidance":             guidance,
        "recommended_banks":    banks_with_schedule,
    }