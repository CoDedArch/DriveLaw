from sqlalchemy import JSON, Column, Enum, Integer,Boolean, ForeignKey, String, Float, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
from app.core.constants import OffenseType, PaymentStatus, PaymentMethod, PaymentPurpose


class Payment(Base, TimestampMixin):
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    offense_id = Column(Integer, ForeignKey('traffic_offenses.id'), nullable=True)  # Link to specific offense
    
    # Payment Details
    amount = Column(Float, nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    method = Column(Enum(PaymentMethod))
    purpose = Column(Enum(PaymentPurpose), nullable=False)  # FINE_PAYMENT, APPEAL_FEE, etc.
    
    # Transaction Details
    transaction_reference = Column(String(100), unique=True)
    receipt_number = Column(String(50), unique=True)
    payment_date = Column(DateTime)
    due_date = Column(DateTime)  # When payment is required by
    
    # Payment Gateway Details
    gateway_response = Column(JSON)  # Store gateway response for reference
    gateway_transaction_id = Column(String(100))
    
    # Additional Details
    notes = Column(Text)
    processed_by = Column(Integer, ForeignKey('users.id'))  # For manual payments
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    offense = relationship("TrafficOffense", back_populates="payments")
    processor = relationship("User", foreign_keys=[processed_by])
    
    def __repr__(self):
        return f"<Payment {self.purpose.value} GHS {self.amount} ({self.status.value})>"

# Fee structure remains the same but with additional offense-related purposes
class FeeStructure(Base, TimestampMixin):
    __tablename__ = 'fee_structures'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    purpose = Column(Enum(PaymentPurpose), nullable=False, unique=True)
    offense_type = Column(Enum(OffenseType))  # For offense-specific fees
    amount = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    description = Column(Text)
    
    def __repr__(self):
        return f"<Fee {self.name}: GHS {self.amount}>"
