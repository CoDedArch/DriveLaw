from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from app.core.constants import NotificationType
from bs4 import BeautifulSoup
import re

class NotificationOut(BaseModel):
    id: int
    notification_type: NotificationType
    title: str
    message: str
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    sender_id: Optional[int]
    related_application_id: Optional[int]
    notification_metadata: Optional[str]
    
    @validator('message')
    def format_message(cls, v):
        """Format HTML message to plain text"""
        if v:
            soup = BeautifulSoup(v, 'html.parser')
            plain_text = soup.get_text(strip=True)
            return re.sub(r'\s+', ' ', plain_text).strip()
        return v
    
    class Config:
        from_attributes = True

class NotificationsListResponse(BaseModel):
    notifications: List[NotificationOut]
    total_count: int
    unread_count: int

class MarkAsReadRequest(BaseModel):
    notification_ids: List[int]