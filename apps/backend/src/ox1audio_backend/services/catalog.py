from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from io import BytesIO
from pathlib import PurePosixPath
from typing import Literal

from sqlalchemy import Float, and_, cast, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ox1audio_backend import storage
from ox1audio_backend.config import get_settings
from ox1audio_backend.exceptions import AppError
from ox1audio_backend.ingest.audio_tags import EmbeddedCover, read_audio_tags
from ox1audio_backend.models import ImportJob, JobStatus, MlJob, Track, TrackArtist, TrackStatus
from ox1audio_backend.schemas.tracks import JobOut, TrackListOut, WaveformOut
from ox1audio_backend.services import artists as artist_svc
from ox1audio_backend.services import tracks as track_svc
from ox1audio_backend.services.covers import store_track_cover
from ox1audio_backend.services.track_search import (
    metadata_relevance_expr,
    track_metadata_match_clause,
)
from ox1audio_backend.shared_constants import ALLOWED_IMAGE_MIME_TYPES

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
_COVER_TYPES = set(ALLOWED_IMAGE_MIME_TYPES) | {"image/jpg"}

TrackSort = Literal["imported_at", "duration", "title", "artist"]
SortOrder = Literal["asc", "desc"]
JobPhase = Literal["queued", "importing", "indexing", "complete", "failed"]


class CatalogError(AppError):
    pass


def allowed_extensions() -> set[str]:
    settings = get_settings()
    return {
        ext.strip().lower()
        for ext in settings.allowed_audio_extensions.split(",")
        if ext.strip()
    }


def safe_filename(filename: str) -> str:
    name = PurePosixPath(filename.replace("\\", "/")).name
    if not name or name in {".", ".."}:
        raise CatalogError("Invalid filename")
    cleaned = _SAFE_FILENAME.sub("_", name).strip("._")
    if not cleaned:
        raise CatalogError("Invalid filename")
    return cleaned[:200]


def title_from_filename(filename: str) -> str:
    stem = PurePosixPath(filename).stem.strip() or "Untitled"
    return stem[:512]


def job_phase(
    *,
    import_status: str,
    total_files: int,
    ready_files: int,
    pending_files: int,
    failed_files: int,
) -> JobPhase:
    if import_status == JobStatus.QUEUED:
        return "queued"
    if import_status == JobStatus.RUNNING:
        return "importing"
    if import_status == JobStatus.FAILED and ready_files == 0 and pending_files == 0:
        return "failed"
    if pending_files > 0:
        return "indexing"
    if total_files > 0 and ready_files == 0 and failed_files >= total_files:
        return "failed"
    return "complete"


async def track_counts_by_import(
    db: AsyncSession,
) -> dict[uuid.UUID | None, tuple[int, int, int]]:
    """Map import_job_id → (ready, pending, failed)."""
    rows = await db.execute(
        select(
            Track.import_job_id,
            func.count()
            .filter(Track.status == TrackStatus.READY)
            .label("ready"),
            func.count()
            .filter(
                Track.status.in_(
                    [TrackStatus.UPLOADING, TrackStatus.QUEUED, TrackStatus.INDEXING]
                )
            )
            .label("pending"),
            func.count()
            .filter(Track.status == TrackStatus.FAILED)
            .label("failed"),
        ).group_by(Track.import_job_id)
    )
    return {
        import_job_id: (int(ready), int(pending), int(failed))
        for import_job_id, ready, pending, failed in rows.all()
    }


def track_filters(
    *,
    q: str | None,
    artist: str | None,
    artist_id: uuid.UUID | None,
    status_filter: TrackStatus | None,
):
    filters = []
    if status_filter is not None:
        filters.append(Track.status == status_filter)
    query = (q or "").strip()
    if query:
        clause = track_metadata_match_clause(query)
        if clause is not None:
            filters.append(clause)
    artist_query = (artist or "").strip()
    if artist_query:
        filters.append(Track.artist.ilike(f"%{artist_query}%"))
    if artist_id is not None:
        filters.append(
            Track.id.in_(
                select(TrackArtist.track_id).where(TrackArtist.artist_id == artist_id)
            )
        )
    return filters


def track_order(sort: TrackSort, order: SortOrder):
    ascending = order == "asc"
    if sort == "duration":
        duration = cast(Track.analysis["duration_s"].astext, Float)
        column = duration.asc().nulls_last() if ascending else duration.desc().nulls_last()
        return column, Track.imported_at.desc()
    if sort == "title":
        column = Track.title.asc() if ascending else Track.title.desc()
        return column, Track.imported_at.desc()
    if sort == "artist":
        column = Track.artist.asc() if ascending else Track.artist.desc()
        return column, Track.imported_at.desc()
    column = Track.imported_at.asc() if ascending else Track.imported_at.desc()
    return (column,)


async def list_jobs(db: AsyncSession) -> list[JobOut]:
    imports = list(
        await db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()))
    )
    counts = await track_counts_by_import(db)
    jobs: list[JobOut] = []

    for job in imports:
        ready, pending, failed = counts.get(job.id, (0, 0, 0))
        total = job.total_files or (ready + pending + failed)
        jobs.append(
            JobOut(
                id=str(job.id),
                name=job.original_filename,
                phase=job_phase(
                    import_status=job.status,
                    total_files=total,
                    ready_files=ready,
                    pending_files=pending,
                    failed_files=failed,
                ),
                total_files=total,
                ready_files=ready,
                pending_files=pending,
                failed_files=failed,
                error_message=job.error_message,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
        )

    ready, pending, failed = counts.get(None, (0, 0, 0))
    other_total = ready + pending + failed
    if other_total > 0:
        now = datetime.now(UTC)
        jobs.append(
            JobOut(
                id="other",
                name="Other uploads",
                phase=job_phase(
                    import_status=JobStatus.COMPLETE,
                    total_files=other_total,
                    ready_files=ready,
                    pending_files=pending,
                    failed_files=failed,
                ),
                total_files=other_total,
                ready_files=ready,
                pending_files=pending,
                failed_files=failed,
                error_message=None,
                created_at=min((j.created_at for j in imports), default=now),
                updated_at=max((j.updated_at for j in imports), default=now),
            )
        )

    return jobs


async def job_out(
    db: AsyncSession,
    job_id: str,
    import_job_id: uuid.UUID | None,
    job_name: str,
    created_at: datetime,
    updated_at: datetime,
) -> JobOut:
    counts = await track_counts_by_import(db)
    ready, pending, failed = counts.get(import_job_id, (0, 0, 0))
    total = ready + pending + failed
    import_status = JobStatus.COMPLETE
    error_message: str | None = None

    if import_job_id is not None:
        job_row = await db.scalar(select(ImportJob).where(ImportJob.id == import_job_id))
        if job_row is not None:
            total = job_row.total_files or total
            updated_at = job_row.updated_at
            error_message = job_row.error_message
            import_status = JobStatus(job_row.status)

    return JobOut(
        id=job_id,
        name=job_name,
        phase=job_phase(
            import_status=import_status,
            total_files=total,
            ready_files=ready,
            pending_files=pending,
            failed_files=failed,
        ),
        total_files=total,
        ready_files=ready,
        pending_files=pending,
        failed_files=failed,
        error_message=error_message,
        created_at=created_at,
        updated_at=updated_at,
    )


async def resolve_job_scope(
    db: AsyncSession, job_id: str
) -> tuple[uuid.UUID | None, str, datetime, datetime]:
    if job_id == "other":
        now = datetime.now(UTC)
        return None, "Other uploads", now, now

    try:
        import_uuid = uuid.UUID(job_id)
    except ValueError as exc:
        raise CatalogError("Job not found", status_code=404) from exc

    job = await db.scalar(select(ImportJob).where(ImportJob.id == import_uuid))
    if job is None:
        raise CatalogError("Job not found", status_code=404)
    return job.id, job.original_filename, job.created_at, job.updated_at


async def cancel_job(db: AsyncSession, job_id: str) -> JobOut:
    """Stop indexing: mark pending tracks + their ML jobs as cancelled."""
    import_job_id, job_name, created_at, updated_at = await resolve_job_scope(db, job_id)

    if import_job_id is not None:
        job = await db.scalar(select(ImportJob).where(ImportJob.id == import_job_id))
        if job is not None and job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
            job.status = JobStatus.FAILED
            job.error_message = "Cancelled"

    pending_statuses = [TrackStatus.UPLOADING, TrackStatus.QUEUED, TrackStatus.INDEXING]
    if import_job_id is None:
        track_filter = and_(Track.status.in_(pending_statuses), Track.import_job_id.is_(None))
    else:
        track_filter = and_(
            Track.status.in_(pending_statuses),
            Track.import_job_id == import_job_id,
        )

    track_ids = list((await db.scalars(select(Track.id).where(track_filter))).all())
    if track_ids:
        await db.execute(
            update(Track)
            .where(Track.id.in_(track_ids))
            .values(status=TrackStatus.FAILED, error_message="Cancelled")
        )
        await db.execute(
            update(MlJob)
            .where(
                MlJob.track_id.in_(track_ids),
                MlJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
            .values(status=JobStatus.FAILED, error_message="Cancelled")
        )
    await db.commit()
    return await job_out(db, job_id, import_job_id, job_name, created_at, updated_at)


async def retry_failed_job(db: AsyncSession, job_id: str) -> JobOut:
    """Re-queue failed tracks for indexing (skips Cancelled)."""
    import_job_id, job_name, created_at, updated_at = await resolve_job_scope(db, job_id)

    if import_job_id is None:
        track_scope = Track.import_job_id.is_(None)
    else:
        track_scope = Track.import_job_id == import_job_id

    track_ids = list(
        (
            await db.scalars(
                select(Track.id).where(
                    track_scope,
                    Track.status == TrackStatus.FAILED,
                    or_(
                        Track.error_message.is_(None),
                        Track.error_message != "Cancelled",
                    ),
                )
            )
        ).all()
    )
    if track_ids:
        await db.execute(
            update(Track)
            .where(Track.id.in_(track_ids))
            .values(status=TrackStatus.QUEUED, error_message=None)
        )
        await db.execute(
            update(MlJob)
            .where(
                MlJob.track_id.in_(track_ids),
                MlJob.status == JobStatus.FAILED,
                or_(
                    MlJob.error_message.is_(None),
                    MlJob.error_message != "Cancelled",
                ),
            )
            .values(
                status=JobStatus.QUEUED,
                attempt_count=0,
                available_at=None,
                error_message=None,
            )
        )
    await db.commit()
    return await job_out(db, job_id, import_job_id, job_name, created_at, updated_at)


async def upload_track(
    db: AsyncSession,
    *,
    filename: str,
    content_type: str,
    data: bytes,
) -> Track:
    safe_name = safe_filename(filename)
    suffix = PurePosixPath(safe_name).suffix.lower()
    allowed = allowed_extensions()
    if suffix not in allowed:
        raise CatalogError(
            f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(allowed))}"
        )

    tags = read_audio_tags(data, safe_name)
    track_id = uuid.uuid4()
    object_key = f"tracks/{track_id}/{safe_name}"

    try:
        storage.put_object(object_key, BytesIO(data), len(data), content_type)
    except Exception as exc:
        raise CatalogError(f"Storage upload failed: {exc}", status_code=502) from exc

    track = Track(
        id=track_id,
        title=tags.title or title_from_filename(safe_name),
        artist=tags.artist or "",
        original_filename=safe_name,
        object_key=object_key,
        content_type=content_type,
        size_bytes=len(data),
        status=TrackStatus.QUEUED,
    )
    if tags.cover is not None:
        cover_key, cover_color = store_track_cover(track_id, tags.cover)
        track.cover_object_key = cover_key
        track.cover_color = cover_color
    db.add(track)
    await db.flush()
    await artist_svc.link_artists_from_tags(db, track, tags.artists)
    db.add(MlJob(track_id=track.id, status=JobStatus.QUEUED))
    await db.commit()
    await db.refresh(track)
    return track


async def upload_zip(
    db: AsyncSession,
    *,
    filename: str,
    content_type: str,
    spool_path: str,
) -> ImportJob:
    safe_name = safe_filename(filename)
    if PurePosixPath(safe_name).suffix.lower() != ".zip":
        raise CatalogError("Expected a .zip file")

    job_id = uuid.uuid4()
    object_key = f"imports/{job_id}/{safe_name}"
    try:
        storage.fput_object(object_key, spool_path, content_type)
    except Exception as exc:
        raise CatalogError(f"Storage upload failed: {exc}", status_code=502) from exc

    job = ImportJob(
        id=job_id,
        object_key=object_key,
        original_filename=safe_name,
        status=JobStatus.QUEUED,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def list_tracks(
    db: AsyncSession,
    *,
    q: str | None = None,
    artist: str | None = None,
    artist_id: uuid.UUID | None = None,
    status_filter: TrackStatus | None = None,
    sort: TrackSort = "imported_at",
    order: SortOrder = "desc",
    limit: int = 50,
    offset: int = 0,
) -> TrackListOut:
    filters = track_filters(
        q=q, artist=artist, artist_id=artist_id, status_filter=status_filter
    )
    count_stmt = select(func.count()).select_from(Track)
    list_stmt = select(Track)
    if filters:
        count_stmt = count_stmt.where(and_(*filters))
        list_stmt = list_stmt.where(and_(*filters))
    total = int(await db.scalar(count_stmt) or 0)
    query = (q or "").strip()
    if query:
        order_by = (
            metadata_relevance_expr(query).desc(),
            *track_order(sort, order),
        )
    else:
        order_by = track_order(sort, order)
    rows = list(
        await db.scalars(list_stmt.order_by(*order_by).offset(offset).limit(limit))
    )
    return TrackListOut(
        items=await track_svc.tracks_out(db, rows),
        total=total,
        limit=limit,
        offset=offset,
    )


async def update_track(
    db: AsyncSession,
    track_id: uuid.UUID,
    *,
    title: str | None = None,
    artist_ids: list[uuid.UUID] | None = None,
) -> Track:
    track = await db.scalar(select(Track).where(Track.id == track_id))
    if track is None:
        raise CatalogError("Track not found", status_code=404)
    if title is not None:
        cleaned = title.strip()
        if not cleaned:
            raise CatalogError("Title required")
        track.title = cleaned[:512]
    if artist_ids is not None:
        try:
            await artist_svc.set_track_artists(db, track, artist_ids)
        except artist_svc.ArtistError as exc:
            raise CatalogError(exc.message, status_code=exc.status_code) from exc
    await db.commit()
    await db.refresh(track)
    return track


async def update_track_cover(
    db: AsyncSession,
    track_id: uuid.UUID,
    *,
    data: bytes,
    content_type: str,
) -> Track:
    track = await db.scalar(select(Track).where(Track.id == track_id))
    if track is None:
        raise CatalogError("Track not found", status_code=404)

    normalized = content_type.lower()
    if normalized == "image/jpg":
        normalized = "image/jpeg"
    if normalized not in _COVER_TYPES:
        raise CatalogError("Cover must be JPEG, PNG, or WebP")

    cover_key, cover_color = store_track_cover(
        track_id,
        EmbeddedCover(data=data, content_type=normalized),
    )
    if track.cover_object_key and track.cover_object_key != cover_key:
        storage.remove_object(track.cover_object_key)
    track.cover_object_key = cover_key
    track.cover_color = cover_color
    await db.commit()
    await db.refresh(track)
    return track


async def get_track_or_404(db: AsyncSession, track_id: uuid.UUID) -> Track:
    track = await db.scalar(select(Track).where(Track.id == track_id))
    if track is None:
        raise CatalogError("Track not found", status_code=404)
    return track


async def get_import_or_404(db: AsyncSession, import_id: uuid.UUID) -> ImportJob:
    job = await db.scalar(select(ImportJob).where(ImportJob.id == import_id))
    if job is None:
        raise CatalogError("Import not found", status_code=404)
    return job


def waveform_out(track: Track) -> WaveformOut:
    if not track.analysis:
        raise CatalogError("Waveform not found", status_code=404)
    waveform = track.analysis.get("waveform") or {}
    samples = waveform.get("samples")
    if not isinstance(samples, list) or not samples:
        raise CatalogError("Waveform not found", status_code=404)
    duration = waveform.get("duration_s")
    if duration is None:
        duration = track.analysis.get("duration_s")
    if duration is None:
        raise CatalogError("Waveform not found", status_code=404)
    return WaveformOut(
        duration_s=float(duration),
        samples=[float(value) for value in samples],
    )
