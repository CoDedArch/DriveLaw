from sqlalchemy import JSON, Boolean, Enum, Column, DateTime, Float, ForeignKey, Integer, String, Text
from app.core.constants import OffenseSeverity, OffenseStatus, OffenseType
from app.models.base import Base, TimestampMixin
from sqlalchemy.orm import relationship

class TrafficOffense(Base, TimestampMixin):
    __tablename__ = 'traffic_offenses'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Offense Details
    offense_number = Column(String(20), unique=True, nullable=False)  # e.g., OFF001
    offense_type = Column(Enum(OffenseType), nullable=False)
    offense_date = Column(DateTime, nullable=False)
    offense_time = Column(String(10), nullable=False)  # Store as "HH:MM" format
    location = Column(String(255), nullable=False)
    
    # Fine & Status
    fine_amount = Column(Float, nullable=False)
    status = Column(Enum(OffenseStatus), default=OffenseStatus.UNPAID)
    severity = Column(Enum(OffenseSeverity), default=OffenseSeverity.MINOR)
    
    # Additional Details
    description = Column(Text)
    evidence_urls = Column(JSON)  # Store array of evidence file URLs
    due_date = Column(DateTime, nullable=False)  # When payment is due
    officer_id = Column(String(50))  # ID of issuing officer
    vehicle_registration = Column(String(20))  # License plate
    
    # System fields
    is_active = Column(Boolean, default=True)
    points = Column(Integer, default=0)  # Driving points deducted
    
    # Relationships
    user = relationship("User")
    appeals = relationship("OffenseAppeal", back_populates="offense")
    payments = relationship("Payment", back_populates="offense")
    
    def __repr__(self):
        return f"<TrafficOffense {self.offense_number} - {self.offense_type.value}>"