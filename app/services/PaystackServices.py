import httpx
import uuid
from typing import Optional
from app.schemas.payment import PaymentInitRequest, PaymentInitResponse
from app.core.config import settings

class PaystackService:
    BASE_URL = "https://api.paystack.co"

    @classmethod
    async def initialize_payment(cls, data: PaymentInitRequest) -> PaymentInitResponse:
        url = f"{cls.BASE_URL}/transaction/initialize"

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "email": data.email,
            "amount": int(data.amount * 100),  # Paystack expects amount in pesewas
            "callback_url": data.callback_url,
            "reference": data.reference,  # ✅ use passed-in reference
            "metadata": {
                "purpose": data.purpose.value,
                "notes": data.notes or "",
                "user_id": data.user_id
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                raise Exception("Failed to initialize Paystack payment")

            resp_data = response.json()
            if not resp_data.get("status"):
                raise Exception(resp_data.get("message", "Paystack init failed"))

            data = resp_data["data"]
            return PaymentInitResponse(
                authorization_url=data["authorization_url"],
                reference=data["reference"],
                access_code=data.get("access_code"),
                status="success",
            )
        
    @classmethod
    async def verify_transaction(cls, reference: str) -> dict:
        url = f"{cls.BASE_URL}/transaction/verify/{reference}"

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                raise Exception("Failed to verify payment")

            resp_data = response.json()

            if not resp_data.get("status"):
                raise Exception(resp_data.get("message", "Verification failed"))

            return resp_data["data"]