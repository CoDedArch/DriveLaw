# services/email_service.py
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv
from app.core.config import settings

load_dotenv()

SENDGRID_API_KEY = settings.SENDGRID_API_KEY
SENDER_EMAIL = settings.FROM_EMAIL
DIGI_PERMIT_LOGO_URL = "https://your-cdn.com/static/digi-permit-logo.png"

if not SENDGRID_API_KEY:
    raise ValueError("SENDGRID_API_KEY is not set in settings")

async def send_email_notification(email: str, subject: str, html_content: str):
    """Send generic email notification"""
    try:
        # Create base email template
        full_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
            <div style="text-align: center; margin-bottom: 20px;">
                <img src="{DIGI_PERMIT_LOGO_URL}" alt="Digi-Permit Logo" width="80" style="margin-bottom: 10px;" />
                <h2 style="color: #6366F1;">Digi-Permit Notification</h2>
            </div>
            {html_content}
            <hr style="margin: 20px 0;">
            <p style="color: #666; font-size: 0.9em;">
                This is an automated notification. Please do not reply to this email.
            </p>
        </div>
        """
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails=email,
            subject=subject,
            html_content=full_html
        )
        
        response = sg.send(message)
        print(f"[EMAIL] Sent notification to {email}, status: {response.status_code}")
        return True
        
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send to {email}: {e}")
        if hasattr(e, 'body'):
            print(f"[EMAIL ERROR] Response: {e.body}")
        raise