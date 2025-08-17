# app/utils/contact_utils.py
import re

def normalize_contact(contact: str, channel: str) -> str:
    if channel == "email":
        return contact.lower()
    elif channel == "sms":
        return format_phone(contact)
    return contact

def format_phone(phone: str) -> str:
    phone = re.sub(r"\D", "", phone)
    if phone.startswith("2330"):
        phone = "233" + phone[4:]
    elif phone.startswith("0") and len(phone) == 10:
        phone = "233" + phone[1:]
    return "+" + phone if not phone.startswith("+") else phone
