# from sqlalchemy import select, func
# from app.models.document import PermitTypeModel, DocumentTypeModel
# from app.services.Zoning_initializer import ZoningInitializer
# from app.services.applicant_type_initializer import ApplicantTypeInitializer
# from app.services.mmda_initializer import MMDAInitializer
# from app.services.permit_initializer import PermitSystemInitializer
# from app.services.previous_land_initializer import PreviousLandUseSeeder
# from app.services.indentureInitializer import IndentureInitializer
# from app.services.site_condition_drainage_initializer import SiteConditionAndDrainageInitializer
# from app.core.config import settings
# import logging
# from sqlalchemy.ext.asyncio import AsyncSession

# logger = logging.getLogger(__name__)

# async def seed_all(db: AsyncSession) -> bool:
#     """Orchestrate all database seeding operations with external session management"""
#     try:
#         # Check if seeding is needed
#         if not await needs_seeding(db):
#             logger.info("⏩ Database already seeded, skipping")
#             return False
            
#         logger.info("🚀 Starting database seeding process...")
        
        
#         # 1. Seed document types and requirements
#         await PermitSystemInitializer.initialize_document_types(db)
#         await PermitSystemInitializer.initialize_permit_types(db)
#         await PermitSystemInitializer.initialize_permit_requirements(db)

#         #2 seed Site Conditions and Drainage types
#         await SiteConditionAndDrainageInitializer.initialize(db)
        
#         # 3. Seed zoning districts
#         await ApplicantTypeInitializer.initialize(db)
#         # 4. Seed zoning districts
#         await ZoningInitializer.initialize_zoning_districts(db)

#         await IndentureInitializer.initialize_all(db)
        
#         await PreviousLandUseSeeder.seed(db)
#         #5. Seed MMDA, Departments, and Committees
#         await MMDAInitializer.initialize_mmdas(db)
#         # Commit is handled by the caller
#         logger.info("✅ Seeding operations completed (commit pending)")
#         return True
            
#     except Exception as e:
#         logger.error(f"🔥 Seeding failed: {e}")
#         # Rollback should be handled by the caller
#         raise

    
# async def needs_seeding(db: AsyncSession) -> bool:
#     """Check if seeding is required"""
#     # Check if permit types exist
#     result = await db.execute(select(func.count(PermitTypeModel.id)))
#     permit_count = result.scalar()
    
#     # Check if document types exist
#     result = await db.execute(select(func.count(DocumentTypeModel.id)))
#     doc_count = result.scalar()
    
#     return permit_count == 0 or doc_count == 0 or settings.FORCE_SEED

# async def seed_permit_types(db: AsyncSession):
#     """Seed permit types only"""  
#     logger.info("⏳ Seeding permit types...")
#     await PermitTypeModel.seed_defaults(db)
#     logger.info("✅ Permit types seeded")