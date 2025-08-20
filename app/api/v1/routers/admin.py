# app/api/admin/drivers.py

from dataclasses import Field
from datetime import datetime, timedelta
import enum
from typing import List, Optional
from unittest import case
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import and_, or_, select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.core.database import aget_db
from app.core.security import get_current_user
from app.core.constants import AppealStatus, OffenseSeverity, OffenseType, UserRole, OffenseStatus, VerificationStage
from app.models.appeals import OffenseAppeal
from app.models.user import User
from app.models.offenses import TrafficOffense

router = APIRouter(prefix="/admin", tags=["admin"])

# Response Models
class DriverVehicleResponse(BaseModel):
    make: str
    model: str
    year: int
    plate: str

class DriverSummaryResponse(BaseModel):
    id: str
    name: str
    license: str
    email: str
    phone: str
    registrationDate: str
    status: str
    totalOffenses: int
    totalFines: float
    paidFines: float
    outstandingFines: float
    licenseExpiry: str
    vehicle: Optional[DriverVehicleResponse] = None

class DriverOffenseResponse(BaseModel):
    id: str
    type: str
    date: str
    fine: float
    status: str

class DriverDetailsResponse(BaseModel):
    id: str
    name: str
    license: str
    email: str
    phone: str
    registrationDate: str
    status: str
    totalOffenses: int
    totalFines: float
    paidFines: float
    outstandingFines: float
    licenseExpiry: str
    vehicle: Optional[DriverVehicleResponse] = None
    offenses: List[DriverOffenseResponse]

class DriversListResponse(BaseModel):
    drivers: List[DriverSummaryResponse]
    totalCount: int
    activeCount: int
    suspendedCount: int
    pendingCount: int

class LicenseActionRequest(BaseModel):
    action: str  # "suspend" | "reinstate" | "verify"
    reason: str

# Helper functions
async def check_admin_access(request: Request, db: AsyncSession):
    """Verify that the current user is an admin"""
    user = await get_current_user(request, db)
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403, 
            detail="Access denied. Admin privileges required."
        )
    return user

def map_user_status_to_driver_status(user) -> str:
    """Map user verification stage to driver status"""
    if not user.is_active:
        return "Pending Verification"
    
    # Check if user has any active suspensions or restrictions
    # This would need to be implemented based on your suspension logic
    # For now, assume active users are "Active" and you can add suspension logic later
    return "Active"

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Option 1: Using separate queries (Recommended)
async def calculate_offense_stats(db: AsyncSession, user_id: int):
    """Calculate offense statistics for a driver using separate queries"""
    try:
        # Query 1: Get total offenses and total fines
        total_query = select(
            func.count(TrafficOffense.id).label('total_offenses'),
            func.coalesce(func.sum(TrafficOffense.fine_amount), 0).label('total_fines')
        ).where(TrafficOffense.user_id == user_id)
        
        total_result = await db.execute(total_query)
        total_stats = total_result.first()
        
        # Query 2: Get paid fines only
        paid_query = select(
            func.coalesce(func.sum(TrafficOffense.fine_amount), 0).label('paid_fines')
        ).where(
            (TrafficOffense.user_id == user_id) & 
            (TrafficOffense.status == OffenseStatus.PAID)
        )
        
        paid_result = await db.execute(paid_query)
        paid_stats = paid_result.first()
        
        if total_stats:
            total_offenses = total_stats.total_offenses or 0
            total_fines = float(total_stats.total_fines or 0)
            paid_fines = float(paid_stats.paid_fines or 0) if paid_stats else 0.0
            outstanding_fines = total_fines - paid_fines
            
            # Return camelCase keys to match your Pydantic model
            return {
                'totalOffenses': total_offenses,
                'totalFines': total_fines,
                'paidFines': paid_fines,
                'outstandingFines': outstanding_fines
            }
        
        return {
            'totalOffenses': 0,
            'totalFines': 0.0,
            'paidFines': 0.0,
            'outstandingFines': 0.0
        }
        
    except Exception as e:
        print(f"Error in calculate_offense_stats: {str(e)}")
        return {
            'totalOffenses': 0,
            'totalFines': 0.0,
            'paidFines': 0.0,
            'outstandingFines': 0.0
        }


# Endpoints

@router.get("/drivers", response_model=DriversListResponse)
async def get_all_drivers(
    request: Request,
    db: AsyncSession = Depends(aget_db),
    search: Optional[str] = Query(None, description="Search by name, email, phone, or license"),
    status: Optional[str] = Query(None, description="Filter by status: Active, Suspended, Pending Verification"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get all drivers for admin dashboard"""
    await check_admin_access(request, db)
    
    # Base query - get all users except admins
    query = select(User).where(User.role != UserRole.ADMIN)
    
    # Apply search filter
    if search:
        search_term = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(User.first_name).like(search_term),
                func.lower(User.last_name).like(search_term),
                func.lower(User.email).like(search_term),
                func.lower(User.phone).like(search_term),
                func.lower(User.national_id_number).like(search_term)
            )
        )
    
    # Get total count before applying pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total_count = total_result.scalar()
    
    # Apply pagination
    query = query.offset(offset).limit(limit).order_by(desc(User.created_at))
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    drivers = []
    active_count = 0
    suspended_count = 0
    pending_count = 0
    
    for user in users:
        # Calculate offense statistics
        offense_stats = await calculate_offense_stats(db, user.id)
        
        # Map user status
        driver_status = map_user_status_to_driver_status(user)
        
        # Count by status
        if driver_status == "Active":
            active_count += 1
        elif driver_status == "Suspended":
            suspended_count += 1
        elif driver_status == "Pending Verification":
            pending_count += 1
        
        # Apply status filter
        if status and driver_status != status:
            continue
        
        # Create driver response
        full_name = f"{user.first_name} {user.last_name}"
        if user.other_name:
            full_name = f"{user.first_name} {user.other_name} {user.last_name}"
        
        driver = DriverSummaryResponse(
            id=f"DRV-{user.id:04d}",
            name=full_name,
            license=user.national_id_number or "N/A",
            email=user.email,
            phone=user.phone,
            registrationDate=user.created_at.strftime("%Y-%m-%d"),
            status=driver_status,
            licenseExpiry="2026-12-31",  # You may want to add this field to User model
            **offense_stats
        )
        drivers.append(driver)
    
    return DriversListResponse(
        drivers=drivers,
        totalCount=total_count,
        activeCount=active_count,
        suspendedCount=suspended_count,
        pendingCount=pending_count
    )



@router.get("/dashboard/stats")
async def get_dashboard_statistics(
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Get comprehensive dashboard statistics for admin"""
    await check_admin_access(request, db)
    
    try:
        # Get driver statistics
        driver_stats_query = select(User).where(User.role != UserRole.ADMIN)
        driver_result = await db.execute(driver_stats_query)
        all_drivers = driver_result.scalars().all()
        
        total_users = len(all_drivers)
        
        # Get monthly offenses (current month)
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_offenses_query = select(func.count(TrafficOffense.id)).where(
            TrafficOffense.offense_date >= current_month_start
        )
        monthly_offenses_result = await db.execute(monthly_offenses_query)
        monthly_offenses = monthly_offenses_result.scalar() or 0
        
        # Get fines collected (paid offenses total)
        fines_collected_query = select(func.coalesce(func.sum(TrafficOffense.fine_amount), 0)).where(
            TrafficOffense.status == OffenseStatus.PAID
        )
        fines_collected_result = await db.execute(fines_collected_query)
        fines_collected = float(fines_collected_result.scalar() or 0)
        
        # Get pending appeals
        pending_appeals_query = select(func.count(OffenseAppeal.id)).where(
            OffenseAppeal.status == AppealStatus.UNDER_REVIEW
        )
        pending_appeals_result = await db.execute(pending_appeals_query)
        pending_appeals = pending_appeals_result.scalar() or 0
        
        # Get active officers (admins and officers who are active)
        active_officers_query = select(func.count(User.id)).where(
            and_(
                User.role.in_([UserRole.ADMIN, UserRole.OFFICER]),
                User.is_active == True
            )
        )
        active_officers_result = await db.execute(active_officers_query)
        active_officers = active_officers_result.scalar() or 0
        
        # FIXED: Active sessions calculation
        # Option 1: Use recently created accounts as proxy for activity
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        active_sessions_query = select(func.count(User.id)).where(
            and_(
                User.created_at >= twenty_four_hours_ago,  # Changed from last_login to created_at
                User.is_active == True
            )
        )
        active_sessions_result = await db.execute(active_sessions_query)
        active_sessions = active_sessions_result.scalar() or 0
        
        # Alternative approach: Just use total active users as "sessions"
        # active_sessions = total_users
        
        # Calculate percentage changes (mock for now - you'd compare with previous period)
        # These would be calculated by comparing current period with previous period
        user_change = 5  # +5%
        offense_change = -2  # -2%
        fines_change = 12  # +12%
        appeals_change = 3  # +3%
        
        return {
            "stats": {
                "totalUsers": total_users,
                "monthlyOffenses": monthly_offenses,
                "finesCollected": fines_collected,
                "pendingAppeals": pending_appeals,
                "activeOfficers": active_officers,
                "systemHealth": "Optimal",
                "databaseUsage": "45%",
                "serverLoad": "28%",
                "activeSessions": active_sessions
            },
            "changes": {
                "totalUsers": user_change,
                "monthlyOffenses": offense_change,
                "finesCollected": fines_change,
                "pendingAppeals": appeals_change
            }
        }
        
    except Exception as e:
        print(f"Error in get_dashboard_statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/drivers/{driver_id}", response_model=DriverDetailsResponse)
async def get_driver_details(
    driver_id: str,
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Get detailed information about a specific driver"""
    await check_admin_access(request, db)
    
    # Extract user ID from driver ID format (DRV-XXXX)
    try:
        user_id = int(driver_id.replace("DRV-", "").lstrip("0"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid driver ID format")
    
    # Get user details
    user_query = select(User).where(
        and_(
            User.id == user_id,
            User.role != UserRole.ADMIN
        )
    )
    
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    # Get offense statistics
    offense_stats = await calculate_offense_stats(db, user.id)
    
    # Get all offenses for this driver
    offenses_query = (
        select(TrafficOffense)
        .where(TrafficOffense.user_id == user.id)
        .order_by(desc(TrafficOffense.offense_date))
    )
    
    offenses_result = await db.execute(offenses_query)
    offenses = offenses_result.scalars().all()
    
    # Map offenses to response format
    offense_responses = []
    for offense in offenses:
        offense_responses.append(DriverOffenseResponse(
            id=offense.offense_number,
            type=offense.offense_type.value.replace("_", " ").title(),
            date=offense.offense_date.strftime("%Y-%m-%d"),
            fine=offense.fine_amount,
            status=offense.status.value.replace("_", " ").title()
        ))
    
    # Create full name
    full_name = f"{user.first_name} {user.last_name}"
    if user.other_name:
        full_name = f"{user.first_name} {user.other_name} {user.last_name}"
    
    # Map user status
    driver_status = map_user_status_to_driver_status(user)
    
    return DriverDetailsResponse(
        id=f"DRV-{user.id:04d}",
        name=full_name,
        license=user.national_id_number or "N/A",
        email=user.email,
        phone=user.phone,
        registrationDate=user.created_at.strftime("%Y-%m-%d"),
        status=driver_status,
        licenseExpiry="2026-12-31",  # You may want to add this field
        offenses=offense_responses,
        **offense_stats
    )

@router.post("/drivers/{driver_id}/license-action")
async def perform_license_action(
    driver_id: str,
    action_data: LicenseActionRequest,
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Suspend, reinstate, or verify a driver's license"""
    await check_admin_access(request, db)
    
    # Extract user ID from driver ID format
    try:
        user_id = int(driver_id.replace("DRV-", "").lstrip("0"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid driver ID format")
    
    # Get user
    user_query = select(User).where(
        and_(
            User.id == user_id,
            User.role != UserRole.ADMIN
        )
    )
    
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    # Perform the license action
    if action_data.action == "suspend":
        user.is_active = False
        # You might want to create a separate suspension table to track reasons
        action_message = "suspended"
        
    elif action_data.action == "reinstate":
        user.is_active = True
        action_message = "reinstated"
        
    elif action_data.action == "verify":
        user.is_active = True
        user.verification_stage = VerificationStage.FULLY_VERIFIED  # Changed from COMPLETED
        action_message = "verified"
        
    elif action_data.action == "activate":  # Added activate option
        user.is_active = True
        action_message = "activated"
        
    else:
        raise HTTPException(
            status_code=400, 
            detail="Invalid action. Valid actions are: suspend, reinstate, verify, activate"
        )
    
    try:
        # Save changes
        await db.commit()
        await db.refresh(user)
        
        return {
            "message": f"Driver license {action_message} successfully",
            "driver_id": driver_id,
            "action": action_data.action,
            "reason": action_data.reason,
            "user_status": {
                "is_active": user.is_active,
                "verification_stage": user.verification_stage.value if user.verification_stage else None
            }
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to perform action: {str(e)}"
        )

@router.get("/drivers/stats/overview")
async def get_driver_statistics(
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Get overall driver statistics for admin dashboard"""
    await check_admin_access(request, db)
    
    try:
        # Get all drivers (non-admin users)
        query = select(User).where(User.role != UserRole.ADMIN)
        result = await db.execute(query)
        users = result.scalars().all()
        
        total_drivers = len(users)
        active_drivers = sum(1 for user in users if user.is_active)
        suspended_drivers = sum(1 for user in users if not user.is_active and user.verification_stage == VerificationStage.FULLY_VERIFIED)
        pending_drivers = sum(1 for user in users if user.verification_stage != VerificationStage.FULLY_VERIFIED)
        
        # Get total fines statistics with simpler queries
        total_fines_query = select(func.coalesce(func.sum(TrafficOffense.fine_amount), 0))
        total_fines_result = await db.execute(total_fines_query)
        total_fines = total_fines_result.scalar() or 0
        
        paid_fines_query = select(func.coalesce(func.sum(TrafficOffense.fine_amount), 0)).where(
            TrafficOffense.status == OffenseStatus.PAID
        )
        paid_fines_result = await db.execute(paid_fines_query)
        paid_fines = paid_fines_result.scalar() or 0
        
        total_offenses_query = select(func.count(TrafficOffense.id))
        total_offenses_result = await db.execute(total_offenses_query)
        total_offenses = total_offenses_result.scalar() or 0
        
        outstanding_fines = total_fines - paid_fines
        
        return {
            "totalDrivers": total_drivers,
            "activeDrivers": active_drivers,
            "suspendedDrivers": suspended_drivers,
            "pendingDrivers": pending_drivers,
            "totalOffenses": total_offenses,
            "totalFines": float(total_fines),
            "paidFines": float(paid_fines),
            "outstandingFines": float(outstanding_fines)
        }
        
    except Exception as e:
        print(f"Error in get_driver_statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
class OffenseUpdateRequest(BaseModel):
    status: Optional[str] = None
    fine: Optional[float] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    severity: Optional[str] = None

class OffenseResponse(BaseModel):
    id: str
    offenseNumber: str
    date: str
    officer: dict
    type: str
    licensePlate: str
    driver: dict
    location: str
    fine: float
    status: str
    description: str
    evidence: List[str]
    dueDate: str
    severity: str
    createdAt: str
    updatedAt: str

@router.get("/offenses")
async def get_offenses(
    request: Request,
    db: AsyncSession = Depends(aget_db),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    offense_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0)
):
    """Get paginated list of all offenses with filtering"""
    await check_admin_access(request, db)
    
    try:
        # Build base query with eager loading
        query = select(TrafficOffense).options(
            selectinload(TrafficOffense.user)
        )
        
        # Apply filters
        conditions = []
        
        if search:
            search_term = f"%{search.lower()}%"
            conditions.append(
                or_(
                    func.lower(TrafficOffense.offense_number).contains(search_term),
                    func.lower(TrafficOffense.vehicle_registration).contains(search_term),
                    func.lower(TrafficOffense.location).contains(search_term),
                    func.lower(User.first_name).contains(search_term),
                    func.lower(User.last_name).contains(search_term),
                    func.lower(User.email).contains(search_term)
                )
            )
            query = query.join(User)
        
        if status and status != 'all':
            try:
                status_enum = OffenseStatus(status.upper().replace(' ', '_'))
                conditions.append(TrafficOffense.status == status_enum)
            except ValueError:
                pass
        
        if severity and severity != 'all':
            try:
                severity_enum = OffenseSeverity(severity.upper())
                conditions.append(TrafficOffense.severity == severity_enum)
            except ValueError:
                pass
        
        if offense_type and offense_type != 'all':
            try:
                type_enum = OffenseType(offense_type.upper().replace(' ', '_'))
                conditions.append(TrafficOffense.offense_type == type_enum)
            except ValueError:
                pass
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            conditions.append(TrafficOffense.offense_date >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            conditions.append(TrafficOffense.offense_date <= end_dt)
        
        # Apply conditions to query
        if conditions:
            query = query.where(and_(*conditions))
        
        # Get total count - Create a separate count query
        count_query = select(func.count(TrafficOffense.id))
        
        # Apply same joins and conditions to count query
        if search:
            count_query = count_query.select_from(TrafficOffense.join(User))
        
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        total_count_result = await db.execute(count_query)
        total_count = total_count_result.scalar()
        
        # Apply pagination and ordering to main query
        query = query.order_by(desc(TrafficOffense.created_at))
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        offenses = result.scalars().all()
        
        # Get status counts
        status_counts = {}
        for status_val in OffenseStatus:
            status_count_query = select(func.count(TrafficOffense.id)).where(
                TrafficOffense.status == status_val
            )
            
            # Apply search condition if present (excluding date filters for status counts)
            search_conditions = []
            if search:
                search_term = f"%{search.lower()}%"
                search_conditions.append(
                    or_(
                        func.lower(TrafficOffense.offense_number).contains(search_term),
                        func.lower(TrafficOffense.vehicle_registration).contains(search_term),
                        func.lower(TrafficOffense.location).contains(search_term),
                        func.lower(User.first_name).contains(search_term),
                        func.lower(User.last_name).contains(search_term),
                        func.lower(User.email).contains(search_term)
                    )
                )
                status_count_query = status_count_query.select_from(TrafficOffense.join(User))
            
            # Add non-date filter conditions
            if severity and severity != 'all':
                try:
                    severity_enum = OffenseSeverity(severity.upper())
                    search_conditions.append(TrafficOffense.severity == severity_enum)
                except ValueError:
                    pass
            
            if offense_type and offense_type != 'all':
                try:
                    type_enum = OffenseType(offense_type.upper().replace(' ', '_'))
                    search_conditions.append(TrafficOffense.offense_type == type_enum)
                except ValueError:
                    pass
            
            if search_conditions:
                status_count_query = status_count_query.where(and_(*search_conditions))
            
            count_result = await db.execute(status_count_query)
            status_counts[status_val.value.lower().replace('_', ' ')] = count_result.scalar()
        
        # Format response
        offense_list = []
        for offense in offenses:
            offense_data = {
                "id": str(offense.id),
                "offenseNumber": offense.offense_number,
                "date": offense.offense_date.isoformat(),
                "officer": {
                    "id": offense.officer_id or "",
                    "name": f"Officer {offense.officer_id or 'Unknown'}"
                },
                "type": offense.offense_type.value,
                "licensePlate": offense.vehicle_registration or "",
                "driver": {
                    "id": str(offense.user.id),
                    "name": f"{offense.user.first_name} {offense.user.last_name}",
                    "license": offense.user.national_id_number or "",
                    "email": offense.user.email,
                    "phone": offense.user.phone
                },
                "location": offense.location,
                "fine": float(offense.fine_amount),
                "status": offense.status.value.title().replace('_', ' '),
                "description": offense.description or "",
                "evidence": offense.evidence_urls or [],
                "dueDate": offense.due_date.isoformat(),
                "severity": offense.severity.value.lower(),
                "createdAt": offense.created_at.isoformat(),
                "updatedAt": offense.updated_at.isoformat()
            }
            offense_list.append(offense_data)
        
        return {
            "offenses": offense_list,
            "totalCount": total_count,
            "pendingPaymentCount": status_counts.get("unpaid", 0),
            "underAppealCount": status_counts.get("under_appeal", 0),
            "paidCount": status_counts.get("paid", 0),
            "overdueCount": status_counts.get("overdue", 0),
            "cancelledCount": status_counts.get("cancelled", 0)
        }
        
    except Exception as e:
        print(f"Error in get_offenses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# 2. Get Single Offense Details
@router.get("/offenses/{offense_id}")
async def get_offense_details(
    offense_id: int,
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Get detailed information about a specific offense"""
    await check_admin_access(request, db)
    
    try:
        # Get offense with all related data
        query = select(TrafficOffense).options(
            selectinload(TrafficOffense.user),
            selectinload(TrafficOffense.appeals),
            selectinload(TrafficOffense.payments)
        ).where(TrafficOffense.id == offense_id)
        
        result = await db.execute(query)
        offense = result.scalar_one_or_none()
        
        if not offense:
            raise HTTPException(status_code=404, detail="Offense not found")
        
        # Format detailed response
        offense_details = {
            "id": str(offense.id),
            "offenseNumber": offense.offense_number,
            "date": offense.offense_date.isoformat(),
            "officer": {
                "id": offense.officer_id or "",
                "name": f"Officer {offense.officer_id or 'Unknown'}"
            },
            "type": offense.offense_type.value,
            "licensePlate": offense.vehicle_registration or "",
            "driver": {
                "id": str(offense.user.id),
                "name": f"{offense.user.first_name} {offense.user.last_name}",
                "license": offense.user.national_id_number or "",
                "email": offense.user.email,
                "phone": offense.user.phone
            },
            "location": offense.location,
            "fine": float(offense.fine_amount),
            "status": offense.status.value.title().replace('_', ' '),
            "description": offense.description or "",
            "evidence": offense.evidence_urls or [],
            "dueDate": offense.due_date.isoformat(),
            "severity": offense.severity.value.lower(),
            "createdAt": offense.created_at.isoformat(),
            "updatedAt": offense.updated_at.isoformat(),
            
            # Additional details
            "officerDetails": {
                "id": offense.officer_id or "",
                "name": f"Officer {offense.officer_id or 'Unknown'}",
                "badge": offense.officer_id or "",
                "department": "Traffic Police"
            },
            "vehicleDetails": {
                "make": "Unknown",
                "model": "Unknown", 
                "year": 2020,
                "color": "Unknown"
            },
            "paymentHistory": [
    {
        "id": str(payment.id),
        "amount": float(payment.amount),
        "date": payment.created_at.isoformat(),
        "method": payment.method.value if payment.method else "Unknown",  # FIXED
        "reference": payment.transaction_reference or ""
    } for payment in offense.payments
],
            "appealHistory": [
    {
        "id": str(appeal.id),
        "date": appeal.created_at.isoformat(),
        "reason": appeal.reason.value if appeal.reason else "Unknown",  # Added safety check
        "status": appeal.status.value.title().replace('_', ' ') if appeal.status else "Unknown",
        "decision": appeal.reviewer_notes or ""
    } for appeal in offense.appeals
]
        }
        
        return offense_details
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_offense_details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# 3. Update Offense
@router.patch("/offenses/{offense_id}")
async def update_offense(
    offense_id: int,
    updates: OffenseUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Update offense details"""
    await check_admin_access(request, db)
    
    try:
        # Get offense
        query = select(TrafficOffense).where(TrafficOffense.id == offense_id)
        result = await db.execute(query)
        offense = result.scalar_one_or_none()
        
        if not offense:
            raise HTTPException(status_code=404, detail="Offense not found")
        
        # Apply updates
        if updates.status:
            try:
                status_enum = OffenseStatus(updates.status.upper().replace(' ', '_'))
                offense.status = status_enum
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid status")
        
        if updates.fine is not None:
            offense.fine_amount = updates.fine
        
        if updates.description is not None:
            offense.description = updates.description
        
        if updates.due_date:
            offense.due_date = datetime.fromisoformat(updates.due_date.replace('Z', '+00:00'))
        
        if updates.severity:
            try:
                severity_enum = OffenseSeverity(updates.severity.upper())
                offense.severity = severity_enum
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid severity")
        
        offense.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(offense)
        
        return {
            "message": "Offense updated successfully",
            "offenseId": str(offense.id),
            "status": offense.status.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error in update_offense: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# 4. Get Offense Statistics
@router.get("/offenses/stats/overview")
async def get_offense_statistics(
    request: Request,
    db: AsyncSession = Depends(aget_db),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Get comprehensive offense statistics"""
    await check_admin_access(request, db)
    
    try:
        # Build base query with date filters if provided
        base_query = select(TrafficOffense)
        conditions = []
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            conditions.append(TrafficOffense.offense_date >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            conditions.append(TrafficOffense.offense_date <= end_dt)
        
        if conditions:
            base_query = base_query.where(and_(*conditions))
        
        # Total offenses
        total_query = select(func.count(TrafficOffense.id))
        if conditions:
            total_query = total_query.where(and_(*conditions))
        total_result = await db.execute(total_query)
        total_offenses = total_result.scalar()
        
        # Status counts
        status_counts = {}
        for status in OffenseStatus:
            count_query = select(func.count(TrafficOffense.id)).where(
                TrafficOffense.status == status
            )
            if conditions:
                count_query = count_query.where(and_(*conditions))
            
            result = await db.execute(count_query)
            status_counts[status.value.lower()] = result.scalar()
        
        # Severity counts
        severity_counts = {}
        for severity in OffenseSeverity:
            count_query = select(func.count(TrafficOffense.id)).where(
                TrafficOffense.severity == severity
            )
            if conditions:
                count_query = count_query.where(and_(*conditions))
            
            result = await db.execute(count_query)
            severity_counts[f"{severity.value.lower()}SeverityCount"] = result.scalar()
        
        # Fine statistics
        total_fines_query = select(func.coalesce(func.sum(TrafficOffense.fine_amount), 0))
        if conditions:
            total_fines_query = total_fines_query.where(and_(*conditions))
        total_fines_result = await db.execute(total_fines_query)
        total_fines = total_fines_result.scalar()
        
        # Collected fines (paid status)
        collected_query = select(func.coalesce(func.sum(TrafficOffense.fine_amount), 0)).where(
            TrafficOffense.status == OffenseStatus.PAID
        )
        if conditions:
            collected_query = collected_query.where(and_(*conditions))
        collected_result = await db.execute(collected_query)
        collected_fines = collected_result.scalar()
        
        outstanding_fines = total_fines - collected_fines
        average_fine = total_fines / total_offenses if total_offenses > 0 else 0
        
        return {
            "totalOffenses": total_offenses,
            "pendingPayment": status_counts.get("unpaid", 0),
            "underAppeal": status_counts.get("under_appeal", 0),
            "paid": status_counts.get("paid", 0),
            "overdue": status_counts.get("overdue", 0),
            "cancelled": status_counts.get("cancelled", 0),
            "totalFines": float(total_fines),
            "collectedFines": float(collected_fines),
            "outstandingFines": float(outstanding_fines),
            "averageFine": float(average_fine),
            **severity_counts
        }
        
    except Exception as e:
        print(f"Error in get_offense_statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")




class AppealStatusEnum(str, enum.Enum):
    UNDER_REVIEW = "Under Review"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    PENDING_REVIEW = "Pending Review"

# Enum for Priority
class PriorityEnum(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class DecisionEnum(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class OfficerBase(BaseModel):
    id: str
    name: str
    badge: Optional[str] = ""
    department: Optional[str] = ""

class OfficerDetails(OfficerBase):
    email: Optional[str] = ""
    phone: Optional[str] = ""

class DriverBase(BaseModel):
    id: str
    name: str
    license: str
    email: Optional[str] = None
    phone: Optional[str] = None

class DriverDetails(DriverBase):
    address: Optional[str] = None

class OffenseBase(BaseModel):
    id: str
    offenseNumber: str
    type: str
    date: str
    location: str
    fine: float
    description: str

class OffenseDetails(OffenseBase):
    issuingOfficer: Optional[OfficerBase] = None

class EvidenceDetails(BaseModel):
    id: str
    filename: str
    fileType: str
    fileSize: int
    uploadDate: str
    url: str

class AppealHistory(BaseModel):
    id: str
    action: str
    performedBy: str
    performedAt: str
    notes: Optional[str] = None

# Main Appeal schemas
class AppealBase(BaseModel):
    id: str
    appealNumber: str
    offenseId: str
    offense: OffenseBase
    driver: DriverBase
    submittedDate: str
    status: AppealStatusEnum
    assignedTo: OfficerBase
    priority: PriorityEnum
    reason: str
    evidence: List[str]
    reviewNotes: Optional[str] = None
    reviewDate: Optional[str] = None
    dueDate: str
    createdAt: str
    updatedAt: str

class AppealDetails(AppealBase):
    officerDetails: OfficerDetails
    offenseDetails: OffenseDetails
    driverDetails: DriverDetails
    evidenceDetails: Optional[List[EvidenceDetails]] = []
    appealHistory: Optional[List[AppealHistory]] = []

# Request schemas
class AppealUpdateRequest(BaseModel):
    status: Optional[AppealStatusEnum] = None
    priority: Optional[PriorityEnum] = None
    assignedTo: Optional[str] = None
    reviewNotes: Optional[str] = None
    dueDate: Optional[str] = None

class AppealReviewRequest(BaseModel):
    decision: DecisionEnum
    reviewNotes: str
    notifyDriver: Optional[bool] = True

# Response schemas
class AppealListResponse(BaseModel):
    appeals: List[AppealBase]
    totalCount: int
    pendingReviewCount: int
    underReviewCount: int
    approvedCount: int
    rejectedCount: int

class AppealStatsResponse(BaseModel):
    totalAppeals: int
    pendingReview: int
    underReview: int
    approved: int
    rejected: int
    totalFinesAppealed: float
    approvedFinesAmount: float
    rejectedFinesAmount: float
    averageProcessingTime: float
    highPriorityCount: int
    mediumPriorityCount: int
    lowPriorityCount: int
    overdueCount: int

# Standard response schemas
class AppealUpdateResponse(BaseModel):
    message: str
    appealId: str

class AppealReviewResponse(BaseModel):
    message: str
    appealId: str
    status: str

class SuccessResponse(BaseModel):
    success: bool

# Officer list schema (for assignments)
class Officer(BaseModel):
    id: str
    name: str
    badge: Optional[str] = None
    department: Optional[str] = None

class OfficerListResponse(BaseModel):
    officers: List[Officer] = []

# Export request schema
class ExportFilters(BaseModel):
    search: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignedTo: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None

# Error response schema
class ErrorResponse(BaseModel):
    detail: str

# Additional utility schemas
class DateRange(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class PaginationParams(BaseModel):
    limit: int = 50
    offset: int = 0

class FilterParams(BaseModel):
    search: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.get("/appeals/admin", response_model=AppealListResponse)
async def get_appeals(
    request: Request,
    db: AsyncSession = Depends(aget_db),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0)
):
    """Get paginated list of all appeals with filtering"""
    await check_admin_access(request, db)
    
    try:
        # Build base query with eager loading
        query = select(OffenseAppeal).options(
            selectinload(OffenseAppeal.user),
            selectinload(OffenseAppeal.offense),
            selectinload(OffenseAppeal.reviewer)
        )
        
        # Apply filters
        conditions = []
        
        if search:
            search_term = f"%{search.lower()}%"
            conditions.append(
                or_(
                    func.lower(OffenseAppeal.appeal_number).contains(search_term),
                    func.lower(OffenseAppeal.description).contains(search_term),
                    func.lower(User.first_name).contains(search_term),
                    func.lower(User.last_name).contains(search_term),
                    func.lower(User.email).contains(search_term),
                    func.lower(TrafficOffense.offense_number).contains(search_term)
                )
            )
            query = query.join(User, OffenseAppeal.user_id == User.id)
            query = query.join(TrafficOffense, OffenseAppeal.offense_id == TrafficOffense.id)
        
        if status and status != 'all':
            try:
                status_enum = AppealStatus(status.upper().replace(' ', '_'))
                conditions.append(OffenseAppeal.status == status_enum)
            except ValueError:
                pass
        
        # Priority is not in your model, but I'll add logic for when it's added
        # For now, we can simulate priority based on submission date (newer = higher priority)
        
        if assigned_to and assigned_to != 'all':
            try:
                assigned_to_id = int(assigned_to)
                conditions.append(OffenseAppeal.reviewer_id == assigned_to_id)
            except ValueError:
                pass
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            conditions.append(OffenseAppeal.submission_date >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            conditions.append(OffenseAppeal.submission_date <= end_dt)
        
        # Apply conditions to query
        if conditions:
            query = query.where(and_(*conditions))
        
        # Get total count
        count_query = select(func.count(OffenseAppeal.id))
        
        if search:
            count_query = count_query.select_from(
                OffenseAppeal.join(User, OffenseAppeal.user_id == User.id)
                .join(TrafficOffense, OffenseAppeal.offense_id == TrafficOffense.id)
            )
        
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        total_count_result = await db.execute(count_query)
        total_count = total_count_result.scalar()
        
        # Apply pagination and ordering
        query = query.order_by(desc(OffenseAppeal.submission_date))
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        appeals = result.scalars().all()
        
        # Get status counts
        status_counts = {}
        for status_val in AppealStatus:
            status_count_query = select(func.count(OffenseAppeal.id)).where(
                OffenseAppeal.status == status_val
            )
            
            # Apply search and other non-status filters for accurate counts
            search_conditions = []
            if search:
                search_term = f"%{search.lower()}%"
                search_conditions.append(
                    or_(
                        func.lower(OffenseAppeal.appeal_number).contains(search_term),
                        func.lower(OffenseAppeal.description).contains(search_term),
                        func.lower(User.first_name).contains(search_term),
                        func.lower(User.last_name).contains(search_term),
                        func.lower(User.email).contains(search_term)
                    )
                )
                status_count_query = status_count_query.select_from(
                    OffenseAppeal.join(User, OffenseAppeal.user_id == User.id)
                )
            
            if assigned_to and assigned_to != 'all':
                try:
                    assigned_to_id = int(assigned_to)
                    search_conditions.append(OffenseAppeal.reviewer_id == assigned_to_id)
                except ValueError:
                    pass
            
            if search_conditions:
                status_count_query = status_count_query.where(and_(*search_conditions))
            
            count_result = await db.execute(status_count_query)
            status_counts[status_val.value.lower().replace('_', ' ')] = count_result.scalar()
        
        # Format response
        appeal_list = []
        for appeal in appeals:
            # Calculate priority based on days since submission (simulate)
            days_since_submission = (datetime.utcnow() - appeal.submission_date).days
            if days_since_submission > 7:
                priority = "high"
            elif days_since_submission > 3:
                priority = "medium"
            else:
                priority = "low"
            
            # Calculate due date (simulate - 14 days from submission)
            due_date = appeal.submission_date + timedelta(days=14)
            
            appeal_data = {
                "id": str(appeal.id),
                "appealNumber": appeal.appeal_number,
                "offenseId": str(appeal.offense_id),
                "offense": {
                    "id": str(appeal.offense.id),
                    "offenseNumber": appeal.offense.offense_number,
                    "type": appeal.offense.offense_type.value,
                    "date": appeal.offense.offense_date.isoformat(),
                    "location": appeal.offense.location,
                    "fine": float(appeal.offense.fine_amount),
                    "description": appeal.offense.description or ""
                },
                "driver": {
                    "id": str(appeal.user.id),
                    "name": f"{appeal.user.first_name} {appeal.user.last_name}",
                    "license": appeal.user.national_id_number or "",
                    "email": appeal.user.email,
                    "phone": appeal.user.phone
                },
                "submittedDate": appeal.submission_date.isoformat(),
                "status": appeal.status.value.title().replace('_', ' '),
                "assignedTo": {
                    "id": str(appeal.reviewer_id) if appeal.reviewer_id else "",
                    "name": f"{appeal.reviewer.first_name} {appeal.reviewer.last_name}" if appeal.reviewer else "Unassigned",
                    "badge": f"BADGE{appeal.reviewer_id}" if appeal.reviewer_id else "",
                    "department": "Traffic Division" if appeal.reviewer else ""
                },
                "priority": priority,
                "reason": appeal.reason.value if appeal.reason else "",
                "evidence": appeal.supporting_documents or [],
                "reviewNotes": appeal.reviewer_notes,
                "reviewDate": appeal.response_date.isoformat() if appeal.response_date else None,
                "dueDate": due_date.isoformat(),
                "createdAt": appeal.created_at.isoformat(),
                "updatedAt": appeal.updated_at.isoformat()
            }
            appeal_list.append(appeal_data)
        
        return {
            "appeals": appeal_list,
            "totalCount": total_count,
            "pendingReviewCount": status_counts.get("under_review", 0),
            "underReviewCount": status_counts.get("under_review", 0),
            "approvedCount": status_counts.get("approved", 0),
            "rejectedCount": status_counts.get("rejected", 0)
        }
        
    except Exception as e:
        print(f"Error in get_appeals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/appeals/{appeal_id}")
async def get_appeal_details(
    appeal_id: int,
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Get detailed information about a specific appeal"""
    await check_admin_access(request, db)
    
    try:
        query = select(OffenseAppeal).options(
            selectinload(OffenseAppeal.user),
            selectinload(OffenseAppeal.offense),
            selectinload(OffenseAppeal.reviewer)
        ).where(OffenseAppeal.id == appeal_id)
        
        result = await db.execute(query)
        appeal = result.scalar_one_or_none()
        
        if not appeal:
            raise HTTPException(status_code=404, detail="Appeal not found")
        
        # Calculate priority and due date (simulate)
        days_since_submission = (datetime.utcnow() - appeal.submission_date).days
        if days_since_submission > 7:
            priority = "high"
        elif days_since_submission > 3:
            priority = "medium"
        else:
            priority = "low"
        
        due_date = appeal.submission_date + timedelta(days=14)
        
        # Format detailed response
        appeal_details = {
            "id": str(appeal.id),
            "appealNumber": appeal.appeal_number,
            "offenseId": str(appeal.offense_id),
            "offense": {
                "id": str(appeal.offense.id),
                "offenseNumber": appeal.offense.offense_number,
                "type": appeal.offense.offense_type.value,
                "date": appeal.offense.offense_date.isoformat(),
                "location": appeal.offense.location,
                "fine": float(appeal.offense.fine_amount),
                "description": appeal.offense.description or ""
            },
            "driver": {
                "id": str(appeal.user.id),
                "name": f"{appeal.user.first_name} {appeal.user.last_name}",
                "license": appeal.user.national_id_number or "",
                "email": appeal.user.email,
                "phone": appeal.user.phone
            },
            "submittedDate": appeal.submission_date.isoformat(),
            "status": appeal.status.value.title().replace('_', ' '),
            "assignedTo": {
                "id": str(appeal.reviewer_id) if appeal.reviewer_id else "",
                "name": f"{appeal.reviewer.first_name} {appeal.reviewer.last_name}" if appeal.reviewer else "Unassigned",
                "badge": f"BADGE{appeal.reviewer_id}" if appeal.reviewer_id else "",
                "department": "Traffic Division" if appeal.reviewer else ""
            },
            "priority": priority,
            "reason": appeal.reason.value if appeal.reason else "",
            "evidence": appeal.supporting_documents or [],
            "reviewNotes": appeal.reviewer_notes,
            "reviewDate": appeal.response_date.isoformat() if appeal.response_date else None,
            "dueDate": due_date.isoformat(),
            "createdAt": appeal.created_at.isoformat(),
            "updatedAt": appeal.updated_at.isoformat(),
            
            # Extended details
            "officerDetails": {
                "id": str(appeal.reviewer_id) if appeal.reviewer_id else "",
                "name": f"{appeal.reviewer.first_name} {appeal.reviewer.last_name}" if appeal.reviewer else "Unassigned",
                "badge": f"BADGE{appeal.reviewer_id}" if appeal.reviewer_id else "",
                "department": "Traffic Division" if appeal.reviewer else "",
                "email": appeal.reviewer.email if appeal.reviewer else "",
                "phone": appeal.reviewer.phone if appeal.reviewer else ""
            },
            "offenseDetails": {
                "id": str(appeal.offense.id),
                "offenseNumber": appeal.offense.offense_number,
                "type": appeal.offense.offense_type.value,
                "date": appeal.offense.offense_date.isoformat(),
                "location": appeal.offense.location,
                "fine": float(appeal.offense.fine_amount),
                "description": appeal.offense.description or "",
                "issuingOfficer": {
                    "id": appeal.offense.officer_id or "",
                    "name": f"Officer {appeal.offense.officer_id or 'Unknown'}"
                }
            },
            "driverDetails": {
                "id": str(appeal.user.id),
                "name": f"{appeal.user.first_name} {appeal.user.last_name}",
                "license": appeal.user.national_id_number or "",
                "email": appeal.user.email,
                "phone": appeal.user.phone,
                "address": appeal.user.address
            },
            "evidenceDetails": [
                {
                    "id": str(i),
                    "filename": doc.split('/')[-1] if isinstance(doc, str) else f"evidence_{i}",
                    "fileType": "image/jpeg",  # You'd determine this from actual file
                    "fileSize": 0,  # You'd get this from file metadata
                    "uploadDate": appeal.submission_date.isoformat(),
                    "url": doc if isinstance(doc, str) else ""
                }
                for i, doc in enumerate(appeal.supporting_documents or [])
            ],
            "appealHistory": [
                {
                    "id": "1",
                    "action": "Appeal Submitted",
                    "performedBy": f"{appeal.user.first_name} {appeal.user.last_name}",
                    "performedAt": appeal.submission_date.isoformat(),
                    "notes": "Initial appeal submission"
                }
            ]
        }
        
        if appeal.reviewer:
            appeal_details["appealHistory"].append({
                "id": "2",
                "action": "Appeal Assigned",
                "performedBy": "System",
                "performedAt": appeal.updated_at.isoformat(),
                "notes": f"Assigned to {appeal.reviewer.first_name} {appeal.reviewer.last_name}"
            })
        
        if appeal.response_date:
            appeal_details["appealHistory"].append({
                "id": "3",
                "action": f"Appeal {appeal.status.value.title()}",
                "performedBy": f"{appeal.reviewer.first_name} {appeal.reviewer.last_name}" if appeal.reviewer else "System",
                "performedAt": appeal.response_date.isoformat(),
                "notes": appeal.reviewer_notes or ""
            })
        
        return appeal_details
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_appeal_details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.patch("/appeals/{appeal_id}")
async def update_appeal(
    appeal_id: int,
    updates: AppealUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Update appeal details"""
    await check_admin_access(request, db)
    
    try:
        query = select(OffenseAppeal).where(OffenseAppeal.id == appeal_id)
        result = await db.execute(query)
        appeal = result.scalar_one_or_none()
        
        if not appeal:
            raise HTTPException(status_code=404, detail="Appeal not found")
        
        # Update fields
        if updates.status:
            try:
                appeal.status = AppealStatus(updates.status.upper().replace(' ', '_'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid status")
        
        if updates.assignedTo:
            try:
                assigned_to_id = int(updates.assignedTo)
                # Verify the user exists and is an admin/officer
                user_query = select(User).where(
                    User.id == assigned_to_id,
                    User.role.in_([UserRole.ADMIN, UserRole.OFFICER])
                )
                user_result = await db.execute(user_query)
                assigned_user = user_result.scalar_one_or_none()
                
                if not assigned_user:
                    raise HTTPException(status_code=400, detail="Invalid officer assignment")
                
                appeal.reviewer_id = assigned_to_id
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid assigned_to value")
        
        if updates.reviewNotes:
            appeal.reviewer_notes = updates.reviewNotes
        
        if updates.dueDate:
            try:
                appeal.due_date = datetime.fromisoformat(updates.dueDate.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid due date format")
        
        await db.commit()
        await db.refresh(appeal)
        
        return {"message": "Appeal updated successfully", "appealId": str(appeal.id)}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error in update_appeal: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/appeals/{appeal_id}/review")
async def review_appeal(
    appeal_id: int,
    review_data: AppealReviewRequest,
    request: Request,
    db: AsyncSession = Depends(aget_db)
):
    """Review and make a decision on an appeal"""
    await check_admin_access(request, db)
    
    try:
        query = select(OffenseAppeal).where(OffenseAppeal.id == appeal_id)
        result = await db.execute(query)
        appeal = result.scalar_one_or_none()
        
        if not appeal:
            raise HTTPException(status_code=404, detail="Appeal not found")
        
        # Update appeal status based on decision
        if review_data.decision == "approved":
            appeal.status = AppealStatus.APPROVED
        elif review_data.decision == "rejected":
            appeal.status = AppealStatus.REJECTED
        else:
            raise HTTPException(status_code=400, detail="Invalid decision")
        
        appeal.reviewer_notes = review_data.reviewNotes
        appeal.response_date = datetime.utcnow()
        
        # Get current user (reviewer) from request
        # This would typically come from your auth system
        # For now, we'll assume it's passed in the request or session
        
        await db.commit()
        await db.refresh(appeal)
        
        # If notifyDriver is True, you would send notification here
        # This would integrate with your notification system
        
        return {
            "message": f"Appeal {review_data.decision} successfully",
            "appealId": str(appeal.id),
            "status": appeal.status.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error in review_appeal: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/appeals/stats/overview")
async def get_appeal_stats(
    request: Request,
    db: AsyncSession = Depends(aget_db),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Get comprehensive appeal statistics"""
    await check_admin_access(request, db)
    
    try:
        # Build base query for date filtering
        conditions = []
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            conditions.append(OffenseAppeal.submission_date >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            conditions.append(OffenseAppeal.submission_date <= end_dt)
        
        # Base condition for filtering
        base_condition = and_(*conditions) if conditions else True
        
        # Get total appeals
        total_query = select(func.count(OffenseAppeal.id)).where(base_condition)
        total_result = await db.execute(total_query)
        total_appeals = total_result.scalar()
        
        # Get status counts
        status_counts = {}
        for status in AppealStatus:
            status_query = select(func.count(OffenseAppeal.id)).where(
                and_(OffenseAppeal.status == status, base_condition)
            )
            status_result = await db.execute(status_query)
            status_counts[status.value] = status_result.scalar()
        
        # Get total fines appealed - FIXED
        fines_query = select(func.sum(TrafficOffense.fine_amount)).where(
            and_(OffenseAppeal.offense_id == TrafficOffense.id, base_condition)
        )
        fines_result = await db.execute(fines_query)
        total_fines_appealed = float(fines_result.scalar() or 0)
        
        # Get approved fines amount - FIXED
        approved_fines_query = select(func.sum(TrafficOffense.fine_amount)).where(
            and_(
                OffenseAppeal.offense_id == TrafficOffense.id,
                OffenseAppeal.status == AppealStatus.APPROVED,
                base_condition
            )
        )
        approved_fines_result = await db.execute(approved_fines_query)
        approved_fines_amount = float(approved_fines_result.scalar() or 0)
        
        # Get rejected fines amount - FIXED
        rejected_fines_query = select(func.sum(TrafficOffense.fine_amount)).where(
            and_(
                OffenseAppeal.offense_id == TrafficOffense.id,
                OffenseAppeal.status == AppealStatus.REJECTED,
                base_condition
            )
        )
        rejected_fines_result = await db.execute(rejected_fines_query)
        rejected_fines_amount = float(rejected_fines_result.scalar() or 0)
        
        # Calculate average processing time (for completed appeals)
        completed_appeals_query = select(
            func.avg(
                func.extract('epoch', OffenseAppeal.response_date - OffenseAppeal.submission_date) / 86400
            )
        ).where(
            and_(
                OffenseAppeal.response_date.is_not(None),
                base_condition
            )
        )
        avg_processing_result = await db.execute(completed_appeals_query)
        avg_processing_time = float(avg_processing_result.scalar() or 0)
        
        # Calculate priority counts (simulated based on submission date)
        now = datetime.utcnow()
        
        high_priority_query = select(func.count(OffenseAppeal.id)).where(
            and_(
                OffenseAppeal.submission_date <= now - timedelta(days=7),
                OffenseAppeal.status == AppealStatus.UNDER_REVIEW,
                base_condition
            )
        )
        high_priority_result = await db.execute(high_priority_query)
        high_priority_count = high_priority_result.scalar()
        
        medium_priority_query = select(func.count(OffenseAppeal.id)).where(
            and_(
                OffenseAppeal.submission_date <= now - timedelta(days=3),
                OffenseAppeal.submission_date > now - timedelta(days=7),
                OffenseAppeal.status == AppealStatus.UNDER_REVIEW,
                base_condition
            )
        )
        medium_priority_result = await db.execute(medium_priority_query)
        medium_priority_count = medium_priority_result.scalar()
        
        low_priority_query = select(func.count(OffenseAppeal.id)).where(
            and_(
                OffenseAppeal.submission_date > now - timedelta(days=3),
                OffenseAppeal.status == AppealStatus.UNDER_REVIEW,
                base_condition
            )
        )
        low_priority_result = await db.execute(low_priority_query)
        low_priority_count = low_priority_result.scalar()
        
        # Calculate overdue count (appeals older than 14 days without response)
        overdue_query = select(func.count(OffenseAppeal.id)).where(
            and_(
                OffenseAppeal.submission_date <= now - timedelta(days=14),
                OffenseAppeal.response_date.is_(None),
                base_condition
            )
        )
        overdue_result = await db.execute(overdue_query)
        overdue_count = overdue_result.scalar()
        
        return {
            "totalAppeals": total_appeals,
            "pendingReview": status_counts.get(AppealStatus.UNDER_REVIEW.value, 0),
            "underReview": status_counts.get(AppealStatus.UNDER_REVIEW.value, 0),
            "approved": status_counts.get(AppealStatus.APPROVED.value, 0),
            "rejected": status_counts.get(AppealStatus.REJECTED.value, 0),
            "totalFinesAppealed": total_fines_appealed,
            "approvedFinesAmount": approved_fines_amount,
            "rejectedFinesAmount": rejected_fines_amount,
            "averageProcessingTime": avg_processing_time,
            "highPriorityCount": high_priority_count,
            "mediumPriorityCount": medium_priority_count,
            "lowPriorityCount": low_priority_count,
            "overdueCount": overdue_count
        }
        
    except Exception as e:
        print(f"Error in get_appeal_stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")