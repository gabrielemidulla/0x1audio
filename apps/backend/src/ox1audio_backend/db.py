from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ox1audio_backend.config import get_settings


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
    """Bootstrap schema for local/dev.

    Models drive table/column creation via create_all. Extensions and functional
    indexes that SQLAlchemy cannot express are applied here (and mirrored in the
    Alembic baseline for greenfield installs). Existing DBs: `alembic stamp head`.
    """
    from ox1audio_backend import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Functional unique index on lower(artists.name) — not expressible on the model.
        index_row = await conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND indexname = 'uq_artists_name_lower'"
            )
        )
        indexdef = index_row.scalar()
        if indexdef is None or "lower(artists.name)" not in indexdef:
            await conn.execute(text("DROP INDEX IF EXISTS uq_artists_name_lower"))
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX uq_artists_name_lower "
                    "ON artists (lower(artists.name))"
                )
            )

        # Typo-tolerant metadata search (catalog q= / search_metadata tool).
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_tracks_title_trgm "
                "ON tracks USING gin (title gin_trgm_ops)"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_tracks_artist_trgm "
                "ON tracks USING gin (artist gin_trgm_ops)"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_artists_name_trgm "
                "ON artists USING gin (name gin_trgm_ops)"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_ml_jobs_available_at "
                "ON ml_jobs (available_at)"
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
