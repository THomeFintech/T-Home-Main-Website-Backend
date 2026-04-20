"""
main.py – Loan Prediction + Application Workflow API
"""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

from fastapi import FastAPI, Depends, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.documents_router import router as document_router
from app.database import engine, get_db, Base

# ── Import ALL models first so SQLAlchemy registers every table ──
from app import models                          # User, LoanRecord
from app import models_extended                 # BankSelection, KYC, Income, etc.
from app.models_dashboard import (             # EMISchedule, Notification, Advisor, UserAdvisor
    EMISchedule, Notification, Advisor, UserAdvisor
)

# ── Schemas ──
from app.schemas import LoanRequest, ContactCreate, MarketingCreate

# ── DB models used directly in main ──
from app.models_extended import (
    ContactRequest, MarketingDetails, JobApplication
)
from app.loan_application_router import router as loan_app_router

# ── Prediction ──
from app.prediction import predict_loan

# ── Routers ──
from app.application_router import router as application_router
from app.auth_routes import router as auth_router
from app.dashboard_routes import router as dashboard_router


# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title="T-Home Fintech – Loan Approval & Application API",
    description="AI-powered Loan Prediction and End-to-End Application Workflow",
    version="1.0.0",
)

# ── CORS (only once) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://t-home-main-website-front-end.vercel.app",          
        "https://t-home-main-website-front-p8nramqlb-thomeadmins-projects.vercel.app",  
        "http://localhost:5173",                                      
        "http://localhost:3000",                                       
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ── Routers ──
app.include_router(application_router)
app.include_router(auth_router,        prefix="/auth",        tags=["Authentication"])
app.include_router(dashboard_router,   prefix="/dashboard",   tags=["Dashboard"])
app.include_router(document_router, prefix="/documents", tags=["Documents"])



# ── Create ALL tables (runs after every model is imported) ──
Base.metadata.create_all(bind=engine)


# ============================================================
# Health / DB Check
# ============================================================

@app.get("/db-check", tags=["Health"])
def check_db_connection(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "success", "message": "PostgreSQL connected successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "loan-api", "version": "1.0.0"}


@app.get("/", tags=["Health"])
def root():
    return {
        "service": "T-Home Fintech Loan API",
        "status": "running",
        "modules": [
            "Loan Prediction",
            "Bank Selection",
            "KYC Upload",
            "Income Documents",
            "Co-Applicant",
            "Final Submission",
            "Contact System",
            "Dashboard",
        ],
    }


# ============================================================
# Contact
# ============================================================

@app.post("/contact", tags=["Contact"])
def create_contact(data: ContactCreate, db: Session = Depends(get_db)):
    try:
        contact = ContactRequest(
            name=data.name,
            phone=data.phone,
            email=data.email,
            service=data.service,
            message=data.message,
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return {"status": "success", "message": "Contact request submitted successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================================
# Loan Prediction
# ============================================================

@app.post("/predict", tags=["Prediction"])
def predict(request: LoanRequest, db: Session = Depends(get_db)):
    try:
        result = predict_loan(request)
        return {
            "status": "success",
            "loan_id": result.get("loan_id"),
            "decision": result.get("decision"),
            "approval_probability": result.get("approval_probability"),
            "approved_amount": result.get("approved_amount"),
            "reasons": result.get("reasons", []),
            "guidance": result.get("guidance", []),
            "recommended_banks": result.get("recommended_banks", []),
        }
    except Exception as e:
        return {
            "status": "error",
            "loan_id": None,
            "decision": "Error",
            "approval_probability": 0,
            "approved_amount": 0,
            "reasons": ["Prediction failed"],
            "guidance": [str(e)],
            "recommended_banks": [],
        }


# ============================================================
# Marketing Subscription
# ============================================================

@app.post("/subscribe", tags=["Marketing"])
def subscribe(data: MarketingCreate, db: Session = Depends(get_db)):
    try:
        existing = db.query(MarketingDetails).filter(
            MarketingDetails.email == data.email
        ).first()
        if existing:
            return {"status": "exists", "message": "Email already subscribed"}
        db.add(MarketingDetails(email=data.email))
        db.commit()
        return {"status": "success", "message": "Subscribed successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================================
# Job Application
# ============================================================

@app.post("/apply-job", tags=["Careers"])
async def apply_job(
    full_name: str = Form(...),
    phone: str = Form(...),
    qualification: str = Form(...),
    experience: str = Form(...),
    cover_letter: str = Form(...),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        file_bytes = await resume.read()
        new_app = JobApplication(
            full_name=full_name,
            phone=phone,
            qualification=qualification,
            experience=experience,
            cover_letter=cover_letter,
            resume_data=file_bytes,
            resume_name=resume.filename,
        )
        db.add(new_app)
        db.commit()
        db.refresh(new_app)
        return {"status": "success", "message": "Application submitted successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
