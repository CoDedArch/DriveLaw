# app/api/driver_routes.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional
from datetime import datetime, timedelta
from app.core.database import aget_db
from app.models.appeals import OffenseAppeal, OffenseStatistics
from app.models.offenses import TrafficOffense
from app.models.payment import Payment
from app.models.user import User
from app.core.security import decode_jwt_token, get_current_user
from app.core.constants import OffenseStatus, AppealStatus, PaymentStatus
from pydantic import BaseModel

from app.schemas.appeal import AppealResponse
from app.schemas.dashboard import DashboardData, DashboardResponse
from app.schemas.offense import OffenseResponse
from app.schemas.payment import PaymentResponse

router = APIRouter(prefix="/driver", tags=["driver"])

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard_data(
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Get dashboard overview data"""
    user = await get_current_user(request, db)
    
    # Get user statistics
    stats_query = select(OffenseStatistics).where(OffenseStatistics.user_id == user.id)
    stats_result = await db.execute(stats_query)
    stats = stats_result.scalar_one_or_none()
    
    # Get recent offenses (last 5)
    offenses_query = (
        select(TrafficOffense)
        .where(TrafficOffense.user_id == user.id)
        .order_by(desc(TrafficOffense.offense_date))
        .limit(5)
    )
    offenses_result = await db.execute(offenses_query)
    offenses = offenses_result.scalars().all()
    
    # Calculate pending amount
    pending_query = (
        select(func.sum(TrafficOffense.fine_amount))
        .where(
            and_(
                TrafficOffense.user_id == user.id,
                TrafficOffense.status == OffenseStatus.UNPAID
            )
        )
    )
    pending_result = await db.execute(pending_query)
    pending_amount = pending_result.scalar() or 0.0
    
    # Format response
    driver_data = DashboardData(
        name=f"{user.first_name} {user.last_name}",
        license=user.national_id_number or "N/A",
        totalOffenses=stats.total_offenses if stats else 0,
        totalFines=stats.total_fines_amount if stats else 0.0,
        pendingAppeals=stats.pending_appeals if stats else 0,
        drivingScore=stats.driving_score if stats else 100
    )
    
    recent_offenses = [
        OffenseResponse(
            id=offense.offense_number,
            date=offense.offense_date.strftime("%Y-%m-%d"),
            time=offense.offense_time,
            type=offense.offense_type.value,
            location=offense.location,
            fine=offense.fine_amount,
            status=offense.status.value,
            description=offense.description or "",
            evidence=offense.evidence_urls[0] if offense.evidence_urls else "",
            dueDate=offense.due_date.strftime("%Y-%m-%d"),
            severity=offense.severity.value
        )
        for offense in offenses
    ]
    
    return DashboardResponse(
        driverData=driver_data,
        recentOffenses=recent_offenses,
        pendingAmount=pending_amount
    )

@router.get("/offenses", response_model=List[OffenseResponse])
async def get_user_offenses(
    request: Request,
    db: AsyncSession = Depends(aget_db),
    status: Optional[str] = None,
    offense_type: Optional[str] = None
):
    """Get all user offenses with optional filtering"""
    user = await get_current_user(request, db)
    
    query = select(TrafficOffense).where(TrafficOffense.user_id == user.id)
    
    # Apply filters
    if status:
        try:
            status_enum = OffenseStatus(status.upper())
            query = query.where(TrafficOffense.status == status_enum)
        except ValueError:
            pass
    
    if offense_type:
        try:
            # Convert offense_type string to enum if needed
            query = query.where(TrafficOffense.offense_type.ilike(f"%{offense_type}%"))
        except:
            pass
    
    query = query.order_by(desc(TrafficOffense.offense_date))
    
    result = await db.execute(query)
    offenses = result.scalars().all()
    
    return [
        OffenseResponse(
            id=offense.offense_number,
            date=offense.offense_date.strftime("%Y-%m-%d"),
            time=offense.offense_time,
            type=offense.offense_type.value,
            location=offense.location,
            fine=offense.fine_amount,
            status=offense.status.value,
            description=offense.description or "",
            evidence=offense.evidence_urls[0] if offense.evidence_urls else "",
            dueDate=offense.due_date.strftime("%Y-%m-%d"),
            severity=offense.severity.value
        )
        for offense in offenses
    ]

@router.get("/payments", response_model=List[PaymentResponse])
async def get_payment_history(
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Get user's payment history"""
    user = await get_current_user(request, db)
    
    # Get payments with offense details
    query = (
        select(Payment, TrafficOffense)
        .join(TrafficOffense, Payment.offense_id == TrafficOffense.id, isouter=True)
        .where(Payment.user_id == user.id)
        .where(Payment.status == PaymentStatus.COMPLETED)
        .order_by(desc(Payment.payment_date))
    )
    
    result = await db.execute(query)
    payments_with_offenses = result.all()
    
    return [
        PaymentResponse(
            id=payment.transaction_reference or f"PAY{payment.id:03d}",
            date=payment.payment_date.strftime("%Y-%m-%d") if payment.payment_date else "",
            amount=payment.amount,
            type=offense.offense_type.value if offense else "General Payment",
            status=payment.status.value,
            offenseId=offense.offense_number if offense else "",
            method=payment.method.value if payment.method else "Unknown",
            location=offense.location if offense else None
        )
        for payment, offense in payments_with_offenses
    ]

@router.get("/appeals", response_model=List[AppealResponse])
async def get_user_appeals(
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Get user's appeals with offense details"""
    user = await get_current_user(request, db)
    
    query = (
        select(OffenseAppeal, TrafficOffense)
        .join(TrafficOffense, OffenseAppeal.offense_id == TrafficOffense.id)
        .where(OffenseAppeal.user_id == user.id)
        .order_by(desc(OffenseAppeal.submission_date))
    )
    
    result = await db.execute(query)
    appeals_with_offenses = result.all()
    
    return [
        AppealResponse(
            id=appeal.appeal_number,
            offenseId=offense.offense_number,
            offenseType=offense.offense_type.value,
            location=offense.location,
            submissionDate=appeal.submission_date.strftime("%Y-%m-%d"),
            status=appeal.status.value,
            reason=appeal.reason.value,
            description=appeal.description,
            responseDate=appeal.response_date.strftime("%Y-%m-%d") if appeal.response_date else None,
            reviewerNotes=appeal.reviewer_notes
        )
        for appeal, offense in appeals_with_offenses
    ]

# Payment Summary endpoint
@router.get("/payment-summary")
async def get_payment_summary(
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Get payment overview summary"""
    user = await get_current_user(request, db)
    
    # Outstanding fines
    outstanding_query = (
        select(func.sum(TrafficOffense.fine_amount), func.count(TrafficOffense.id))
        .where(
            and_(
                TrafficOffense.user_id == user.id,
                TrafficOffense.status == OffenseStatus.UNPAID
            )
        )
    )
    outstanding_result = await db.execute(outstanding_query)
    outstanding_amount, outstanding_count = outstanding_result.first()
    
    # This month's fines (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    monthly_query = (
        select(func.sum(TrafficOffense.fine_amount), func.count(TrafficOffense.id))
        .where(
            and_(
                TrafficOffense.user_id == user.id,
                TrafficOffense.offense_date >= thirty_days_ago
            )
        )
    )
    monthly_result = await db.execute(monthly_query)
    monthly_amount, monthly_count = monthly_result.first()
    
    # Total paid amount
    paid_query = (
        select(func.sum(Payment.amount), func.count(Payment.id))
        .where(
            and_(
                Payment.user_id == user.id,
                Payment.status == PaymentStatus.COMPLETED
            )
        )
    )
    paid_result = await db.execute(paid_query)
    paid_amount, paid_count = paid_result.first()
    
    return {
        "outstandingAmount": outstanding_amount or 0.0,
        "outstandingCount": outstanding_count or 0,
        "thisMonthAmount": monthly_amount or 0.0,
        "thisMonthCount": monthly_count or 0,
        "totalPaidAmount": paid_amount or 0.0,
        "totalPaidCount": paid_count or 0
    }

# Single offense details
@router.get("/offenses/{offense_id}", response_model=OffenseResponse)
async def get_offense_details(
    offense_id: str,
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Get detailed information about a specific offense"""
    user = await get_current_user(request, db)
    
    query = (
        select(TrafficOffense)
        .where(
            and_(
                TrafficOffense.offense_number == offense_id,
                TrafficOffense.user_id == user.id
            )
        )
    )
    
    result = await db.execute(query)
    offense = result.scalar_one_or_none()
    
    if not offense:
        raise HTTPException(status_code=404, detail="Offense not found")
    
    return OffenseResponse(
        id=offense.offense_number,
        date=offense.offense_date.strftime("%Y-%m-%d"),
        time=offense.offense_time,
        type=offense.offense_type.value,
        location=offense.location,
        fine=offense.fine_amount,
        status=offense.status.value,
        description=offense.description or "",
        evidence=offense.evidence_urls[0] if offense.evidence_urls else "",
        dueDate=offense.due_date.strftime("%Y-%m-%d"),
        severity=offense.severity.value
    )