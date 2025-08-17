from sqlalchemy import Column, Enum, Integer, ForeignKey, String, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
from app.core.constants import NotificationType

class Notification(Base, TimestampMixin):
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True)
    recipient_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    sender_id = Column(Integer, ForeignKey('users.id'))
    notification_type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime)
    notification_metadata = Column(Text)  # JSON string for additional data
    
    # Relationships
    recipient = relationship("User", foreign_keys=[recipient_id])
    sender = relationship("User", foreign_keys=[sender_id])
    
    def __repr__(self):
        return f"<Notification to User {self.recipient_id}: {self.title}>"