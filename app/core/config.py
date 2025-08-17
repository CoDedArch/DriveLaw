import os
import hashlib
import logging
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import ClassVar, List, Dict, Any

load_dotenv(".env", override=True)
logger = logging.getLogger(__name__)


def hash_key(key: str) -> str:
    """Hash the key using SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()


class Settings(BaseSettings):
    """Class to store all the settings of the application."""

    APOSTGRES_DATABASE_URL: str = Field(env="APOSTGRES_DATABASE_URL")
    HASHED_API_KEY: str = Field(env="HASHED_API_KEY")
    OPENAI_API_KEY: str = Field(env="OPENAI_API_KEY")
    AWS_ACCESS_KEY_ID: str = Field(env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str = Field(env="AWS_SECRET_ACCESS_KEY")
    SENDGRID_API_KEY: str = Field(env="SENDGRID_API_KEY")
    FROM_EMAIL: str = Field(env="FROM_EMAIL")
    AWS_REGION: str = Field(env="AWS_REGION")
    AWS_S3_BUCKET: str = Field(env="AWS_S3_BUCKET")
    AWS_S3_BASE_URL: str = Field(env="AWS_S3_BASE_URL")
    SECRET_KEY: str = Field(env="SECRET_KEY")
    ALGORITHM: str = Field(env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(env="ACCESS_TOKEN_EXPIRE", default=30)
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "no-reply@versecatch.pro")
    BASE_URL: str = os.getenv("BASE_URL")
    PAYSTACK_SECRET_KEY: str = os.getenv("PAYSTACK_SECRET_KEY")
    ARKESEL_API_KEY: str = os.getenv("ARKESEL_API_KEY")
    ARKESEL_SENDER_ID: str = os.getenv("ARKESEL_SENDER_ID")
    DATA_DIR: str = Field(default="../../data",env="DATA_DIR")
    SEED_ON_STARTUP: bool = Field(True, env="SEED_ON_STARTUP")
    FORCE_SEED: bool = Field(False, env="FORCE_SEED")  # Ignore existing data
    REQUIRE_SEED: bool = Field(False, env="REQUIRE_SEED")  # Crash if seeding fails
    DB_MODELS: ClassVar[List[str]] = [
        "app.models.notification",
        "app.models.payment",
        "app.models.user",
        "app.models.appeals",
        "app.models.offenses"
    ]
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()