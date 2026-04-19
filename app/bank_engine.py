import json
import os
from .utils import calculate_emi, generate_amortization_schedule, INTEREST_RANGE

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data")

HOME_LOAN_BANKS     = json.load(open(os.path.join(DATA_PATH, "home_loans_cleaned.json")))
LAP_BANKS           = json.load(open(os.path.join(DATA_PATH, "loan_against_property_cleaned.json")))
MORTGAGE_BANKS      = json.load(open(os.path.join(DATA_PATH, "mortgage_loans_cleaned.json")))
PERSONAL_LOAN_BANKS = json.load(open(os.path.join(DATA_PATH, "personal_loans_cleaned.json")))


# ─────────────────────────────────────────────────────────────────────────────
# CIBIL → INTEREST RATE SLAB TABLE  (Home Loans only)
# Source: official rate card (screenshot).
# Maps (CIBIL band, loan amount slab, employment group) → target interest rate.
# ─────────────────────────────────────────────────────────────────────────────
CIBIL_RATE_TABLE = {

    # CIBIL ≥ 825
    "825_plus": {
        "range": (825, 900),
        "slabs": [
            {
                "slab_key": "up_to_5cr",
                "min_amount": 0,
                "max_amount": 50_000_000,
                "salaried_professional": 7.15,
                "self_employed_freelancer": 7.25,
            },
            {
                "slab_key": "5cr_to_15cr",
                "min_amount": 50_000_001,
                "max_amount": 150_000_000,
                "salaried_professional": 7.45,
                "self_employed_freelancer": 7.55,
            },
        ],
    },

    # CIBIL 800-824
    "800_824": {
        "range": (800, 824),
        "slabs": [
            {
                "slab_key": "up_to_5cr",
                "min_amount": 0,
                "max_amount": 50_000_000,
                "salaried_professional": 7.25,
                "self_employed_freelancer": 7.35,
            },
            {
                "slab_key": "5cr_to_15cr",
                "min_amount": 50_000_001,
                "max_amount": 150_000_000,
                "salaried_professional": 7.55,
                "self_employed_freelancer": 7.65,
            },
        ],
    },

    # CIBIL 775-799
    "775_799": {
        "range": (775, 799),
        "slabs": [
            {
                "slab_key": "up_to_50L",
                "min_amount": 0,
                "max_amount": 5_000_000,
                "salaried_professional": 7.35,
                "self_employed_freelancer": 7.45,
            },
            {
                "slab_key": "50L_to_2cr",
                "min_amount": 5_000_001,
                "max_amount": 20_000_000,
                "salaried_professional": 7.45,
                "self_employed_freelancer": 7.55,
            },
            {
                "slab_key": "2cr_to_15cr",
                "min_amount": 20_000_001,
                "max_amount": 150_000_000,
                "salaried_professional": 7.65,
                "self_employed_freelancer": 7.75,
            },
        ],
    },

    # CIBIL 750-774
    "750_774": {
        "range": (750, 774),
        "slabs": [
            {
                "slab_key": "up_to_50L",
                "min_amount": 0,
                "max_amount": 5_000_000,
                "salaried_professional": 7.45,
                "self_employed_freelancer": 7.55,
            },
            {
                "slab_key": "50L_to_2cr",
                "min_amount": 5_000_001,
                "max_amount": 20_000_000,
                "salaried_professional": 7.55,
                "self_employed_freelancer": 7.65,
            },
            {
                "slab_key": "2cr_to_15cr",
                "min_amount": 20_000_001,
                "max_amount": 150_000_000,
                "salaried_professional": 7.75,
                "self_employed_freelancer": 7.85,
            },
        ],
    },

    # CIBIL 725-749
    "725_749": {
        "range": (725, 749),
        "slabs": [
            {
                "slab_key": "up_to_50L",
                "min_amount": 0,
                "max_amount": 5_000_000,
                "salaried_professional": 7.65,
                "self_employed_freelancer": 7.75,
            },
            {
                "slab_key": "50L_to_2cr",
                "min_amount": 5_000_001,
                "max_amount": 20_000_000,
                "salaried_professional": 7.75,
                "self_employed_freelancer": 7.85,
            },
            {
                "slab_key": "2cr_to_15cr",
                "min_amount": 20_000_001,
                "max_amount": 150_000_000,
                "salaried_professional": 7.95,
                "self_employed_freelancer": 8.05,
            },
        ],
    },

    # CIBIL 700-724
    "700_724": {
        "range": (700, 724),
        "slabs": [
            {
                "slab_key": "up_to_50L",
                "min_amount": 0,
                "max_amount": 5_000_000,
                "salaried_professional": 7.95,
                "self_employed_freelancer": 8.15,
            },
            {
                "slab_key": "50L_to_2cr",
                "min_amount": 5_000_001,
                "max_amount": 20_000_000,
                "salaried_professional": 8.05,
                "self_employed_freelancer": 8.25,
            },
            {
                "slab_key": "2cr_to_15cr",
                "min_amount": 20_000_001,
                "max_amount": 150_000_000,
                "salaried_professional": 8.25,
                "self_employed_freelancer": 8.45,
            },
        ],
    },

    # CIBIL 600-699
    "600_699": {
        "range": (600, 699),
        "slabs": [
            {
                "slab_key": "up_to_50L",
                "min_amount": 0,
                "max_amount": 5_000_000,
                "salaried_professional": 8.75,
                "self_employed_freelancer": 8.95,
            },
            {
                "slab_key": "50L_to_2cr",
                "min_amount": 5_000_001,
                "max_amount": 20_000_000,
                "salaried_professional": 8.85,
                "self_employed_freelancer": 9.05,
            },
            {
                "slab_key": "2cr_to_15cr",
                "min_amount": 20_000_001,
                "max_amount": 150_000_000,
                "salaried_professional": 9.50,
                "self_employed_freelancer": 9.60,
            },
        ],
    },

    # CIBIL < 600  (201–599)
    "below_600": {
        "range": (201, 599),
        "slabs": [
            {
                "slab_key": "up_to_50L",
                "min_amount": 0,
                "max_amount": 5_000_000,
                "salaried_professional": 9.55,
                "self_employed_freelancer": 9.65,
            },
            {
                "slab_key": "50L_to_2cr",
                "min_amount": 5_000_001,
                "max_amount": 20_000_000,
                "salaried_professional": 9.65,
                "self_employed_freelancer": 9.75,
            },
            {
                "slab_key": "2cr_to_5cr",
                "min_amount": 20_000_001,
                "max_amount": 50_000_000,
                "salaried_professional": 10.00,
                "self_employed_freelancer": 10.10,
            },
        ],
    },

    # NTC / Thin-file: 150 ≤ CIBIL ≤ 200
    "150_200": {
        "range": (150, 200),
        "slabs": [
            {
                "slab_key": "up_to_35L",
                "min_amount": 0,
                "max_amount": 3_500_000,
                "salaried_professional": 7.65,
                "self_employed_freelancer": 7.75,
            },
            {
                "slab_key": "35L_to_2cr",
                "min_amount": 3_500_001,
                "max_amount": 20_000_000,
                "salaried_professional": 7.75,
                "self_employed_freelancer": 7.85,
            },
        ],
    },

    # NTC / Thin-file: 101 ≤ CIBIL ≤ 149
    "101_149": {
        "range": (101, 149),
        "slabs": [
            {
                "slab_key": "up_to_35L",
                "min_amount": 0,
                "max_amount": 3_500_000,
                "salaried_professional": 7.95,
                "self_employed_freelancer": 8.15,
            },
            {
                "slab_key": "35L_to_2cr",
                "min_amount": 3_500_001,
                "max_amount": 20_000_000,
                "salaried_professional": 8.05,
                "self_employed_freelancer": 8.25,
            },
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# CIBIL SCORE → RATE PREMIUM TABLE  (Personal / LAP / Mortgage)
#
# For non-Home loan types the CIBIL slab table above does not apply.
# Instead, we add a premium on top of each bank's minimum_interest_rate.
# Better CIBIL → lower premium → cheaper rate for the borrower.
# ─────────────────────────────────────────────────────────────────────────────
CIBIL_PREMIUM_TABLE = [
    # (min_cibil, max_cibil, premium_pct)
    (825, 900, 0.00),
    (800, 824, 0.10),
    (775, 799, 0.25),
    (750, 774, 0.40),
    (725, 749, 0.60),
    (700, 724, 0.90),
    (600, 699, 1.50),
    (201, 599, 2.50),
    (150, 200, 1.00),   # thin-file / NTC — treated leniently
    (101, 149, 1.50),
]

# A bank whose (min_rate + premium) > max_rate is capped at max_rate (not rejected).
_MAX_PREMIUM_ALLOWED = 3.0


# ─────────────────────────────────────────────────────────────────────────────
# EMPLOYMENT-PRODUCT AFFINITY TABLE
# ─────────────────────────────────────────────────────────────────────────────
EMPLOYMENT_AFFINITY = {
    ("salaried_professional", "Home"):     0.95,
    ("salaried_professional", "Personal"): 0.85,
    ("salaried_professional", "LAP"):      0.70,
    ("salaried_professional", "Mortgage"): 0.65,

    ("self_employed_freelancer", "LAP"):      0.90,
    ("self_employed_freelancer", "Mortgage"): 0.80,
    ("self_employed_freelancer", "Home"):     0.65,
    ("self_employed_freelancer", "Personal"): 0.55,
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: EMPLOYMENT GROUP
# ─────────────────────────────────────────────────────────────────────────────
def get_employment_group(employment_type: str) -> str:
    if employment_type in ("Salaried", "Professional"):
        return "salaried_professional"
    return "self_employed_freelancer"


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: CIBIL PREMIUM (for Personal / LAP / Mortgage)
# ─────────────────────────────────────────────────────────────────────────────
def get_cibil_premium(cibil: int) -> float:
    """
    Return the interest-rate premium (in percentage points) to add on top of
    a bank's minimum_interest_rate for non-Home loan types.
    Returns _MAX_PREMIUM_ALLOWED + 1 if CIBIL falls outside every defined band.
    """
    for lo, hi, premium in CIBIL_PREMIUM_TABLE:
        if lo <= cibil <= hi:
            return premium
    return _MAX_PREMIUM_ALLOWED + 1.0  # outside all bands → reject


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: HOME LOAN TARGET RATE (from CIBIL slab table)
# ─────────────────────────────────────────────────────────────────────────────
def get_target_rate(cibil: int, loan_amount: float, employment_type: str) -> float | None:
    """
    Look up the exact target interest rate from the rate card (Home Loans only).
    Returns None if CIBIL ≤ 100 (hard reject handled upstream).
    """
    if cibil <= 100:
        return None

    emp_group = get_employment_group(employment_type)

    for band_data in CIBIL_RATE_TABLE.values():
        lo, hi = band_data["range"]
        if lo <= cibil <= hi:
            for slab in band_data["slabs"]:
                if slab["min_amount"] <= loan_amount <= slab["max_amount"]:
                    return slab[emp_group]
            # Amount exceeds all slabs in this band → use the highest slab rate
            return band_data["slabs"][-1][emp_group]

    return None  # CIBIL not in any band (shouldn't happen if >100 and ≤900)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: COMPUTE EACH BANK'S EFFECTIVE RATE FOR THE BORROWER'S CIBIL PROFILE
#
# Returns (effective_rate, target_rate, rate_gap) or None if ineligible.
#
#   effective_rate  — the actual rate this bank would charge
#   target_rate     — the CIBIL-slab benchmark rate (borrower's ideal)
#   rate_gap        — effective_rate − target_rate  (0 = exact match; higher = costlier)
#
# Design rule (matches business requirement):
#   Rank-1  bank : rate_gap == 0  (exact match or best available ≤ target)
#   Rank-2/3 banks: smallest positive rate_gap, ordered ascending
# ─────────────────────────────────────────────────────────────────────────────
def _compute_bank_rate(
    bank: dict,
    loan_type: str,
    cibil: int,
    loan_amount: float,
    employment_type: str,
) -> tuple[float, float, float] | None:
    """
    Returns (effective_rate, target_rate, rate_gap) or None if the bank
    cannot serve this borrower's CIBIL / amount profile.
    """
    bank_min = bank["minimum_interest_rate"]
    bank_max = bank.get("maximum_interest_rate", bank_min + 5.0)

    if loan_type == "Home":
        target = get_target_rate(cibil, loan_amount, employment_type)
        if target is None:
            return None  # CIBIL ≤ 100

        # FIX: tighten the competitiveness window to +2.0 pp above target
        # (old code used 1.5 pp; 2.0 pp admits a wider but still useful set)
        if bank_min > target + 2.0:
            return None  # bank is uncompetitively expensive for this borrower

        # The bank charges at least its floor, but not less than the slab target.
        # If target < bank_min the borrower pays bank_min (bank won't go below floor).
        # If target ≥ bank_min the borrower benefits from the slab rate.
        effective = max(bank_min, target)
        effective = min(effective, bank_max)
        rate_gap  = round(effective - target, 4)
        return effective, target, rate_gap

    else:
        # Personal / LAP / Mortgage: add CIBIL-driven premium to bank's floor
        premium = get_cibil_premium(cibil)
        if premium > _MAX_PREMIUM_ALLOWED:
            return None  # CIBIL outside all defined bands

        effective = bank_min + premium
        # Cap at bank_max if the premium pushes us over it
        effective = min(effective, bank_max)
        target    = bank_min + premium  # target == effective for non-Home
        rate_gap  = round(effective - bank_min, 4)  # gap from bank floor
        return effective, target, rate_gap


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: BANK LIST BY LOAN TYPE
# ─────────────────────────────────────────────────────────────────────────────
def get_bank_list(loan_type: str) -> list:
    if loan_type == "Home":
        return HOME_LOAN_BANKS
    elif loan_type == "LAP":
        return LAP_BANKS
    elif loan_type == "Mortgage":
        return MORTGAGE_BANKS
    return PERSONAL_LOAN_BANKS


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: BANK AMOUNT LIMITS (used by prediction.py for pre-checks)
# ─────────────────────────────────────────────────────────────────────────────
def get_bank_limits(loan_type: str) -> dict:
    ALTERNATE_SUGGESTIONS = {
        "Home":     ["LAP", "Mortgage"],
        "Personal": ["LAP"],
        "LAP":      ["Mortgage", "Home"],
        "Mortgage": ["LAP"],
    }
    banks = get_bank_list(loan_type)
    if not banks:
        return {"global_min": 0, "global_max": 0, "alternates": []}
    return {
        "global_min": min(b["minimum_loan_amount"] for b in banks),
        "global_max": max(b["maximum_loan_amount"] for b in banks),
        "alternates": ALTERNATE_SUGGESTIONS.get(loan_type, []),
    }


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: SECONDARY SCORING (tie-break within same rate_gap bucket)
#
# Used to pick the best bank when multiple banks share an identical rate_gap.
# Higher score = better.
# ─────────────────────────────────────────────────────────────────────────────
def _secondary_score(
    bank: dict,
    effective_rate: float,
    target_rate: float,
    user: dict,
    monthly_income: float,
    loan_type: str,
    tenure: int,
    amount: float,
) -> float:
    # EMI affordability (50%)
    emi = calculate_emi(amount, effective_rate, tenure)
    emi_ratio = (emi / monthly_income) if monthly_income > 0 else 1.0
    emi_score = max(0.0, 1.0 - max(0.0, emi_ratio - 0.25) / 0.35)

    # Tenure headroom (30%)
    bank_max_tenure = bank.get("maximum_tenure", tenure)
    headroom        = max(0, bank_max_tenure - tenure)
    tenure_score    = min(1.0, headroom / 10.0)

    # Employment-product affinity (20%)
    emp_group      = get_employment_group(user.get("employment_type", "Salaried"))
    affinity_score = EMPLOYMENT_AFFINITY.get((emp_group, loan_type), 0.50)

    return round(0.50 * emi_score + 0.30 * tenure_score + 0.20 * affinity_score, 4)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT: RECOMMEND BANKS
# ─────────────────────────────────────────────────────────────────────────────
def recommend_banks(user: dict) -> dict:
    """
    Return the top-3 most suitable banks for a given user profile.

    Ranking rule (hard requirement):
        Slot 1 — bank whose effective_rate == target_rate  (exact match)
                 If no exact match, use the bank with the smallest positive gap.
        Slot 2 — next closest (different bank, different rate from slot 1)
        Slot 3 — next closest (different bank, different rate from slot 2)

    Expected keys in `user`:
        loan_type           str   — "Home" | "Personal" | "LAP" | "Mortgage"
        loan_amount         float — requested amount (or approved_amount after ML step)
        cibil_score         int
        employment_type     str   — "Salaried" | "Self-employed" | "Professional" | "Freelancer"
        age                 int
        tenure              int   — in years
        net_monthly_income  float
        approved_amount     float (optional)
        interest_rate       float (optional — explicit rate override from user)
    """
    banks          = get_bank_list(user["loan_type"])
    loan_type      = user["loan_type"]
    amount_to_calc = user.get("approved_amount") or user["loan_amount"]
    cibil          = user.get("cibil_score", 0)
    employment     = user.get("employment_type", "Salaried")
    monthly_income = user.get("net_monthly_income") or (user.get("annual_income", 0) / 12)
    tenure         = user["tenure"]

    # ── HARD REJECT: CIBIL 0–100 ─────────────────────────────────────────────
    if cibil <= 100:
        return {
            "no_banks_found": True,
            "reason": (
                f"CIBIL score {cibil} is critically low (≤ 100). "
                "No bank offers loans to applicants in this CIBIL range."
            ),
            "suggestion": (
                "A CIBIL score of at least 101 is required to access any loan product. "
                "Start by opening a secured credit card against a Fixed Deposit, "
                "use it lightly, and pay the full bill every month for 12–18 months."
            ),
            "banks": [],
        }

    # ── EXPLICIT INTEREST RATE RANGE CHECK ───────────────────────────────────
    explicit_rate = user.get("interest_rate")
    if explicit_rate is not None:
        ir_range = INTEREST_RANGE.get(loan_type)
        if ir_range:
            min_r, max_r = ir_range
            if not (min_r <= explicit_rate <= max_r):
                return {
                    "no_banks_found": True,
                    "reason": (
                        f"Interest rate {explicit_rate}% is outside the market range "
                        f"for {loan_type} loans ({min_r}% – {max_r}%). "
                        "No banks offer this product at the requested rate."
                    ),
                    "suggestion": (
                        f"Choose an interest rate between {min_r}% and {max_r}% "
                        f"for a {loan_type} loan and re-submit your application."
                    ),
                    "banks": [],
                }

    # ── GLOBAL MIN / MAX ──────────────────────────────────────────────────────
    all_max_limits = [b["maximum_loan_amount"] for b in banks]
    all_min_limits = [b["minimum_loan_amount"]  for b in banks]
    global_max     = max(all_max_limits) if all_max_limits else 0
    global_min     = min(all_min_limits) if all_min_limits else 0

    # ── PER-BANK ELIGIBILITY FILTER ──────────────────────────────────────────
    eligible = []

    for bank in banks:
        # Age check
        if not (bank["minimum_age_limit"] <= user["age"] <= bank["maximum_age_limit"]):
            continue

        # Loan amount range
        if not (bank["minimum_loan_amount"] <= amount_to_calc <= bank["maximum_loan_amount"]):
            continue

        # Tenure limit
        if tenure > bank["maximum_tenure"]:
            continue

        # CIBIL-aware rate computation
        rate_result = _compute_bank_rate(bank, loan_type, cibil, amount_to_calc, employment)
        if rate_result is None:
            continue  # bank not suitable for this CIBIL profile

        effective_rate, target_rate, rate_gap = rate_result

        emi      = calculate_emi(amount_to_calc, effective_rate, tenure)
        schedule = generate_amortization_schedule(amount_to_calc, effective_rate, tenure)

        sec_score = _secondary_score(
            bank=bank,
            effective_rate=effective_rate,
            target_rate=target_rate,
            user=user,
            monthly_income=monthly_income,
            loan_type=loan_type,
            tenure=tenure,
            amount=amount_to_calc,
        )

        eligible.append({
            "bank_name":             bank["bank_name"],
            "interest_rate":         round(effective_rate, 2),
            "emi":                   round(emi, 2),
            "amortization_schedule": schedule,
            "_rate_gap":             rate_gap,        # primary sort key (ASC)
            "_sec_score":            sec_score,       # tie-break (DESC)
            "_target_rate":          round(target_rate, 2),
            "_bank_raw":             bank,
        })

    # ── NO ELIGIBLE BANKS ─────────────────────────────────────────────────────
    if not eligible:
        if amount_to_calc > global_max:
            reason = (
                f"Loan amount ₹{amount_to_calc:,.0f} exceeds the maximum limit of "
                f"₹{global_max:,.0f} for {loan_type} loan."
            )
            suggestion = (
                f"Consider reducing your loan amount to ₹{global_max:,.0f} or below."
            )
        elif amount_to_calc < global_min:
            reason = (
                f"Loan amount ₹{amount_to_calc:,.0f} is below the minimum limit of "
                f"₹{global_min:,.0f} for {loan_type} loan."
            )
            suggestion = f"Consider requesting at least ₹{global_min:,.0f}."
        else:
            reason = (
                "No banks currently match your profile criteria "
                "(age, tenure, loan amount, or CIBIL score band)."
            )
            suggestion = (
                "Try adjusting your tenure or loan amount. "
                "Improving your CIBIL score may also unlock more options."
            )

        return {
            "no_banks_found": True,
            "reason":         reason,
            "suggestion":     suggestion,
            "banks":          [],
        }

    # ── SORT: primary = rate_gap ASC, secondary = sec_score DESC ─────────────
    # This ensures the bank closest to (or exactly at) the slab target rate
    # always comes first.
    sorted_banks = sorted(eligible, key=lambda x: (x["_rate_gap"], -x["_sec_score"]))

    # ── SELECT TOP-3 WITH DISTINCT BANKS AND DISTINCT RATES ──────────────────
    #
    # Rule:
    #   Slot 1 → lowest rate_gap (exact match preferred)
    #   Slot 2 → next different rate AND different bank name
    #   Slot 3 → next different rate (from both slot 1 & 2) AND different bank name
    #
    # "Different rate" = differs by ≥ 0.01 pp so we never show two identical
    # rates in the recommendation list.
    top3: list[dict] = []
    seen_banks: set[str]  = set()
    seen_rates: set[float] = set()

    for candidate in sorted_banks:
        bank_name = candidate["bank_name"]
        rate      = candidate["interest_rate"]

        # Skip duplicate banks or duplicate rates
        if bank_name in seen_banks:
            continue
        if rate in seen_rates:
            continue

        seen_banks.add(bank_name)
        seen_rates.add(rate)
        top3.append(candidate)

        if len(top3) == 3:
            break

    # ── BUILD MATCH TAGS ─────────────────────────────────────────────────────
    def _build_match_tags(candidate: dict, rank: int) -> list[str]:
        tags = []
        rg   = candidate["_rate_gap"]

        if rank == 1:
            if rg == 0.0:
                tags.append("Exact rate match for your credit profile")
            else:
                tags.append(f"Best available rate (+{rg:.2f}% above your slab target)")
        else:
            tags.append(f"Competitive alternative (+{rg:.2f}% above target rate)")

        emi_pct = (candidate["emi"] / monthly_income * 100) if monthly_income > 0 else 100
        if emi_pct <= 30:
            tags.append(f"Low EMI burden ({emi_pct:.0f}% of monthly income)")
        elif emi_pct <= 45:
            tags.append(f"Manageable EMI ({emi_pct:.0f}% of monthly income)")

        bank_raw = candidate["_bank_raw"]
        headroom = bank_raw.get("maximum_tenure", 0) - tenure
        if headroom >= 10:
            tags.append(f"Up to {headroom} years extra tenure flexibility")
        elif headroom >= 5:
            tags.append(f"{headroom} years tenure buffer available")

        emp_group = get_employment_group(user.get("employment_type", "Salaried"))
        affinity  = EMPLOYMENT_AFFINITY.get((emp_group, loan_type), 0.50)
        if affinity >= 0.85:
            tags.append("Specialist lender for your employment and loan type")
        elif affinity >= 0.70:
            tags.append("Good lender fit for your employment profile")

        return tags[:3]

    # ── ASSEMBLE OUTPUT ───────────────────────────────────────────────────────
    output: list[dict] = []
    for rank, candidate in enumerate(top3, start=1):
        match_tags = _build_match_tags(candidate, rank)

        # Compute a normalised match_score (100 = exact, decreases with gap)
        gap        = candidate["_rate_gap"]
        sec        = candidate["_sec_score"]
        # Combine: 60% rate proximity, 40% secondary factors
        rate_prox  = max(0.0, 1.0 - gap / 2.0)          # 0 gap → 1.0; 2 pp gap → 0.0
        match_score = round((0.60 * rate_prox + 0.40 * sec) * 100, 1)

        output.append({
            "bank_name":             candidate["bank_name"],
            "interest_rate":         candidate["interest_rate"],
            "emi":                   candidate["emi"],
            "amortization_schedule": candidate["amortization_schedule"],
            "match_score":           match_score,
            "match_tags":            match_tags,
        })

    return {
        "no_banks_found": False,
        "reason":         None,
        "suggestion":     None,
        "banks":          output,
    }