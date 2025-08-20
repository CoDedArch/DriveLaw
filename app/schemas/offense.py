from pydantic import BaseModel
from enum import Enum


class OffenseResponse(BaseModel):
    id: str
    date: str
    time: str
    type: str
    location: str
    fine: float
    status: str
    description: str
    evidence: str
    dueDate: str
    severity: str


class OffenseSeverity(str, Enum):
    MAJOR = "MAJOR"
    MODERATE = "MODERATE"
    MINOR = "MINOR"

class OffenseStatus(str, Enum):
    UNPAID = "UNPAID"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    UNDER_APPEAL = "UNDER_APPEAL"
    OVERDUE = "OVERDUE"

class OffenseType(str, Enum):
    SPEEDING = "Speeding"
    RED_LIGHT_VIOLATION = "Red Light Violation"
    ILLEGAL_PARKING = "Illegal Parking"
    LANE_VIOLATION = "Lane Violation"