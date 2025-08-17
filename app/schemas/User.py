from datetime import date, datetime
from typing import Annotated, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, constr, validator

class ApplicantTypeOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None

    class Config:
        orm_mode = True
class GhanaCardDocument(BaseModel):
    front: str  # URL to the front image
    back: str

class OnboardingData(BaseModel):
    firstname: str  # Frontend sends 'firstname'
    lastname: str   # Frontend sends 'lastname'
    email: str
    gender: str  # "Male" or "Female"
    dob: str  # Frontend sends as string, we'll convert to date
    contact: str  # Frontend sends formatted phone number with +233
    nationality: str
    nationalid: str  # "Ghana Card", "Passport", or "Driver's License"
    idnumber: str
    region: str
    role: str  # "driver", "officer", or "admin"
    gpsaddress: str
    
    @validator('dob')
    def parse_date_of_birth(cls, v):
        """Convert string date to datetime object"""
        try:
            return datetime.strptime(v, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError('Date of birth must be in YYYY-MM-DD format')
    
    @validator('contact')
    def validate_contact(cls, v):
        """Ensure contact starts with +233"""
        if not v.startswith('+233'):
            raise ValueError('Phone number must start with +233')
        return v

class UserProfileOut(BaseModel):
    ghana_card_number: Optional[str] = None
    digital_address: Optional[str] = None
    specialization: Optional[str] = None
    work_email: Optional[str] = None
    staff_number: Optional[str] = None
    designation: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    other_name: Optional[str] = None
    phone: str
    alt_phone: Optional[str] = None
    is_active: bool
    role: str
    preferred_verification: str
    verification_stage: str
    date_of_birth: Optional[datetime] = None
    gender: Optional[str]
    address: Optional[str] = None
    applicant_type_code: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class UserDocumentOut(BaseModel):
    id: int
    document_type: str
    file_url: str

    model_config = ConfigDict(from_attributes=True)


class CurrentUserResponse(BaseModel):
    authenticated: bool
    user: UserOut
    profile: Optional[UserProfileOut]
    documents: List[UserDocumentOut] = []


class GhanaCardInput(BaseModel):
    ghana_card_number: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=20)]


class StaffOnboardingRequest(BaseModel):
    mmda_id: int
    department_id: int
    committee_id: int
    role: str
    specialization: Optional[str]
    work_email: Optional[EmailStr] = None
    staff_number: Optional[str]
    designation: Optional[str]

    @validator("work_email", pre=True)
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v

class DepartmentBase(BaseModel):
    id: int
    name: str
    code: str

class CommitteeBase(BaseModel):
    id: int
    name: str
