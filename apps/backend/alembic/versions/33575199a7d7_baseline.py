"""baseline

Revision ID: 33575199a7d7
Revises:
Create Date: 2026-07-19

Existing databases that already have schema from init_db()/create_all should run:
  alembic stamp head

Greenfield installs: run upgrade after create_all (or rely on init_db for bootstrap).
This revision applies extensions and functional indexes that create_all cannot express.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "33575199a7d7"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tables/columns come from SQLAlchemy models (create_all / future autogenerate).
    # Keep only DDL that models cannot express.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_artists_name_lower "
        "ON artists (lower(artists.name))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tracks_title_trgm "
        "ON tracks USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tracks_artist_trgm "
        "ON tracks USING gin (artist gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_artists_name_trgm "
        "ON artists USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ml_jobs_available_at "
        "ON ml_jobs (available_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ml_jobs_available_at")
    op.execute("DROP INDEX IF EXISTS ix_artists_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_tracks_artist_trgm")
    op.execute("DROP INDEX IF EXISTS ix_tracks_title_trgm")
    op.execute("DROP INDEX IF EXISTS uq_artists_name_lower")
