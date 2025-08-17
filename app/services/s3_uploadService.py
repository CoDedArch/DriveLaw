# app/utils/s3_upload.py

from typing import Optional
import uuid
import boto3
from fastapi import UploadFile
from slugify import slugify
from app.core.config import settings

s3 = boto3.client(
    "s3",
    region_name=settings.AWS_REGION,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)


def upload_file_to_s3(file: UploadFile, folder: str = "uploads", username: Optional[str] = None) -> str:
    file_ext = file.filename.split(".")[-1]
    base_name = ".".join(file.filename.split(".")[:-1])
    safe_name = slugify(base_name)

    # Add username or default fallback
    user_segment = slugify(username) if username else "anonymous"

    unique_filename = f"{folder}/{user_segment}/{safe_name}-{uuid.uuid4()}.{file_ext}"

    s3.upload_fileobj(
        file.file,
        settings.AWS_S3_BUCKET,
        unique_filename,
        ExtraArgs={"ContentType": file.content_type},
    )

    return f"{settings.AWS_S3_BASE_URL}{unique_filename}"

