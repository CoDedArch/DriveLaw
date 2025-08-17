from sqlite3 import IntegrityError
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import aget_db
from app.core.security import decode_jwt_token
from sqlalchemy.orm import joinedload
from app.models.user import User, UserDocument
from app.core.constants import  UserRole, VerificationStage
from app.schemas.User import OnboardingData, StaffOnboardingRequest
from datetime import datetime

from app.utils.contact_utils import normalize_contact

router = APIRouter(
    prefix="/onboarding",
    tags=["onboarding"]
    )

class UserValidationError(Exception):
    def __init__(self, field: str, message: str, code: str = None):
        self.field = field
        self.message = message
        self.code = code
        super().__init__(message)

class DuplicateFieldError(UserValidationError):
    def __init__(self, field: str, value: str):
        message = f"The {field} '{value}' is already registered with another account"
        super().__init__(field, message, "DUPLICATE_FIELD")

# Helper function to check for existing records
async def check_unique_fields(db: AsyncSession, user_id: int, data: OnboardingData, user: User):
    """
    Check if any unique fields already exist for other users
    Returns a list of validation errors if duplicates are found
    """
    errors = []
    
    # Check email uniqueness (if being updated)
    if hasattr(data, 'email') and data.email:
        email_query = select(User).where(
            User.email == data.email,
            User.id != user_id
        )
        existing_email = await db.scalar(email_query)
        if existing_email:
            errors.append(DuplicateFieldError("email address", data.email))
    
    # Check phone uniqueness
    phone_to_check = None
    if hasattr(data, 'contact') and data.contact:
        phone_to_check = data.contact
    elif not user.phone and hasattr(data, 'contact'):
        phone_to_check = data.contact
    
    if phone_to_check:
        phone_query = select(User).where(
            User.phone == phone_to_check,
            User.id != user_id
        )
        existing_phone = await db.scalar(phone_query)
        if existing_phone:
            errors.append(DuplicateFieldError("phone number", phone_to_check))
    
    # Check alternative phone uniqueness (if provided)
    if hasattr(data, 'alt_contact') and data.alt_contact:
        alt_phone_query = select(User).where(
            User.alt_phone == data.alt_contact,
            User.id != user_id
        )
        existing_alt_phone = await db.scalar(alt_phone_query)
        if existing_alt_phone:
            errors.append(DuplicateFieldError("alternative phone number", data.alt_contact))
    
    # Check national ID uniqueness
    if hasattr(data, 'idnumber') and data.idnumber:
        id_query = select(User).where(
            User.national_id_number == data.idnumber,
            User.id != user_id
        )
        existing_id = await db.scalar(id_query)
        if existing_id:
            errors.append(DuplicateFieldError("national ID number", data.idnumber))
    
    return errors

# Enhanced endpoint with comprehensive error handling
@router.post("/user/onboarding/update-user")
async def complete_onboarding(
    data: OnboardingData,
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    token = request.cookies.get("auth_token")

    print("Token is", token)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = decode_jwt_token(token)
        user_id = int(payload.get("sub"))
        auth_method = payload.get("method")
        onboardingStatus = payload.get("onboarding")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not onboardingStatus:
        raise HTTPException(status_code=401, detail="You have already onboarded")

    # Check for unique field violations before updating
    try:
        validation_errors = await check_unique_fields(db, user_id, data, user)
        if validation_errors:
            error_details = []
            for error in validation_errors:
                error_details.append({
                    "field": error.field,
                    "message": error.message,
                    "code": error.code
                })
            
            raise HTTPException(
                status_code=409,  # Conflict status code for duplicate resources
                detail={
                    "message": "Registration failed due to duplicate information",
                    "errors": error_details
                }
            )
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        print(f"Error checking unique fields: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to validate user data")

    # Handle missing email/phone based on auth method
    if auth_method == "email" and not user.phone:
        user.phone = data.contact
    elif auth_method == "phone" and not user.email:
        user.email = data.email

    # Update user fields with frontend data
    user.first_name = data.firstname
    user.last_name = data.lastname
    user.gender = data.gender
    user.date_of_birth = data.dob
    user.nationality = data.nationality
    user.gps_address = data.gpsaddress
    user.region = data.region
    user.national_id_type = data.nationalid
    user.national_id_number = data.idnumber
    
    # Handle phone number
    if not user.phone:
        user.phone = data.contact
    
    # Set role based on frontend selection
    if data.role == "driver":
        user.role = UserRole.DRIVER
    elif data.role == "officer":
        user.role = UserRole.OFFICER
    elif data.role == "admin":
        user.role = UserRole.ADMIN
    
    # Update verification stage
    user.verification_stage = VerificationStage.DOCUMENT_PENDING
    user.is_active = False

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as e:
        await db.rollback()
        
        # Parse the IntegrityError to provide specific error messages
        error_message = str(e.orig)
        
        # Handle different database constraint violations
        if "email" in error_message.lower():
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Registration failed",
                    "errors": [{
                        "field": "email",
                        "message": "This email address is already registered",
                        "code": "DUPLICATE_EMAIL"
                    }]
                }
            )
        elif "phone" in error_message.lower():
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Registration failed",
                    "errors": [{
                        "field": "phone",
                        "message": "This phone number is already registered",
                        "code": "DUPLICATE_PHONE"
                    }]
                }
            )
        elif "national_id_number" in error_message.lower():
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Registration failed",
                    "errors": [{
                        "field": "national_id",
                        "message": "This national ID number is already registered",
                        "code": "DUPLICATE_NATIONAL_ID"
                    }]
                }
            )
        else:
            # Generic integrity error
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Registration failed due to duplicate information",
                    "errors": [{
                        "field": "unknown",
                        "message": "Some of the provided information is already registered",
                        "code": "DUPLICATE_FIELD"
                    }]
                }
            )
    except Exception as e:
        await db.rollback()
        print(f"Unexpected error during user update: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail={
                "message": "An unexpected error occurred during registration",
                "errors": [{
                    "field": "system",
                    "message": "Please try again later or contact support",
                    "code": "SYSTEM_ERROR"
                }]
            }
        )

    return {
        "message": "Onboarding completed successfully", 
        "user_id": user.id,
        "status": "success"
    }

# @router.post("/user/staff/onboarding")
# async def onboard_staff(
#     payload: StaffOnboardingRequest,
#     request: Request,
#     db: AsyncSession = Depends(aget_db),
# ):
#     # --- Step 1: Extract token and get user ---
#     token = request.cookies.get("auth_token")
#     if not token:
#         raise HTTPException(status_code=401, detail="Not authenticated")

#     try:
#         token_payload = decode_jwt_token(token)
#         user_id = int(token_payload.get("sub"))
#     except Exception:
#         raise HTTPException(status_code=401, detail="Invalid or expired token")

#     user = await db.get(User, user_id)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     # --- Step 2: Validate and update role ---
#     try:
#         new_role = UserRole(payload.role)
#     except ValueError:
#         raise HTTPException(status_code=400, detail="Invalid role specified")

#     user.role = new_role
#     user.is_active = True

#     # --- Step 3: Get or create user profile ---
#     result = await db.execute(
#         select(UserProfile).where(UserProfile.user_id == user.id)
#     )
#     profile = result.scalar_one_or_none()

#     if not profile:
#         profile = UserProfile(user_id=user.id)
#         db.add(profile)

#     profile.specialization = payload.specialization
#     profile.work_email = payload.work_email
#     profile.staff_number = payload.staff_number
#     profile.designation = payload.designation

#     # --- Step 4: Reassign Department and MMDA ---
#     # Remove old DepartmentStaff entries from other MMDAs
#     existing_staff = await db.execute(
#         select(DepartmentStaff)
#         .join(Department)
#         .options(joinedload(DepartmentStaff.department))
#         .filter(DepartmentStaff.user_id == user.id)
#     )
#     for staff_record in existing_staff.scalars():
#         if staff_record.department.mmda_id != payload.mmda_id:
#             await db.delete(staff_record)

#     # Ensure department belongs to the provided MMDA
#     department = await db.get(Department, payload.department_id)
#     if not department or department.mmda_id != payload.mmda_id:
#         raise HTTPException(status_code=400, detail="Department does not belong to the selected MMDA")

#     # Create or update DepartmentStaff
#     result = await db.execute(
#         select(DepartmentStaff).where(
#             DepartmentStaff.user_id == user.id,
#             DepartmentStaff.department_id == payload.department_id
#         )
#     )
#     dept_staff = result.scalar_one_or_none()

#     if not dept_staff:
#         dept_staff = DepartmentStaff(
#             department_id=payload.department_id,
#             user_id=user.id,
#             position=payload.designation or "Officer"
#         )
#         db.add(dept_staff)
#     else:
#         dept_staff.position = payload.designation or dept_staff.position

#     await db.flush()  # Ensure we have dept_staff.id for committee assignment

#     # --- Step 5: Reassign Committees if needed ---
#     # Remove committee memberships from other MMDAs
#     existing_committees = await db.execute(
#         select(CommitteeMember)
#         .join(Committee)
#         .options(joinedload(CommitteeMember.committee))
#         .filter(CommitteeMember.staff_id == dept_staff.id)  # Changed to filter by staff_id
#     )
#     for committee_member in existing_committees.scalars():
#         if committee_member.committee.mmda_id != payload.mmda_id:
#             await db.delete(committee_member)

#     # Ensure committee belongs to provided MMDA
#     committee = await db.get(Committee, payload.committee_id)
#     if not committee or committee.mmda_id != payload.mmda_id:
#         raise HTTPException(status_code=400, detail="Committee does not belong to the selected MMDA")

#     # Create or update CommitteeMember
#     result = await db.execute(
#         select(CommitteeMember).where(
#             CommitteeMember.staff_id == dept_staff.id,  # Changed to use staff_id
#             CommitteeMember.committee_id == payload.committee_id
#         )
#     )
#     committee_member = result.scalar_one_or_none()

#     if not committee_member:
#         committee_member = CommitteeMember(
#             committee_id=payload.committee_id,
#             staff_id=dept_staff.id,  # Using staff_id instead of user_id
#             role=payload.role.replace("_", " ").title()
#         )
#         db.add(committee_member)
#     else:
#         committee_member.role = payload.role.replace("_", " ").title()

#     await db.commit()

#     return {"message": "User onboarding completed successfully"}