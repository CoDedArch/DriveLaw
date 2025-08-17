
# Router endpoint (add to your notifications router)
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from app.models.notification import Notification
from app.core.database import aget_db
from app.core.security import decode_jwt_token
from app.schemas.Notifications import MarkAsReadRequest, NotificationOut, NotificationsListResponse

router = APIRouter(prefix="/notifications",
    tags=["notifications"])

@router.get("/notifications", response_model=NotificationsListResponse)
async def get_user_notifications(
    request: Request,
    db: AsyncSession = Depends(aget_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False)
):
    """Get notifications for the current user with pagination"""
    
    # 1. Decode JWT token from cookie
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_jwt_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 2. Build base query
    query = select(Notification).where(Notification.recipient_id == user_id)
    
    if unread_only:
        query = query.where(Notification.is_read == False)
    
    # Order by creation date (newest first)
    query = query.order_by(Notification.created_at.desc())
    
    # 3. Get total count for pagination
    count_query = select(func.count(Notification.id)).where(Notification.recipient_id == user_id)
    if unread_only:
        count_query = count_query.where(Notification.is_read == False)
    
    total_count_result = await db.execute(count_query)
    total_count = total_count_result.scalar()
    
    # 4. Get unread count
    unread_count_query = select(func.count(Notification.id)).where(
        Notification.recipient_id == user_id,
        Notification.is_read == False
    )
    unread_count_result = await db.execute(unread_count_query)
    unread_count = unread_count_result.scalar()

    # 5. Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    
    # 6. Execute query
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return NotificationsListResponse(
        notifications=notifications,
        total_count=total_count,
        unread_count=unread_count
    )

@router.patch("/notifications/mark-read")
async def mark_notifications_as_read(
    data: MarkAsReadRequest,
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Mark specific notifications as read"""
    
    # 1. Decode JWT token from cookie
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_jwt_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 2. Update notifications
    stmt = (
        update(Notification)
        .where(
            Notification.id.in_(data.notification_ids),
            Notification.recipient_id == user_id,  # Security: only user's own notifications
            Notification.is_read == False  # Only update unread notifications
        )
        .values(
            is_read=True,
            read_at=datetime.utcnow()
        )
    )
    
    result = await db.execute(stmt)
    await db.commit()
    
    return {"message": f"Marked {result.rowcount} notifications as read"}

@router.patch("/notifications/mark-all-read")
async def mark_all_notifications_as_read(
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Mark all user's notifications as read"""
    
    # 1. Decode JWT token from cookie
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_jwt_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 2. Update all unread notifications
    stmt = (
        update(Notification)
        .where(
            Notification.recipient_id == user_id,
            Notification.is_read == False
        )
        .values(
            is_read=True,
            read_at=datetime.utcnow()
        )
    )
    
    result = await db.execute(stmt)
    await db.commit()
    
    return {"message": f"Marked {result.rowcount} notifications as read"}

@router.get("/notifications/{notification_id}", response_model=NotificationOut)
async def get_single_notification(
    notification_id: int,
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Get a specific notification by ID"""
    
    # 1. Decode JWT token from cookie
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_jwt_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 2. Get the notification
    query = select(Notification).where(
        Notification.id == notification_id,
        Notification.recipient_id == user_id  # Security: only user's own notifications
    )
    
    result = await db.execute(query)
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # 3. Mark as read if not already read
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        await db.commit()
    
    return notification