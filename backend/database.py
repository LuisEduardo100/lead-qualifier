from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from backend.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def migrate_db():
    """Adds new columns to existing Channel table without dropping data (SQLite safe)."""
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA table_info(channels)"))
        existing_cols = {row[1] for row in result}
        new_cols = [
            ("channel_type", "ALTER TABLE channels ADD COLUMN channel_type VARCHAR(30) DEFAULT 'baileys'"),
            ("wa_token", "ALTER TABLE channels ADD COLUMN wa_token VARCHAR(500)"),
            ("wa_phone_number_id", "ALTER TABLE channels ADD COLUMN wa_phone_number_id VARCHAR(50)"),
            ("wa_business_id", "ALTER TABLE channels ADD COLUMN wa_business_id VARCHAR(50)"),
        ]
        for col_name, sql in new_cols:
            if col_name not in existing_cols:
                await conn.execute(text(sql))
        await conn.commit()
