# Response Models
from typing import Optional
from pydantic import BaseModel


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
