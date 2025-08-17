import hashlib
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Request
import jwt

from app.core.database import aget_db
from app.models.user import User
from .config import settings


def hash_key(key: str) -> str:
    """Hash the key using SHA-256."""
    key = key or ""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(api_key: Optional[str] = None) -> bool:
    """
    Verify the API key hashed is the same as the one in the settings.

    Args:
        - api_key (Optional[str]): The API key to verify.
        
    Returns:
        - bool: Whether the API key is valid.
    """
    if hash_key(api_key) == settings.HASHED_API_KEY:
        return True
    return False


def create_jwt_token(data: dict, expires_delta: timedelta = timedelta(hours=1)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow()  # Add issued at time
    })
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    print("Created token:", token)  # Debug print
    return token

def decode_jwt_token(token: str):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        print("Decoded payload:", payload)  # Debug print
        return payload
    except Exception as e:
        print(f"JWT Decode Error: {str(e)}")  # Detailed error logging
        raise

async def get_current_user(request: Request, db: AsyncSession = Depends(aget_db)) -> User:
    """Helper function to get current user from token"""
    token = request.cookies.get("auth_token")
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = decode_jwt_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user