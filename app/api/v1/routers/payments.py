from datetime import datetime
import traceback
from fastapi import APIRouter, Query, Request, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from app.core.database import aget_db
from app.core.security import decode_jwt_token
from app.models.payment import Payment, PaymentPurpose, PaymentStatus
from app.services.PaystackServices import PaystackService
from app.schemas.payment import PaymentInitRequest, PaymentInitResponse, PaymentMethod, PaymentRequest
from app.models.user import User

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/initialize", response_model=PaymentInitResponse)
async def initialize_payment(
    payload: PaymentRequest,
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    # 🔐 Extract user from cookie token
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload_token = decode_jwt_token(token)
        user_id = int(payload_token.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 🔍 Get user
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 💳 Create pending payment
    reference = f"APP-{uuid4().hex[:10].upper()}"
    payment = Payment(
        user_id=user.id,
        amount=payload.amount,
        purpose=payload.purpose or PaymentPurpose.PROCESSING_FEE,  # Allow specifying purpose
        status=PaymentStatus.PENDING,
        transaction_reference=reference,
        application_id=payload.application_id  # Store application ID if provided
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    # 🚀 Call Paystack API
    try:
        response = await PaystackService.initialize_payment(
            data=PaymentInitRequest(
                amount=payload.amount,
                email=user.email,
                callback_url=str(payload.callback_url),
                purpose=payload.purpose or PaymentPurpose.PROCESSING_FEE,
                notes=None,
                user_id=user.id,
                reference=reference,
                application_id=payload.application_id
            )
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

    return response



@router.get("/verify")
async def verify_payment(reference: str, db: AsyncSession = Depends(aget_db)):
    # 1. Fetch payment record by reference
    result = await db.execute(
        select(Payment).where(Payment.transaction_reference == reference)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status == PaymentStatus.COMPLETED:
        return {
            "message": "Already verified", 
            "status": payment.status,
            "purpose": payment.purpose
        }

    # 2. Verify with Paystack
    try:
        verification = await PaystackService.verify_transaction(reference)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3. Update payment status
    payment.status = PaymentStatus.COMPLETED
    payment.payment_date = datetime.fromisoformat(verification["paid_at"].replace("Z", "+00:00")).replace(tzinfo=None)
    
    # # If this was a certificate payment, update the application status
    # if payment.purpose == PaymentPurpose.CERTIFICATE_FEE and payment.application_id:
    #     application = await db.get(PermitApplication, payment.application_id)
    #     if application:
    #         application.payment_status = "completed"
    #         db.add(application)
    
    db.add(payment)
    await db.commit()

    return {
        "message": "Payment verified", 
        "status": payment.status,
        "purpose": payment.purpose
    }