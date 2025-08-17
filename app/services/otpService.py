from datetime import datetime, timedelta
from app.models.user import User
from app.core.constants import UserRole, VerificationStage
from fastapi.exceptions import HTTPException
import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.user import UnverifiedUser
from app.services.sendEmailOtp import send_email_otp
from app.services.sendSmsOtp import send_sms_otp
from enum import Enum
from app.core.security import create_jwt_token

MAX_ATTEMPTS = 5
LOCK_DURATION_MINUTES = 15
OTP_EXPIRY_MINUTES = 5

class OTPVerificationStatus(str, Enum):
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    CODE_EXPIRED = "code_expired"
    CODE_INVALID = "code_invalid"
    MAX_ATTEMPTS = "max_attempts"
    LOCKED = "locked"


class OtpService:
    async def generate_otp(self, email_or_phone: str, db: AsyncSession) -> str:
        otp = str(secrets.randbelow(900000) + 100000)
        expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)

        try:
            result = await db.execute(
                select(UnverifiedUser).where(
                    (UnverifiedUser.email == email_or_phone) |
                    (UnverifiedUser.phone == email_or_phone)
                )
            )
            user = result.scalar_one_or_none()
        except Exception as e:
            print(f"Query failed: {type(e).__name__}: {e}")
            raise

        now = datetime.utcnow()

        if user:
            if user.is_locked and user.lock_expires and user.lock_expires > now:
                raise ValueError("User is temporarily locked due to too many failed attempts. Please try again later.")

            # Reset OTP and unlock user if lock expired
            if user.lock_expires and user.lock_expires <= now:
                user.is_locked = False
                user.verification_attempts = 0
                user.lock_expires = None

            user.otp_secret = otp
            user.otp_expires = expires_at
            user.verification_attempts = 0
        else:
            user = UnverifiedUser(
                email=email_or_phone if "@" in email_or_phone else None,
                phone=None if "@" in email_or_phone else email_or_phone,
                otp_secret=otp,
                otp_expires=expires_at,
                verification_attempts=0,
                is_locked=False,
                lock_expires=None,
                verification_channel="email" if "@" in email_or_phone else "sms"
            )
            db.add(user)

        await db.commit()
        return otp

    
    async def send_otp (self, contact: str,  channel:str, db: AsyncSession ):
        if channel not in ["email", "sms"]:
            raise ValueError("Invalid channel")
        # generate the otp
        try:
            otp = await self.generate_otp(contact, db)
        except ValueError as e:
            raise ValueError("User is temporarily locked due to too many failed attempts. Please try again later.")
        
        if channel == "email":
            await send_email_otp(contact, otp)
        else:
            await send_sms_otp(contact, otp)

    async def verify_otp(self, email_or_phone: str, input_code: str, remember: bool, db: AsyncSession) -> OTPVerificationStatus:
        result = await db.execute(
            select(UnverifiedUser).where(
                (UnverifiedUser.email == email_or_phone) |
                (UnverifiedUser.phone == email_or_phone)
            )
        )
        unverified_user = result.scalar_one_or_none()

        now = datetime.utcnow()

        if not unverified_user:
            return {"status": OTPVerificationStatus.NOT_FOUND}

        if unverified_user.is_locked and unverified_user.lock_expires and unverified_user.lock_expires > now:
            return {"status": OTPVerificationStatus.LOCKED}

        if unverified_user.otp_expires < now:
            return {"status": OTPVerificationStatus.CODE_EXPIRED}

        if unverified_user.otp_secret != input_code:
            unverified_user.verification_attempts += 1
            if unverified_user.verification_attempts >= MAX_ATTEMPTS:
                unverified_user.is_locked = True
                unverified_user.lock_expires = now + timedelta(minutes=LOCK_DURATION_MINUTES)
            await db.commit()
            return {
            "status": OTPVerificationStatus.MAX_ATTEMPTS 
            if unverified_user.is_locked else OTPVerificationStatus.CODE_INVALID
            }

        onboarding_stages = {VerificationStage.OTP_PENDING, VerificationStage.OTP_VERIFIED}

        # IF OTP  is correct - CHECK if user Exists
        user_query = await db.execute(
            select(User).where(
                (User.email == email_or_phone) | (User.phone == email_or_phone)
            )
        )

        user = user_query.scalar_one_or_none()


        # set Onboarding to False
        if not user:
            user = User(
                email=email_or_phone if "@" in email_or_phone else None,
                phone=email_or_phone if "@" not in email_or_phone else None,
                first_name=None,  # Will be collected during onboarding
                last_name=None,
                is_active=False,
                preferred_verification="email" if "@" in email_or_phone else "sms",
                role=UserRole.DRIVER,
                verification_stage=VerificationStage.OTP_VERIFIED,
            )
            db.add(user)
            onboarding = True
        else:
            onboarding = user.verification_stage in onboarding_stages
        # Clean Up the unverified user
        await db.delete(unverified_user)
        await db.commit()

        # we'll issue a jwt token that last 1 hour
        method = "email" if "@" in email_or_phone else "phone"
        payload = {
            "sub": str(user.id),
            "onboarding": onboarding,
            "role": user.role.value,
            "method": method,
        }


        if remember:
            token = create_jwt_token(payload, expires_delta=timedelta(days=30))
        else:
            token = create_jwt_token(payload, expires_delta=timedelta(hours=3))


        return {
            "status": OTPVerificationStatus.SUCCESS,
            "token": token,
            "onboarding": onboarding,
            "role": user.role.value
        }