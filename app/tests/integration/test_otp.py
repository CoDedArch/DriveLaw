import pytest
from httpx import AsyncClient
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
import pytest_asyncio

pytestmark = pytest.mark.asyncio

@pytest_asyncio.fixture
async def client():
    # Create a new client for each test
    transport = ASGITransport(app=app)
    async with AsyncClient(transport, base_url="http://test") as client:
        yield client

@pytest.fixture
def test_email():
    return "kelvingbolo98@gmail.com"

@pytest.fixture
def test_phone():
    return "+2330596157150"

@pytest.mark.asyncio
async def test_send_otp_email(client: AsyncClient, test_email):
    response = await client.post(
        "/auth/send-otp",
        json={"contact": test_email, "channel": "email"}
    )
    assert response.status_code == 200
    assert "OTP sent" in response.json()["message"]

@pytest.mark.asyncio
async def test_send_otp_sms(client: AsyncClient, test_phone):
    response = await client.post(
        "/auth/send-otp", 
        json={"contact": test_phone, "channel": "sms"}
    )
    assert response.status_code == 200
    assert "OTP sent" in response.json()["message"]

@pytest.mark.asyncio
async def test_correct_otp_submission(
    client: AsyncClient, 
    test_email, 
    db_session: AsyncSession
):
    # Send OTP
    await client.post(
        "/auth/send-otp", 
        json={"contact": test_email, "channel": "email"}
    )
    
    # Get OTP from database
    result = await db_session.execute(
        "SELECT otp_secret FROM unverified_users WHERE email = :email",
        {"email": test_email}
    )
    otp = result.scalar()

    # Submit OTP
    response = await client.post(
        "/auth/verify-otp", 
        json={"contact": test_email, "otp": otp}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "OTP verified successfully"

@pytest.mark.asyncio
async def test_expired_otp_submission(
    client: AsyncClient, 
    test_email, 
    db_session: AsyncSession
):
    # Send OTP
    await client.post(
        "/auth/send-otp", 
        json={"contact": test_email, "channel": "email"}
    )

    # Expire OTP manually
    await db_session.execute(
        "UPDATE unverified_users SET otp_expires = NOW() - INTERVAL '10 minutes' WHERE email = :email",
        {"email": test_email}
    )
    await db_session.commit()

    # Get expired OTP
    result = await db_session.execute(
        "SELECT otp_secret FROM unverified_users WHERE email = :email",
        {"email": test_email}
    )
    otp = result.scalar()

    # Try verification
    response = await client.post(
        "/auth/verify-otp", 
        json={"contact": test_email, "otp": otp}
    )
    assert response.status_code == 400
    assert "Invalid or expired OTP" in response.json()["detail"]

@pytest.mark.asyncio
async def test_multiple_incorrect_attempts_lockout(
    client: AsyncClient, 
    test_email, 
    db_session: AsyncSession
):
    await client.post(
        "/auth/send-otp", 
        json={"contact": test_email, "channel": "email"}
    )

    for _ in range(5):  # MAX_ATTEMPTS
        res = await client.post(
            "/auth/verify-otp", 
            json={"contact": test_email, "otp": "000000"}
        )
    
    res = await client.post(
        "/auth/verify-otp", 
        json={"contact": test_email, "otp": "000000"}
    )
    assert res.status_code == 400

@pytest.mark.asyncio
async def test_rate_limit_send_otp(client: AsyncClient, test_email):
    for _ in range(3):  # Within rate limit
        res = await client.post(
            "/auth/send-otp", 
            json={"contact": test_email, "channel": "email"}
        )
        assert res.status_code == 200

    # This one should be throttled
    res = await client.post(
        "/auth/send-otp", 
        json={"contact": test_email, "channel": "email"}
    )
    assert res.status_code == 429  # Too Many Requests