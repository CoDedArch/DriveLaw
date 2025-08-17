from pydantic import BaseModel


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