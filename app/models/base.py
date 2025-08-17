from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, DateTime
from datetime import datetime

Base = declarative_base()
Base.metadata.info['custom'] = 'custom_metadata'

class TimestampMixin:
    """Mixin for timestamp columns"""
    __abstract__ = True
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

__all__ = ["Base"]