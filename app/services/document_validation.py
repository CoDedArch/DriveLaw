from sqlalchemy import exists
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.constants import DocumentType
from app.models.document import DocumentTypeModel

class DocumentValidator:
    @classmethod
    async def is_valid_document_type(cls, value: str, db_session: AsyncSession) -> bool:
        # Check if in enum
        if value in DocumentType._value2member_map_:
            return True
        
        # Check database for custom types
        result = await db_session.execute(
            exists().where(
                DocumentTypeModel.name == value,
                DocumentTypeModel.is_active == True
            ).select()
        )
        return result.scalar()