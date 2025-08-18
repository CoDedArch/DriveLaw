from sqlalchemy import JSON, Boolean, Enum, Column, DateTime, Float, ForeignKey, Integer, String, Text
from app.core.constants import AppealReason, AppealStatus, OffenseType
from app.models.base import Base, TimestampMixin
from sqlalchemy.orm import relationship

class OffenseAppeal(Base, TimestampMixin):
    __tablename__ = 'offense_appeals'
    
    id = Column(Integer, primary_key=True,autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    offense_id = Column(Integer, ForeignKey('traffic_offenses.id'), nullable=False)
    
    # Appeal Details
    appeal_number = Column(String(20), unique=True, nullable=False)  # e.g., APP001
    reason = Column(Enum(AppealReason), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum(AppealStatus), default=AppealStatus.UNDER_REVIEW)
    
    # Evidence
    supporting_documents = Column(JSON)  # Array of uploaded document URLs
    
    # Review Details
    reviewer_id = Column(Integer, ForeignKey('users.id'))  # Admin/Officer who reviews
    reviewer_notes = Column(Text)
    response_date = Column(DateTime)
    
    # System fields
    submission_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    offense = relationship("TrafficOffense", back_populates="appeals")
    reviewer = relationship("User", foreign_keys=[reviewer_id]) 
    
    def __repr__(self):
        return f"<OffenseAppeal {self.appeal_number} for {self.offense.offense_number}>"
    
# Optional: Model for tracking violation patterns and analytics
class OffenseStatistics(Base, TimestampMixin):
    __tablename__ = 'offense_statistics'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Driver Statistics
    total_offenses = Column(Integer, default=0)
    total_fines_amount = Column(Float, default=0.0)
    total_paid_amount = Column(Float, default=0.0)
    pending_appeals = Column(Integer, default=0)
    successful_appeals = Column(Integer, default=0)
    driving_score = Column(Integer, default=100)  # Out of 100
    
    # Last calculation date
    last_calculated = Column(DateTime)
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f"<OffenseStatistics User {self.user_id} - Score: {self.driving_score}>"

# Optional: Model for location-based offense tracking
class OffenseLocation(Base, TimestampMixin):
    __tablename__ = 'offense_locations'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    address = Column(String(500))
    gps_coordinates = Column(String(50))  # "latitude,longitude"
    region = Column(String(100))
    district = Column(String(100))
    
    # Statistics
    total_offenses = Column(Integer, default=0)
    most_common_offense = Column(Enum(OffenseType))
    
    def __repr__(self):
        return f"<OffenseLocation {self.name}>"