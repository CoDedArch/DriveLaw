from typing import List
from pydantic import BaseModel

from app.schemas.offense import OffenseResponse


class DashboardData(BaseModel):
    name: str
    license: str
    totalOffenses: int
    totalFines: float
    pendingAppeals: int
    drivingScore: int

class DashboardResponse(BaseModel):
    driverData: DashboardData
    recentOffenses: List[OffenseResponse]
    pendingAmount: float