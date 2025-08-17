from typing import Optional

from pydantic import BaseModel


class AppealResponse(BaseModel):
    id: str
    offenseId: str
    offenseType: str
    location: str
    submissionDate: str
    status: str
    reason: str
    description: str
    responseDate: Optional[str] = None
    reviewerNotes: Optional[str] = None