from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from uuid import UUID
from app.email_service import send_otp_email
from app.utils import generate_otp
from datetime import datetime, timedelta
from app.schemas import VerifyOTPRequest

from app.database import SessionLocal
from app.models import User
from app.security import hash_password, verify_password
from app.jwt_handler import create_access_token, SECRET_KEY, ALGORITHM
from app.schemas import (
    RegisterRequest,
    LoginRequest,
    UpdateProfileRequest,
    UpdateContactRequest,
    ChangePasswordRequest
)
import requests

from pydantic import BaseModel
from typing import Optional

class GoogleAuthRequest(BaseModel):
    google_id: str
    email: str
    name: str
    picture: Optional[str] = None

print("🔥 AUTH ROUTES LOADED FROM:", __file__)

router = APIRouter()
security = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# REGISTER USER

@router.post("/register")
async def register(user: RegisterRequest, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # ✅ generate OTP ONCE
    otp = generate_otp()

    print("🔥 REGISTER API HIT")
    print("🔥 OTP GENERATED:", otp)

    new_user = User(
        name=user.name,
        email=user.email.lower(),
        phone=user.phone,
        password=hash_password(user.password),
        otp=otp,
        otp_expiry=datetime.utcnow() + timedelta(minutes=5),
        is_verified=False
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # ✅ send email ONLY ONCE
    print("🔥 BEFORE EMAIL SEND")
    await send_otp_email(user.email, otp)
    print("🔥 AFTER EMAIL SEND")

    return {
        "message": "OTP sent to email",
        "email": user.email
    }

# LOGIN USER
@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):

    db_user = None

    # 🔥 check email login
    if payload.email:
        db_user = db.query(User).filter(User.email == payload.email).first()

    # 🔥 check phone login
    elif payload.phone:
        db_user = db.query(User).filter(User.phone == payload.phone).first()

    # ❌ user not found
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # ❌ wrong password
    if not verify_password(payload.password, db_user.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    # 🔐 generate token
    token = create_access_token({"user_id": str(db_user.id)})

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@router.post("/google")  # ✅ becomes /auth/google
def google_auth(data: GoogleAuthRequest, db: Session = Depends(get_db)):

    # 1️⃣ Find by google_id
    user = db.query(User).filter(User.google_id == data.google_id).first()

    if not user:
        # 2️⃣ Check if email already registered via email/password
        user = db.query(User).filter(User.email == data.email).first()

        if user:
            # ✅ Link Google to existing account
            user.google_id = data.google_id
            user.auth_provider = "google"
            user.is_verified = True
        else:
            # ✅ New user via Google
            user = User(
                name=data.name,
                email=data.email,
                google_id=data.google_id,
                auth_provider="google",
                is_verified=True,
            )
            db.add(user)

    db.commit()
    db.refresh(user)

    token = create_access_token({"user_id": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    print("🔥 /me API HIT")
    token = credentials.credentials
    print("🔥 TOKEN:", token)
    

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    print("🔥 PAYLOAD:", payload)

    user_id = payload.get("user_id")
    print("🔥 USER ID:", user_id)

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    print("🔥 USER FROM DB:", user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
    "id": str(user.id),
    "name": user.name,
    "email": user.email,
    "role": user.role,
    "dob": user.dob,
    "pan": user.pan,
    "address": user.address,
    "phone": user.phone
}


@router.put("/update-profile")
def update_profile(
    data: UpdateProfileRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user_id = payload.get("user_id")

    user = db.query(User).filter(User.id == UUID(user_id)).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # combine first + last name
    user.name = f"{data.first_name} {data.last_name}"
    user.dob = data.dob
    user.pan = data.pan
    user.address = data.address

    db.commit()

    return {"message": "Profile updated successfully"}

@router.put("/update-contact")
def update_contact(
    data: UpdateContactRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user_id = payload.get("user_id")

    user = db.query(User).filter(User.id == UUID(user_id)).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.email = data.email
    user.phone = data.phone

    db.commit()

    return {"message": "Contact updated successfully"}

@router.put("/change-password")
def change_password(
    data: ChangePasswordRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user_id = payload.get("user_id")

    user = db.query(User).filter(User.id == UUID(user_id)).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(data.old_password, user.password):
        raise HTTPException(status_code=400, detail="Old password incorrect")

    user.password = hash_password(data.new_password)

    db.commit()

    return {"message": "Password updated successfully"}

from datetime import datetime

@router.post("/verify-otp")
def verify_otp(data: VerifyOTPRequest, db: Session = Depends(get_db)):

    # ✅ normalize email
    email = data.email.lower()

    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ❌ already verified
    if user.is_verified:
        raise HTTPException(status_code=400, detail="User already verified")

    # ❌ OTP not present
    if not user.otp:
        raise HTTPException(status_code=400, detail="OTP not generated")

    # ❌ OTP mismatch
    if user.otp != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # ❌ OTP expired
    if not user.otp_expiry or user.otp_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired")

    # ✅ success
    user.is_verified = True
    user.otp = None
    user.otp_expiry = None
    db.commit()

    token = create_access_token({"user_id": str(user.id)})

    return {
        "message": "Verified successfully",
        "access_token": token
    }


from datetime import datetime, timedelta
from app.schemas import ResendOTPRequest

@router.post("/resend-otp")
async def resend_otp(data: ResendOTPRequest, db: Session = Depends(get_db)):

    email = data.email.lower()

    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="User already verified")

    # 🔥 generate new OTP
    otp = generate_otp()

    user.otp = otp
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=5)

    db.commit()

    # 🔥 send email
    await send_otp_email(email, otp)

    return {"message": "OTP resent successfully"}