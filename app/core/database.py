"""
Enhanced Async Database Manager for PostgreSQL with SQLAlchemy
- Automatic database creation if missing
- Proper table initialization
- Render.com optimization
- Comprehensive error handling
"""
from importlib import import_module
from asyncio import current_task
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine
)
import asyncpg
from app.core.config import settings
from app.models.base import Base

class DatabaseSessionManager:
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None

    async def init(self):
        """Initialize database connection with auto-creation fallback"""
        try:
            db_url = self._ensure_ssl(settings.APOSTGRES_DATABASE_URL)
            self.engine = create_async_engine(
                db_url,
                pool_size=15,
                max_overflow=5,
                pool_timeout=30,
                pool_recycle=300,
                pool_pre_ping=True,
                echo=True,  # Enable for debugging
                connect_args={
                    "ssl": "require" if "render.com" in db_url else None,
                    "prepared_statement_cache_size": 0
                }
            )

            try:
                async with self.engine.begin() as conn:
                    await self._setup_database(conn)
            except asyncpg.exceptions.InvalidCatalogNameError:
                if not await self._create_database():
                    raise
                await self._setup_database_after_creation()

            self.session_factory = async_sessionmaker(
                bind=self.engine,
                expire_on_commit=False,
                autoflush=False
            )

        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            raise

    def _ensure_ssl(self, db_url: str) -> str:
        """Ensure SSL is properly configured for Render"""
        if "render.com" in db_url and "?ssl=" not in db_url:
            return f"{db_url}?ssl=require"
        return db_url

    async def _setup_database(self, conn):
        """Initialize database schema"""
        try:
            # Verify connection
            await conn.execute(text("SELECT 1"))
            
            # Create extension
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            
            # Import ALL models before table creation
            for model in settings.DB_MODELS:
                import_module(model)
            
            print(f"📝 Models registered: {list(Base.metadata.tables.keys())}")
            await conn.run_sync(Base.metadata.create_all)
            
            # Verify tables
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            created_tables = [row[0] for row in result]
            print(f"✅ Tables created: {created_tables}")

        except Exception as e:
            print(f"❌ Database setup failed: {e}")
            raise

    async def _setup_database_after_creation(self):
        """Reinitialize after database creation"""
        print("🔄 Setting up newly created database...")
        self.engine = create_async_engine(
            settings.APOSTGRES_DATABASE_URL,
            pool_size=15,
            max_overflow=5,
            pool_pre_ping=True,
            echo=True
        )
        async with self.engine.begin() as conn:
            await self._setup_database(conn)

    @property
    def session(self) -> async_scoped_session:
        """Scoped session for the current async task"""
        if not self.session_factory:
            raise RuntimeError("DatabaseSessionManager not initialized")
        return async_scoped_session(
            self.session_factory,
            scopefunc=current_task
        )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager for safe session handling"""
        async with self.session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def _create_database(self) -> bool:
        """Create the database if it does not exist"""
        import sqlalchemy
        from sqlalchemy.engine.url import make_url
        try:
            db_url = make_url(settings.APOSTGRES_DATABASE_URL)
            db_name = db_url.database

            print("Database URL is:", db_url )
            print("Database URL name:", db_name )

            # Connect to the default database (usually 'postgres')
            default_url = db_url.set(database="postgres")
            engine = create_async_engine(str(default_url), echo=True)
            async with engine.begin() as conn:
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            await engine.dispose()
            print(f"✅ Database '{db_name}' created successfully.")
            return True
        except Exception as e:
            print(f"❌ Failed to create database: {e}")
            return False

    async def close(self):
        """Cleanup connection pool"""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None

# Initialize session manager
session_manager = DatabaseSessionManager()

async def aget_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions
    Usage:
    @router.get("/")
    async def endpoint(db: AsyncSession = Depends(aget_db)):
        ...
    """
    async with session_manager.get_session() as session:
        yield session