from sqlalchemy import JSON, Column, String, Integer, Enum, Boolean, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
from app.core.constants import  UserRole, VerificationStage

class UnverifiedUser(Base, TimestampMixin):
    __tablename__ = 'unverified_users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True)
    phone = Column(String(20), unique=True)
    otp_secret = Column(String(100), nullable=False)
    otp_expires = Column(DateTime, nullable=False)
    verification_channel = Column(String(10), nullable=False)  # 'email' or 'sms'
    verification_attempts = Column(Integer, default=0)
    is_locked = Column(Boolean, default=False)
    lock_expires = Column(DateTime)
    
    def __repr__(self):
        return f"<UnverifiedUser {self.email or self.phone}>"

class User(Base, TimestampMixin):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    
    # Personal Details
    email = Column(String(255), unique=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    other_name = Column(String(100))
    gender = Column(String(10))  # Male, Female, Other
    date_of_birth = Column(DateTime)
    nationality = Column(String(100), default="Ghanaian")
    address = Column(String(255))  # This can store GPS address or home address
    gps_address = Column(String(50))
    
    # Contact Information
    phone = Column(String(20), unique=True)
    alt_phone = Column(String(20), unique=True)
    
    # Identification
    national_id_type = Column(String(50))  # e.g., Ghana Card, Passport
    national_id_number = Column(String(50), unique=True)
    region = Column(String(100))
    
    # Account & Verification
    is_active = Column(Boolean, default=False)  # Disabled until Ghana Card verification
    preferred_verification = Column(String(10), default='email')
    role = Column(Enum(UserRole), nullable=False, default=UserRole.DRIVER)
    verification_stage = Column(
        Enum(VerificationStage), 
        default=VerificationStage.OTP_PENDING
    )
    
    # Relationships
    documents = relationship("UserDocument", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.email} ({self.role.value})>"

class UserDocument(Base, TimestampMixin):
    __tablename__ = 'user_documents'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    document_type = Column(String(50), nullable=False)
    file_url = Column(String(255), nullable=False) 
    
    
    user = relationship(
        "User", 
        back_populates="documents",
        foreign_keys=[user_id] 
    )
    
    def __repr__(self):
        return f"<UserDocument {self.document_type} for User {self.user_id}>"

