# app/api/routes/uploads.py

import traceback
from fastapi import APIRouter, Depends, Form, Request, UploadFile, File, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.constants import UserRole
from app.core.database import aget_db
from app.core.security import decode_jwt_token
from app.models.user import User
from app.services.s3_uploadService import upload_file_to_s3
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/uploads", tags=["uploads"])

@router.post("/user-documents")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(aget_db),
):
    # 🔐 Extract token from cookie
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_jwt_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # 🔍 Get user from DB
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 📤 Upload to S3 with user-named folder
    try:
        url = upload_file_to_s3(
            file,
            folder="uploads/user_documents/ghanacards",
            username=user.first_name or user.email
        )
        return {"file_url": url}
    except Exception as e:
        print("UPLOAD ERROR:", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/application-documents")
async def upload_application_document(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(aget_db)
):
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_jwt_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        url = upload_file_to_s3(
            file,
            folder="uploads/application_documents",
            username=user.first_name or user.email
        )
        return {"file_url": url}
    except Exception as e:
        print("UPLOAD ERROR:", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
# @router.post("/inspection-photos")
# async def upload_inspection_photo(
#     request: Request,
#     file: UploadFile = File(...),
#     inspection_id: str = Form(...),
#     db: AsyncSession = Depends(aget_db)
# ):
#     token = request.cookies.get("auth_token")
#     if not token:
#         raise HTTPException(status_code=401, detail="Not authenticated")

#     try:
#         payload = decode_jwt_token(token)
#         user_id = int(payload.get("sub"))
#     except Exception:
#         raise HTTPException(status_code=401, detail="Invalid or expired token")

#     user = await db.get(User, user_id)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     # # Verify inspection exists
#     # inspection = await db.get(Inspection, int(inspection_id))
#     # if not inspection:
#     #     raise HTTPException(status_code=404, detail="Inspection not found")

#     try:
#         # Upload to S3
#         url = upload_file_to_s3(
#             file,
#             folder="uploads/inspection_photos",
#             username=user.first_name or user.email
#         )

#         # Create photo record in database
#         photo = InspectionPhoto(
#             inspection_id=int(inspection_id),
#             file_path=url,
#             uploaded_by_id=user_id
#         )
#         db.add(photo)
#         await db.commit()

#         return {"file_url": url}
#     except Exception as e:
#         await db.rollback()
#         print("UPLOAD ERROR:", traceback.format_exc())
#         raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# @router.delete("/inspection-photos/{photo_id}")
# async def delete_inspection_photo(
#     photo_id: int,
#     request: Request,
#     db: AsyncSession = Depends(aget_db)
# ):
#     # Verify authentication
#     token = request.cookies.get("auth_token")
#     if not token:
#         raise HTTPException(status_code=401, detail="Not authenticated")

#     try:
#         # Decode token to get user ID
#         payload = decode_jwt_token(token)
#         user_id = int(payload.get("sub"))

#         # Get user role from database
#         user_result = await db.execute(
#             select(User.role).where(User.id == user_id)
#         )
#         user_role = user_result.scalar_one_or_none()

#         if user_role != UserRole.INSPECTION_OFFICER:
#             raise HTTPException(
#                 status_code=403,
#                 detail="Only inspection officers can delete photos"
#             )

#         # Get the photo with uploader information
#         photo_result = await db.execute(
#             select(InspectionPhoto)
#             .options(selectinload(InspectionPhoto.uploaded_by))
#             .where(InspectionPhoto.id == photo_id)
#         )
#         photo = photo_result.scalar_one_or_none()

#         if not photo:
#             raise HTTPException(status_code=404, detail="Photo not found")

#         # Verify permission (uploader or admin)
#         if photo.uploaded_by.id != user_id and user_role != UserRole.ADMIN:
#             raise HTTPException(
#                 status_code=403,
#                 detail="You can only delete your own photos"
#             )

#         # Delete from database
#         await db.delete(photo)
#         await db.commit()

#         # Optional: Delete from storage
#         # if photo.file_path:
#         #     await delete_file_from_storage(photo.file_path)

#         return {"message": "Photo deleted successfully"}

#     except HTTPException:
#         raise
#     except Exception as e:
#         await db.rollback()
#         raise HTTPException(
#             status_code=500,
#             detail=f"Error deleting photo: {str(e)}"
#         )