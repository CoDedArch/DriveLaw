from datetime import timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
# from app.core.constants import VerificationStage
from app.models.user import User
from app.schemas.AthenticationSchemas import SendOtpRequest, VerifyOtpRequest
from authlib.integrations.starlette_client import OAuth
from app.core.database import aget_db
# from app.schemas.User import ApplicantTypeOut, CurrentUserResponse, GhanaCardInput, UserDocumentOut, UserOut, UserProfileOut
from app.services.otpService import OtpService
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.services.otpService import OTPVerificationStatus
import os
from dotenv import load_dotenv
from app.core.security import decode_jwt_token
# from app.core.config import settings

load_dotenv()


router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

otp_service = OtpService()
limiter = Limiter(key_func=get_remote_address)

@router.post("/send-otp", status_code=200)
@limiter.limit("3/minute")
@router.post("/send-otp")
async def send_otp(
    request: Request,
    payload: SendOtpRequest,
    db: AsyncSession = Depends(aget_db)
):
    print("Request Recieved")
    try:
        await otp_service.send_otp(payload.contact, payload.channel, db)
        return {"message": f"OTP sent via {payload.channel}"}

    except ValueError as ve:
        # Catch expected issues like locked user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Too many incorrect attempts. You have been temporarily locked out."
        )

    except Exception as e:
        # Log unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="You are not connected"
        )


@router.post("/verify-otp", status_code=200)
@limiter.limit("3/minute")
async def verify_otp(
    request: Request,
    payload: VerifyOtpRequest,
    db: AsyncSession = Depends(aget_db)
):
    user_remember_me = payload.remember

    result = await otp_service.verify_otp(payload.contact, payload.otp, user_remember_me, db)
    print("results is")
    status = result.get("status")

    if status == OTPVerificationStatus.SUCCESS:
        token = result["token"]
        onboarding = result['onboarding']
        role = result["role"]

        print("role is", role)

        response = JSONResponse( {
            "message": "OTP verified successfully",
            "onboarding": onboarding,
            "role": role
        })

        expires = timedelta(days=30) if user_remember_me else timedelta(hours=1)

        response.set_cookie(
            key="auth_token",
            value=token,
            httponly=True,
            secure=False,  # Must be True for production
            samesite="lax",
            domain="localhost",  # Explicit domain for local development
            path="/",  # Make cookie available for all paths
            max_age=int(expires.total_seconds())
        )

        response.headers["Access-Control-Allow-Origin"] = "http://localhost:3000"
        response.headers["Access-Control-Allow-Credentials"] = "true"

        print("Cookie set in response:", response.headers.get("set-cookie"))

        return response

    if status == OTPVerificationStatus.LOCKED:
        raise HTTPException(403, "You are temporarily locked. Please try again later.")
    if status == OTPVerificationStatus.CODE_EXPIRED:
        raise HTTPException(400, "OTP has expired.")
    if status == OTPVerificationStatus.CODE_INVALID:
        raise HTTPException(400, "Invalid OTP.")
    if status == OTPVerificationStatus.MAX_ATTEMPTS:
        raise HTTPException(403, "Too many failed attempts. You are now locked.")
    if status == OTPVerificationStatus.NOT_FOUND:
        raise HTTPException(404, "OTP session not found.")

    raise HTTPException(500, "Unexpected error")
        


# Google login endpoint
@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = request.url_for('google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

# Google callback endpoint
@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(aget_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = await oauth.google.parse_id_token(request, token)

        # You can access: user_info['email'], user_info['name'], user_info['sub'] (unique ID), etc.

        # TODO: Create/find user in your DB
        # user = await your_user_crud.get_or_create_user(user_info['email'], db)

        return JSONResponse({
            "message": "Google authentication successful",
            "user": {
                "name": user_info.get("name"),
                "email": user_info.get("email"),
                "sub": user_info.get("sub")
            }
        })

    except Exception as e:
        raise HTTPException(status_code=400, detail="Google login failed")
    
# Create an Auth Me Route for the users

@router.get("/me")
async def get_current_user(request: Request, db: AsyncSession = Depends(aget_db)):
    token = request.cookies.get("auth_token")
    print("Raw token from cookies:", token)
    
    if not token:
        print("No token found in cookies")
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_jwt_token(token)
        user_id = int(payload.get("sub"))
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            print("No subject in payload")
            raise HTTPException(status_code=401, detail="Invalid token claims")
            
        return {
            "authenticated": True,
            "user_id": payload.get("sub"),
            "onboarding": payload.get("onboarding", False),
            "role": user.role.value,
            "is_active": user.is_active,
        }
        
    except jwt.ExpiredSignatureError:
        print("Token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        print(f"Invalid token: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")
    

# # get user with Profile Data 
# from sqlalchemy.future import select
# from sqlalchemy.orm import joinedload

# @router.get("/me/profile", response_model=CurrentUserResponse)
# async def get_current_user(request: Request, db: AsyncSession = Depends(aget_db)):
#     token = request.cookies.get("auth_token")
#     print("Raw token from cookies:", token)
    
#     if not token:
#         print("No token found in cookies")
#         raise HTTPException(status_code=401, detail="Not authenticated")

#     try:
#         payload = decode_jwt_token(token)
#         user_id = int(payload.get("sub"))

#         result = await db.execute(
#             select(User)
#             .options(joinedload(User.profile), joinedload(User.documents))
#             .where(User.id == user_id)
#         )
#         user = result.unique().scalar_one_or_none()

#         print("user is", user)
#         print("user preferred_verification:", user.preferred_verification if user else None)

#         if not user:
#             raise HTTPException(status_code=401, detail="Invalid token claims")

#         return CurrentUserResponse(
#             authenticated=True,
#             user=UserOut.model_validate(user),  # Changed from from_orm
#             profile=UserProfileOut.model_validate(user.profile) if user.profile else None,  # Changed from from_orm
#             documents=[UserDocumentOut.model_validate(doc) for doc in user.documents]  # Changed from from_orm
#         )

#     except jwt.ExpiredSignatureError:
#         print("Token expired")
#         raise HTTPException(status_code=401, detail="Token expired")
#     except jwt.InvalidTokenError as e:
#         print(f"Invalid token: {str(e)}")
#         raise HTTPException(status_code=401, detail="Invalid token")
#     except Exception as e:
#         print(f"Unexpected error: {str(e)}")
#         raise HTTPException(status_code=401, detail="Authentication failed")
    

# @router.post("/me/ghana-card", status_code=200)
# async def submit_ghana_card(
#     request: Request,
#     payload: GhanaCardInput,
#     db: AsyncSession = Depends(aget_db)
# ):
#     token = request.cookies.get("auth_token")
#     print("Token is", token)
#     if not token:
#         raise HTTPException(status_code=401, detail="Not authenticated")

#     try:
#         user_id = int(decode_jwt_token(token).get("sub"))
#     except Exception:
#         raise HTTPException(status_code=401, detail="Invalid token")

#     # Fetch user with existing profile
#     result = await db.execute(select(User).options(joinedload(User.profile)).where(User.id == user_id))
#     user = result.unique().scalar_one_or_none()

#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     if user.profile:
#         raise HTTPException(status_code=400, detail="Profile already exists")

#     # Create new profile
#     profile = UserProfile(user_id=user.id, ghana_card_number=payload.ghana_card_number)
#     db.add(profile)

#     # Update user status
#     user.is_active = True
#     user.verification_stage = VerificationStage.FULLY_VERIFIED

#     await db.commit()

#     return {"message": "Ghana card submitted successfully."}

    
# Simple but Powerful Logout
@router.post("/logout")
async def logout():
    response = JSONResponse({"message": "Logged out"})
    response.delete_cookie("auth_token")
    return response


# @router.get("/applicant-types", response_model=List[ApplicantTypeOut])
# async def get_applicant_types(db: AsyncSession = Depends(aget_db)):
#     result = await db.execute(select(ApplicantType).order_by(ApplicantType.name))
#     return result.scalars().all()