from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from tunelink_backend.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from tunelink_backend import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "role VARCHAR(32) NOT NULL DEFAULT 'user'"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE tracks ADD COLUMN IF NOT EXISTS "
                "import_job_id UUID REFERENCES import_jobs(id) ON DELETE SET NULL"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_tracks_import_job_id "
                "ON tracks (import_job_id)"
            )
        )
        await conn.execute(
            text("ALTER TABLE tracks ADD COLUMN IF NOT EXISTS cover_object_key VARCHAR(1024)")
        )
        await conn.execute(
            text("ALTER TABLE tracks ADD COLUMN IF NOT EXISTS cover_color VARCHAR(16)")
        )
        await conn.execute(
            text(
                "ALTER TABLE ml_jobs ADD COLUMN IF NOT EXISTS "
                "attempt_count INTEGER NOT NULL DEFAULT 0"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE ml_jobs ADD COLUMN IF NOT EXISTS "
                "available_at TIMESTAMPTZ"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_ml_jobs_available_at "
                "ON ml_jobs (available_at)"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS "
                "playlist_ids JSONB"
            )
        )
        # Best-effort backfill: attach unassigned tracks to import jobs by time window.
        await conn.execute(
            text(
                """
                UPDATE tracks AS t
                SET import_job_id = j.id
                FROM import_jobs AS j
                WHERE t.import_job_id IS NULL
                  AND t.imported_at >= j.created_at
                  AND t.imported_at <= j.updated_at + INTERVAL '10 minutes'
                """
            )
        )
