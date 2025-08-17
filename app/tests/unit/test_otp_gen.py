import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.otpService import OtpService

@pytest.mark.asyncio
async def test_generate_otp_adds_new_user():
    # Arrange
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # Simulate no existing user

    mock_db.execute.return_value = mock_result

    otp_service = OtpService()

    # Act
    otp = await otp_service.generate_otp("kelvingbolo98@gmail.com", mock_db)

    # Assert
    assert len(otp) == 6
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
