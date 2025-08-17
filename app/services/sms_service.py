# services/sms_service.py
import os
import httpx
from urllib.parse import quote_plus
from app.core.config import settings

ARKESEL_API_KEY = settings.ARKESEL_API_KEY
ARKESEL_SENDER_ID = settings.ARKESEL_SENDER_ID

def format_number(number: str) -> str:
    """Standardize phone number format"""
    return number.strip().replace(" ", "").replace("+", "")

async def send_sms_notification(contact: str, message: str):
    """Send generic SMS notification"""
    if not ARKESEL_API_KEY:
        raise EnvironmentError("Missing Arkesel API key")

    formatted_contact = format_number(contact)
    encoded_message = quote_plus(message)

    url = (
        f"https://sms.arkesel.com/sms/api"
        f"?action=send-sms"
        f"&api_key={ARKESEL_API_KEY}"
        f"&to={formatted_contact}"
        f"&from={ARKESEL_SENDER_ID}"
        f"&sms={encoded_message}"
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            print(f"[SMS] Notification sent to {formatted_contact}")
            return True
    except httpx.HTTPError as e:
        print(f"[SMS ERROR] Failed to send to {formatted_contact}: {e}")
        raise