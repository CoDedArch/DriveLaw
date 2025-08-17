import os
import httpx
from urllib.parse import quote_plus
from app.core.config import settings

ARKESEL_API_KEY = settings.ARKESEL_API_KEY
ARKESEL_SENDER_ID = settings.ARKESEL_SENDER_ID


def format_number(number: str) -> str:
    return number.strip().replace(" ", "").replace("+", "")


async def send_sms_otp(contact: str, otp: str):
    if not ARKESEL_API_KEY:
        raise EnvironmentError("Missing Arkesel API key")

    formatted_contact = format_number(contact)

    message_body = (
        f"DriveLaw OTP: {otp}\n"
        f"This code expires in 5 minutes.\n\n"
        f"Akan: Wo nhyehyɛe kɔd ne {otp}. Ebɛyɛ adwuma mmerɛ 5 pɛ."
    )
    encoded_message = quote_plus(message_body)

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
            print(f"[SMS] OTP sent to {formatted_contact}: {response.text}")
    except httpx.HTTPError as e:
        print(f"[SMS ERROR] Failed to send OTP to {formatted_contact}: {e}")
        raise