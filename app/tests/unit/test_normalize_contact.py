import pytest
from app.utils.contact_utils import normalize_contact, format_phone

@pytest.mark.parametrize("email", [
    "Test@Example.com",
    "USER@domain.org",
    "Name.Surname@GMAIL.COM"
])

def test_normalize_contact_email(email):
    normalized = normalize_contact(email, "email")
    assert normalized == email.lower()


@pytest.mark.parametrize("phone_input,expected", [
    ("+233596159150", "+233596159150"),       # Already normalized
    ("0596159150", "+233596159150"),          # Local format, should convert
    ("2330596159150", "+233596159150"),       # 2330 prefix, remove '0'
    ("(059) 615-9150", "+233596159150"),      # Mixed characters
    ("+233 059 615 9150", "+233596159150"),   # Spaces and valid
    ("0 5 9 6 1 5 9 1 5 0", "+233596159150"), # Spaces only
])
def test_normalize_contact_sms(phone_input, expected):
    normalized = normalize_contact(phone_input, "sms")
    assert normalized == expected


def test_format_phone_removes_non_digits():
    assert format_phone("(059) 615-9150") == "+233596159150"

def test_format_phone_local_to_international():
    assert format_phone("0596159150") == "+233596159150"

def test_format_phone_with_2330_prefix():
    assert format_phone("2330596159150") == "+233596159150"

def test_format_phone_already_international():
    assert format_phone("+233596159150") == "+233596159150"
