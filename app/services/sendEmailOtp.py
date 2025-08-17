# services/email_service.py

import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv
from app.core.config import settings

load_dotenv()

# Use SendGrid API key from settings
SENDGRID_API_KEY = settings.SENDGRID_API_KEY
SENDER_EMAIL = settings.FROM_EMAIL

DRIVELAW_LOGO_URL = "https://your-cdn.com/static/drivelaw-logo.png"  # Replace with actual image URL

if not SENDGRID_API_KEY:
    raise ValueError("SENDGRID_API_KEY is not set in settings")


async def send_email_otp(email: str, code: str):
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <img src="{DRIVELAW_LOGO_URL}" alt="DriveLaw Logo" width="80" style="margin-bottom: 10px;" />
            <h2 style="color: #3B82F6;">DriveLaw Verification Code</h2>
        </div>

        <p>Hello / <strong>Agoo</strong>,</p>
        
        <p>
            Your one-time verification code is: <br>
            <span style="font-size: 24px; font-weight: bold; color: #3B82F6;">{code}</span>
        </p>

        <p>This code will expire in 5 minutes. If you didn't request this code, you can safely ignore this email.</p>

        <hr style="margin: 20px 0;">

        <p><strong>Akan Translation:</strong></p>
        <p>
            Wo DriveLaw dwumadie ho nhyehyɛe kɔd no ne: <br>
            <span style="font-size: 24px; font-weight: bold; color: #3B82F6;">{code}</span>
        </p>
        <p>
            Kɔd no bɛyɛ adwuma mmerɛ 5 pɛ. Sɛ woannhyɛ sɛ wɔmfa nhyehyɛe kɔd mma wo a, gye ntɔkwaw na gya email no.
        </p>

        <p style="margin-top: 30px;">– DriveLaw Team</p>
    </div>
    """

    try:
        # Create SendGrid client
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        
        # Create the email message
        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails=email,
            subject="DriveLaw OTP Code / Nhyehyɛe Kɔd",
            html_content=html_content
        )
        
        # Send the email
        response = sg.send(message)
        
        print(f"[EMAIL] Sent OTP {code} to {email}, status: {response.status_code}")
        
        # Return success indicator
        return {
            "success": True,
            "status_code": response.status_code,
            "message": "Email sent successfully"
        }
        
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send OTP to {email}: {e}")
        
        # Log more details for debugging
        if hasattr(e, 'status_code'):
            print(f"[EMAIL ERROR] HTTP Status: {e.status_code}")
        if hasattr(e, 'body'):
            print(f"[EMAIL ERROR] Response Body: {e.body}")
            
        raise