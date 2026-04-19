from fastapi_mail import FastMail, MessageSchema
from app.email_config import conf

async def send_otp_email(email: str, otp: str):
    message = MessageSchema(
        subject="T-Home Verification Code",
        recipients=[email],
        body=f"""
Hello,

Your OTP is: {otp}

This code is valid for 5 minutes.

- T-Home Team
""",
        subtype="plain"
    )

    fm = FastMail(conf)
    await fm.send_message(message)