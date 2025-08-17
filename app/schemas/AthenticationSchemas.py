from pydantic import BaseModel, validator
from app.utils.contact_utils import normalize_contact


class SendOtpRequest(BaseModel):
    contact: str
    channel: str

    @validator("channel")
    def validate_channel(cls, v):
        if v not in ("email", "sms"):
            print("Validating Channels")
            raise ValueError("Channel must be 'email' or 'sms'")
        return v

    @validator("contact", pre=True)
    def normalize_contact_value(cls, v):
        channel = "email" if "@" in v else "sms"
        if channel:
            normalized_contact = normalize_contact(v, channel)
            return normalized_contact
        return v


class VerifyOtpRequest(BaseModel):
    contact: str
    otp: str
    remember: bool

    @validator("contact", pre=True)
    def normalize_contact_value(cls, v):
        # Default to 'sms' for VerifyOtpRequest if no channel field
        channel = "email" if "@" in v else "sms"
        return normalize_contact(v, channel)
