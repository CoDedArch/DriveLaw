import enum
from typing import Dict, List
from sqlalchemy.sql import exists


class UserRole(enum.Enum):
    DRIVER = "driver"
    OFFICER = "officer"
    ADMIN = "admin"


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class PaymentMethod(enum.Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    MOBILE_MONEY = "mobile_money"
    CREDIT_CARD = "credit_card"

class VerificationStage(enum.Enum):
    OTP_PENDING = "otp_pending"           
    OTP_VERIFIED = "otp_verified"
    DOCUMENT_PENDING = "document_pending"
    FULLY_VERIFIED = "fully_verified"

class PaymentPurpose(enum.Enum):
    FINE_PAYMENT = "fine_payment"
    TRAFFIC_VIOLATION_FEE = "traffic_violation_fee"
    SPEEDING_FINE = "speeding_fine"
    PARKING_VIOLATION = "parking_violation"
    LICENSE_REINSTATEMENT = "license_reinstatement"
    COURT_FEES = "court_fees"
    ADMINISTRATIVE_FEE = "administrative_fee"
    LATE_PAYMENT_PENALTY = "late_payment_penalty"
    IMPOUND_FEES = "impound_fees"
    DUI_PENALTY = "dui_penalty"
    RECKLESS_DRIVING_FINE = "reckless_driving_fine"
    VEHICLE_REGISTRATION_FEE = "vehicle_registration_fee"
    INSPECTION_FEE = "inspection_fee"
    OTHER = "other"

    
class NotificationType(enum.Enum):
    APPLICATION_SUBMITTED = "application_submitted"
    REVIEW_REQUESTED = "review_requested"
    ADDITIONAL_INFO_REQUESTED = "additional_info_requested"
    APPLICATION_APPROVED = "application_approved"
    APPLICATION_REJECTED = "application_rejected"
    INSPECTION_SCHEDULED = "inspection_scheduled"
    APPROVAL_REQUESTED = "inspection_scheduled"
    INSPECTION_RESULT = "inspection_result"
    PAYMENT_RECEIVED = "payment_received"
    SYSTEM_ALERT = "system_alert"

class OffenseType(enum.Enum):
    SPEEDING = "speeding"
    RED_LIGHT_VIOLATION = "red_light_violation"
    PARKING_VIOLATION = "parking_violation"
    LANE_VIOLATION = "lane_violation"
    STOP_SIGN_VIOLATION = "stop_sign_violation"
    SEATBELT_VIOLATION = "seatbelt_violation"
    PHONE_USE = "phone_use"
    RECKLESS_DRIVING = "reckless_driving"
    DUI = "dui"
    OTHER = "other"

class OffenseStatus(enum.Enum):
    UNPAID = "unpaid"
    PAID = "paid"
    UNDER_APPEAL = "under_appeal"
    APPEALED_APPROVED = "appealed_approved"
    APPEALED_REJECTED = "appealed_rejected"
    OVERDUE = "overdue"
    WAIVED = "waived"

class OffenseSeverity(enum.Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    SEVERE = "severe"

class AppealStatus(enum.Enum):
    UNDER_REVIEW = "under_review"
    APPROVED = "approved" 
    REJECTED = "rejected"
    PENDING_DOCUMENTATION = "pending_documentation"
    WITHDRAWN = "withdrawn"

class AppealReason(enum.Enum):
    INCORRECT_DETAILS = "incorrect_details"
    NOT_DRIVER = "not_driver"
    EMERGENCY = "emergency"
    SIGNAGE_ISSUE = "signage_issue"
    EQUIPMENT_MALFUNCTION = "equipment_malfunction"
    ROAD_CONDITIONS = "road_conditions"
    OTHER = "other"