from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import String, select, func, and_, or_
from typing import List, Optional
from app.core.database import aget_db
from app.models.user import User
from app.models.offenses import TrafficOffense
from app.models.payment import Payment
from app.models.appeals import OffenseAppeal, OffenseStatistics
from app.core.security import get_current_user
from app.core.constants import UserRole, OffenseStatus, PaymentStatus, AppealStatus, OffenseType
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import desc, asc

router = APIRouter(prefix="/officer", tags=["officer"])

# Response Models
class UserSummary(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    national_id_number: Optional[str]
    total_offenses: int
    total_fines: float
    pending_appeals: int
    driving_score: int

class DashboardAnalyticsResponse(BaseModel):
    total_users: int
    total_offenses: int
    total_fines_amount: float
    total_paid_amount: float
    pending_appeals: int
    active_users: int

class OffenseResponse(BaseModel):
    id: str
    user_id: int
    user_name: str
    offense_number: str
    offense_type: str
    offense_date: str
    location: str
    fine_amount: float
    status: str
    severity: str

class PaymentResponse(BaseModel):
    id: str
    user_id: int
    user_name: str
    amount: float
    payment_date: Optional[str]
    status: str
    offense_number: Optional[str]
    method: Optional[str]

class AppealResponse(BaseModel):
    id: str
    user_id: int
    user_name: str
    offense_number: str
    appeal_number: str
    reason: str
    status: str
    submission_date: str

class AppealDetailResponse(BaseModel):
    id: str
    user_id: int
    user_name: str
    offense_number: str
    appeal_number: str
    reason: str
    description: str
    status: str
    submission_date: str
    response_date: Optional[str]
    reviewer_notes: Optional[str]
    supporting_documents: Optional[List[str]]
    reviewer_id: Optional[int]

class OffenseDetailResponse(BaseModel):
    id: str
    user_id: int
    user_name: str
    offense_number: str
    offense_type: str
    offense_date: str
    offense_time: str
    location: str
    fine_amount: float
    status: str
    severity: str
    description: Optional[str]
    evidence_urls: Optional[List[str]]
    due_date: str
    vehicle_registration: Optional[str]
    officer_id: Optional[str]
    points: int

class UserFullRecordsResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    other_name: Optional[str]
    email: str
    national_id_number: Optional[str]
    phone: Optional[str]
    alt_phone: Optional[str]
    address: Optional[str]
    gps_address: Optional[str]
    gender: Optional[str]
    date_of_birth: Optional[str]
    nationality: Optional[str]
    national_id_type: Optional[str]
    region: Optional[str]
    is_active: bool
    preferred_verification: Optional[str]
    role: str
    verification_stage: str
    total_offenses: int
    total_fines: float
    pending_appeals: int
    successful_appeals: int
    driving_score: int
    offenses: List[OffenseResponse]
    payments: List[PaymentResponse]
    appeals: List[AppealResponse]

class AppealDecisionRequest(BaseModel):
    status: str
    reviewer_notes: Optional[str]

# Helper function to verify officer role
async def verify_officer(request: Request, db: AsyncSession = Depends(aget_db)):
    user = await get_current_user(request, db)
    if user.role != UserRole.OFFICER:
        raise HTTPException(status_code=403, detail="User is not authorized as an officer")
    return user

@router.get("/dashboard", response_model=DashboardAnalyticsResponse)
async def get_dashboard_analytics(
    request: Request,
    db: AsyncSession = Depends(aget_db),
    officer: User = Depends(verify_officer)
):
    """Get aggregated analytics for all users"""
    total_users_query = select(func.count(User.id))
    total_users_result = await db.execute(total_users_query)
    total_users = total_users_result.scalar()

    active_users_query = select(func.count(User.id)).where(User.is_active == True)
    active_users_result = await db.execute(active_users_query)
    active_users = active_users_result.scalar()

    total_offenses_query = select(func.count(TrafficOffense.id))
    total_offenses_result = await db.execute(total_offenses_query)
    total_offenses = total_offenses_result.scalar()

    total_fines_query = select(func.sum(TrafficOffense.fine_amount))
    total_fines_result = await db.execute(total_fines_query)
    total_fines = total_fines_result.scalar() or 0.0

    total_paid_query = select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.COMPLETED)
    total_paid_result = await db.execute(total_paid_query)
    total_paid = total_paid_result.scalar() or 0.0

    pending_appeals_query = select(func.count(OffenseAppeal.id)).where(OffenseAppeal.status == AppealStatus.UNDER_REVIEW)
    pending_appeals_result = await db.execute(pending_appeals_query)
    pending_appeals = pending_appeals_result.scalar()

    return DashboardAnalyticsResponse(
        total_users=total_users,
        total_offenses=total_offenses,
        total_fines_amount=total_fines,
        total_paid_amount=total_paid,
        pending_appeals=pending_appeals,
        active_users=active_users
    )

@router.get("/users", response_model=List[UserSummary])
async def get_all_users(
    request: Request,
    db: AsyncSession = Depends(aget_db),
    officer: User = Depends(verify_officer),
    email: Optional[str] = None,
    sort_by: Optional[str] = "id",
    sort_order: Optional[str] = "asc",
    limit: int = 100,
    offset: int = 0
):
    """Get all users with filtering and sorting"""
    query = select(User, OffenseStatistics).join(OffenseStatistics, User.id == OffenseStatistics.user_id, isouter=True)

    if email:
        query = query.where(User.email.ilike(f"%{email}%"))

    sort_column = {
        "id": User.id,
        "email": User.email,
        "name": User.first_name,
        "total_offenses": OffenseStatistics.total_offenses,
        "driving_score": OffenseStatistics.driving_score
    }.get(sort_by, User.id)
    query = query.order_by(asc(sort_column) if sort_order == "asc" else desc(sort_column))

    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    users_with_stats = result.all()

    return [
        UserSummary(
            id=user.id,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            email=user.email or "",
            national_id_number=user.national_id_number or None,
            total_offenses=stats.total_offenses if stats else 0,
            total_fines=stats.total_fines_amount if stats else 0.0,
            pending_appeals=stats.pending_appeals if stats else 0,
            driving_score=stats.driving_score if stats else 100
        )
        for user, stats in users_with_stats
    ]

@router.get("/offenses", response_model=List[OffenseResponse])
async def get_all_offenses(
    request: Request,
    db: AsyncSession = Depends(aget_db),
    status: Optional[str] = None,
    offense_type: Optional[str] = None,
    severity: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = "offense_date",
    sort_order: Optional[str] = "desc",
    limit: int = 100,
    offset: int = 0
):
    """Get all traffic offenses across all users with filtering and sorting"""
    query = select(TrafficOffense, User).join(User, TrafficOffense.user_id == User.id)

    # Status filter
    if status:
        try:
            status_enum = OffenseStatus(status.upper())
            query = query.where(TrafficOffense.status == status_enum)
        except ValueError:
            pass  # Ignore invalid status values

    # Offense type filter
    if offense_type:
        query = query.where(TrafficOffense.offense_type.ilike(f"%{offense_type}%"))

    # Severity filter (cast to TEXT to support ILIKE)
    if severity:
        query = query.where(func.cast(TrafficOffense.severity, String).ilike(f"%{severity}%"))

    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                TrafficOffense.offense_number.ilike(search_term),
                TrafficOffense.location.ilike(search_term),
                TrafficOffense.vehicle_registration.ilike(search_term),
                func.concat(User.first_name, ' ', User.last_name).ilike(search_term),
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term)
            )
        )

    # Sorting
    sort_column = {
        "offense_date": TrafficOffense.offense_date,
        "fine_amount": TrafficOffense.fine_amount,
        "user_id": TrafficOffense.user_id,
        "severity": TrafficOffense.severity
    }.get(sort_by, TrafficOffense.offense_date)
    query = query.order_by(asc(sort_column) if sort_order == "asc" else desc(sort_column))

    # Pagination
    query = query.limit(limit).offset(offset)

    # Execute query
    result = await db.execute(query)
    offenses_with_users = result.all()

    # Return response
    return [
        OffenseResponse(
            id=offense.offense_number,
            user_id=user.id,
            user_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
            offense_number=offense.offense_number,
            offense_type=offense.offense_type.value if hasattr(offense.offense_type, 'value') else offense.offense_type,
            offense_date=offense.offense_date.strftime("%Y-%m-%d"),
            location=offense.location,
            fine_amount=offense.fine_amount,
            status=offense.status.value if hasattr(offense.status, 'value') else offense.status,
            severity=offense.severity.value if hasattr(offense.severity, 'value') else offense.severity,
            vehicle_registration=offense.vehicle_registration,
            description=offense.description,
            due_date=offense.due_date.strftime("%Y-%m-%d") if offense.due_date else None,
        )
        for offense, user in offenses_with_users
    ]


@router.get("/payments", response_model=List[PaymentResponse])
async def get_all_payments(
    request: Request,
    db: AsyncSession = Depends(aget_db),
    officer: User = Depends(verify_officer),
    status: Optional[str] = None,
    sort_by: Optional[str] = "payment_date",
    sort_order: Optional[str] = "desc",
    limit: int = 100,
    offset: int = 0
):
    """Get all payment history across all users with filtering and sorting"""
    query = (
        select(Payment, User, TrafficOffense)
        .join(User, Payment.user_id == User.id)
        .join(TrafficOffense, Payment.offense_id == TrafficOffense.id, isouter=True)
    )

    if status:
        try:
            status_enum = PaymentStatus(status.upper())
            query = query.where(Payment.status == status_enum)
        except ValueError:
            pass

    sort_column = {
        "payment_date": Payment.payment_date,
        "amount": Payment.amount,
        "user_id": Payment.user_id
    }.get(sort_by, Payment.payment_date)
    query = query.order_by(asc(sort_column) if sort_order == "asc" else desc(sort_column))

    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    payments_with_users = result.all()

    return [
        PaymentResponse(
            id=payment.transaction_reference or f"PAY{payment.id:03d}",
            user_id=user.id,
            user_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
            amount=payment.amount,
            payment_date=payment.payment_date.strftime("%Y-%m-%d") if payment.payment_date else None,
            status=payment.status.value,
            offense_number=offense.offense_number if offense else None,
            method=payment.method.value if payment.method else None
        )
        for payment, user, offense in payments_with_users
    ]

@router.get("/appeals", response_model=List[AppealResponse])
async def get_all_appeals(
    request: Request,
    db: AsyncSession = Depends(aget_db),
    officer: User = Depends(verify_officer),
    status: Optional[str] = None,
    sort_by: Optional[str] = "submission_date",
    sort_order: Optional[str] = "desc",
    limit: int = 100,
    offset: int = 0
):
    """Get all appeals across all users with filtering and sorting"""
    query = (
        select(OffenseAppeal, User, TrafficOffense)
        .join(User, OffenseAppeal.user_id == User.id)
        .join(TrafficOffense, OffenseAppeal.offense_id == TrafficOffense.id)
    )

    if status:
        try:
            status_enum = AppealStatus(status.upper())
            query = query.where(OffenseAppeal.status == status_enum)
        except ValueError:
            pass

    sort_column = {
        "submission_date": OffenseAppeal.submission_date,
        "user_id": OffenseAppeal.user_id,
        "status": OffenseAppeal.status
    }.get(sort_by, OffenseAppeal.submission_date)
    query = query.order_by(asc(sort_column) if sort_order == "asc" else desc(sort_column))

    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    appeals_with_users = result.all()

    return [
        AppealResponse(
            id=appeal.appeal_number,
            user_id=user.id,
            user_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
            offense_number=offense.offense_number,
            appeal_number=appeal.appeal_number,
            reason=appeal.reason.value,
            status=appeal.status.value,
            submission_date=appeal.submission_date.strftime("%Y-%m-%d")
        )
        for appeal, user, offense in appeals_with_users
    ]

@router.get("/appeals/{appeal_number}", response_model=AppealDetailResponse)
async def get_appeal_details(
    appeal_number: str,
    request: Request,
    db: AsyncSession = Depends(aget_db),
    officer: User = Depends(verify_officer)
):
    """Get detailed information about a specific appeal"""
    query = (
        select(OffenseAppeal, User, TrafficOffense)
        .join(User, OffenseAppeal.user_id == User.id)
        .join(TrafficOffense, OffenseAppeal.offense_id == TrafficOffense.id)
        .where(OffenseAppeal.appeal_number == appeal_number)
    )
    
    result = await db.execute(query)
    appeal_data = result.first()
    
    if not appeal_data:
        raise HTTPException(status_code=404, detail="Appeal not found")
    
    appeal, user, offense = appeal_data
    
    return AppealDetailResponse(
        id=appeal.appeal_number,
        user_id=user.id,
        user_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
        offense_number=offense.offense_number,
        appeal_number=appeal.appeal_number,
        reason=appeal.reason.value,
        description=appeal.description,
        status=appeal.status.value,
        submission_date=appeal.submission_date.strftime("%Y-%m-%d"),
        response_date=appeal.response_date.strftime("%Y-%m-%d") if appeal.response_date else None,
        reviewer_notes=appeal.reviewer_notes,
        supporting_documents=appeal.supporting_documents or [],
        reviewer_id=appeal.reviewer_id
    )

@router.get("/offenses/{offense_number}", response_model=OffenseDetailResponse)
async def get_offense_details(
    offense_number: str,
    request: Request,
    db: AsyncSession = Depends(aget_db),
    officer: User = Depends(verify_officer)
):
    """Get detailed information about a specific offense"""
    query = (
        select(TrafficOffense, User)
        .join(User, TrafficOffense.user_id == User.id)
        .where(TrafficOffense.offense_number == offense_number)
    )
    
    result = await db.execute(query)
    offense_data = result.first()
    
    if not offense_data:
        raise HTTPException(status_code=404, detail="Offense not found")
    
    offense, user = offense_data
    
    return OffenseDetailResponse(
        id=offense.offense_number,
        user_id=user.id,
        user_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
        offense_number=offense.offense_number,
        offense_type=offense.offense_type.value,
        offense_date=offense.offense_date.strftime("%Y-%m-%d"),
        offense_time=offense.offense_time,
        location=offense.location,
        fine_amount=offense.fine_amount,
        status=offense.status.value,
        severity=offense.severity.value,
        description=offense.description,
        evidence_urls=offense.evidence_urls or [],
        due_date=offense.due_date.strftime("%Y-%m-%d"),
        vehicle_registration=offense.vehicle_registration,
        officer_id=offense.officer_id,
        points=offense.points
    )

@router.get("/users/{user_id}", response_model=UserFullRecordsResponse)
async def get_user_full_records(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(aget_db),
    officer: User = Depends(verify_officer)
):
    """Get full records for a single user"""
    user_query = (
        select(User, OffenseStatistics)
        .join(OffenseStatistics, User.id == OffenseStatistics.user_id, isouter=True)
        .where(User.id == user_id)
    )
    user_result = await db.execute(user_query)
    user_data = user_result.first()
    
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    
    user, stats = user_data
    
    offenses_query = (
        select(TrafficOffense)
        .where(TrafficOffense.user_id == user_id)
        .order_by(desc(TrafficOffense.offense_date))
    )
    offenses_result = await db.execute(offenses_query)
    offenses = offenses_result.scalars().all()
    
    payments_query = (
        select(Payment, TrafficOffense)
        .join(TrafficOffense, Payment.offense_id == TrafficOffense.id, isouter=True)
        .where(Payment.user_id == user_id)
        .order_by(desc(Payment.payment_date))
    )
    payments_result = await db.execute(payments_query)
    payments = payments_result.all()
    
    appeals_query = (
        select(OffenseAppeal, TrafficOffense)
        .join(TrafficOffense, OffenseAppeal.offense_id == TrafficOffense.id)
        .where(OffenseAppeal.user_id == user_id)
        .order_by(desc(OffenseAppeal.submission_date))
    )
    appeals_result = await db.execute(appeals_query)
    appeals = appeals_result.all()
    
    return UserFullRecordsResponse(
        id=user.id,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        other_name=user.other_name,
        email=user.email or "",
        national_id_number=user.national_id_number,
        phone=user.phone,
        alt_phone=user.alt_phone,
        address=user.address,
        gps_address=user.gps_address,
        gender=user.gender,
        date_of_birth=user.date_of_birth.strftime("%Y-%m-%d") if user.date_of_birth else None,
        nationality=user.nationality,
        national_id_type=user.national_id_type,
        region=user.region,
        is_active=user.is_active,
        preferred_verification=user.preferred_verification,
        role=user.role.value,
        verification_stage=user.verification_stage.value,
        total_offenses=stats.total_offenses if stats else 0,
        total_fines=stats.total_fines_amount if stats else 0.0,
        pending_appeals=stats.pending_appeals if stats else 0,
        successful_appeals=stats.successful_appeals if stats else 0,
        driving_score=stats.driving_score if stats else 100,
        offenses=[
            OffenseResponse(
                id=offense.offense_number,
                user_id=user.id,
                user_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
                offense_number=offense.offense_number,
                offense_type=offense.offense_type.value,
                offense_date=offense.offense_date.strftime("%Y-%m-%d"),
                location=offense.location,
                fine_amount=offense.fine_amount,
                status=offense.status.value,
                severity=offense.severity.value
            )
            for offense in offenses
        ],
        payments=[
            PaymentResponse(
                id=payment.transaction_reference or f"PAY{payment.id:03d}",
                user_id=user.id,
                user_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
                amount=payment.amount,
                payment_date=payment.payment_date.strftime("%Y-%m-%d") if payment.payment_date else None,
                status=payment.status.value,
                offense_number=offense.offense_number if offense else None,
                method=payment.method.value if payment.method else None
            )
            for payment, offense in payments
        ],
        appeals=[
            AppealResponse(
                id=appeal.appeal_number,
                user_id=user.id,
                user_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
                offense_number=offense.offense_number,
                appeal_number=appeal.appeal_number,
                reason=appeal.reason.value,
                status=appeal.status.value,
                submission_date=appeal.submission_date.strftime("%Y-%m-%d")
            )
            for appeal, offense in appeals
        ]
    )

@router.put("/appeals/{appeal_number}/decision", response_model=AppealDetailResponse)
async def make_appeal_decision(
    appeal_number: str,
    decision: AppealDecisionRequest,
    request: Request,
    db: AsyncSession = Depends(aget_db),
    officer: User = Depends(verify_officer)
):
    """Update the status of an appeal (e.g., approve or reject)"""

    # Fetch appeal
    query = (
        select(OffenseAppeal, User, TrafficOffense)
        .join(User, OffenseAppeal.user_id == User.id)
        .join(TrafficOffense, OffenseAppeal.offense_id == TrafficOffense.id)
        .where(OffenseAppeal.appeal_number == appeal_number)
    )
    result = await db.execute(query)
    appeal_data = result.first()
    
    if not appeal_data:
        raise HTTPException(status_code=404, detail="Appeal not found")
    
    appeal, user, offense = appeal_data
    
    # Check if appeal is still under review
    if appeal.status != AppealStatus.UNDER_REVIEW:
        raise HTTPException(status_code=400, detail="Appeal is not under review")
            
    new_status = AppealStatus(decision.status.lower())

    # Update appeal
    appeal.status = new_status
    appeal.reviewer_id = officer.id
    appeal.reviewer_notes = decision.reviewer_notes
    appeal.response_date = datetime.utcnow()
    
    # Update OffenseStatistics
    stats_query = select(OffenseStatistics).where(OffenseStatistics.user_id == user.id)
    stats_result = await db.execute(stats_query)
    stats = stats_result.scalar_one_or_none()
    
    if stats:
        stats.pending_appeals = max(0, stats.pending_appeals - 1)
        if new_status == AppealStatus.APPROVED:
            stats.successful_appeals += 1
            # Optionally update offense status if approved
            offense.status = OffenseStatus.PAID  # Assuming approval waives the fine
        stats.last_calculated = datetime.utcnow()
    else:
        stats = OffenseStatistics(
            user_id=user.id,
            pending_appeals=0,
            successful_appeals=1 if new_status == AppealStatus.APPROVED else 0,
            total_offenses=0,
            total_fines_amount=0.0,
            total_paid_amount=0.0,
            driving_score=100,
            last_calculated=datetime.utcnow()
        )
        db.add(stats)
    
    try:
        await db.commit()
        await db.refresh(appeal)
        await db.refresh(offense)
        await db.refresh(stats)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update appeal: {str(e)}")
    
    return AppealDetailResponse(
        id=appeal.appeal_number,
        user_id=user.id,
        user_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
        offense_number=offense.offense_number,
        appeal_number=appeal.appeal_number,
        reason=appeal.reason.value,
        description=appeal.description,
        status=appeal.status.value,
        submission_date=appeal.submission_date.strftime("%Y-%m-%d"),
        response_date=appeal.response_date.strftime("%Y-%m-%d") if appeal.response_date else None,
        reviewer_notes=appeal.reviewer_notes,
        supporting_documents=appeal.supporting_documents or [],
        reviewer_id=appeal.reviewer_id
    )