from __future__ import annotations

import os
import re
import tempfile
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Literal

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tunelink_backend.audio_tags import read_audio_tags
from tunelink_backend.auth.deps import get_current_user
from tunelink_backend.config import get_settings
from tunelink_backend.covers import store_track_cover
from tunelink_backend.db import get_db
from tunelink_backend.models import ImportJob, JobStatus, MlJob, Track, TrackStatus, User
from tunelink_backend import storage

router = APIRouter()

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
_READ_CHUNK = 1024 * 1024


class TrackOut(BaseModel):
    id: uuid.UUID
    title: str
    artist: str
    original_filename: str
    content_type: str
    size_bytes: int
    status: TrackStatus
    error_message: str | None
    imported_at: datetime
    indexed_at: datetime | None
    cover_color: str | None = None
    has_cover: bool = False
    duration_s: float | None = None

    model_config = {"from_attributes": True}


class WaveformOut(BaseModel):
    duration_s: float
    samples: list[float]


class ImportJobOut(BaseModel):
    id: uuid.UUID
    original_filename: str
    status: JobStatus
    total_files: int
    processed_files: int
    failed_files: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    """Catalog job with indexing progress (ZIP import → ML index)."""

    id: str
    name: str
    phase: Literal["queued", "importing", "indexing", "complete", "failed"]
    total_files: int
    ready_files: int
    pending_files: int
    failed_files: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


def _job_phase(
    *,
    import_status: str,
    total_files: int,
    ready_files: int,
    pending_files: int,
    failed_files: int,
) -> Literal["queued", "importing", "indexing", "complete", "failed"]:
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


async def _track_counts_by_import(
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


def _allowed_extensions() -> set[str]:
    settings = get_settings()
    return {
        ext.strip().lower()
        for ext in settings.allowed_audio_extensions.split(",")
        if ext.strip()
    }


def _safe_filename(filename: str) -> str:
    name = PurePosixPath(filename.replace("\\", "/")).name
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")
    cleaned = _SAFE_FILENAME.sub("_", name).strip("._")
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")
    return cleaned[:200]


def _title_from_filename(filename: str) -> str:
    stem = PurePosixPath(filename).stem.strip() or "Untitled"
    return stem[:512]


async def _read_upload(file: UploadFile, max_bytes: int) -> bytes:
    """Buffer a small upload in memory (single tracks)."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds max size of {max_bytes} bytes",
            )
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    return b"".join(chunks)


async def _spool_upload(file: UploadFile, max_bytes: int) -> Path:
    """Stream a large upload to a temp file (ZIPs). Caller must unlink the path."""
    fd, path_str = tempfile.mkstemp(suffix=".zip")
    path = Path(path_str)
    total = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = await file.read(_READ_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds max size of {max_bytes} bytes",
                    )
                out.write(chunk)
        if total == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


@router.post(
    "/uploads",
    response_model=TrackOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="uploadTrack",
)
async def upload_track(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Track:
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename required")

    safe_name = _safe_filename(file.filename)
    suffix = PurePosixPath(safe_name).suffix.lower()
    if suffix not in _allowed_extensions():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(_allowed_extensions()))}",
        )

    content_type = file.content_type or "application/octet-stream"
    data = await _read_upload(file, settings.max_upload_bytes)
    tags = read_audio_tags(data, safe_name)

    track_id = uuid.uuid4()
    object_key = f"tracks/{track_id}/{safe_name}"

    try:
        storage.put_object(object_key, BytesIO(data), len(data), content_type)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Storage upload failed: {exc}",
        ) from exc

    track = Track(
        id=track_id,
        title=tags.title or _title_from_filename(safe_name),
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
    db.add(MlJob(track_id=track.id, status=JobStatus.QUEUED))
    await db.commit()
    await db.refresh(track)
    return track


@router.post(
    "/uploads/zip",
    response_model=ImportJobOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="uploadZip",
)
async def upload_zip(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ImportJob:
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename required")

    safe_name = _safe_filename(file.filename)
    if PurePosixPath(safe_name).suffix.lower() != ".zip":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expected a .zip file")

    job_id = uuid.uuid4()
    object_key = f"imports/{job_id}/{safe_name}"
    spool_path = await _spool_upload(file, settings.max_zip_bytes)
    try:
        storage.fput_object(
            object_key,
            str(spool_path),
            file.content_type or "application/zip",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Storage upload failed: {exc}",
        ) from exc
    finally:
        spool_path.unlink(missing_ok=True)

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


@router.get("/imports", response_model=list[ImportJobOut], operation_id="listImports")
async def list_imports(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ImportJob]:
    result = await db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()))
    return list(result)


@router.get("/jobs", response_model=list[JobOut], operation_id="listJobs")
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[JobOut]:
    imports = list(
        await db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()))
    )
    counts = await _track_counts_by_import(db)
    jobs: list[JobOut] = []

    for job in imports:
        ready, pending, failed = counts.get(job.id, (0, 0, 0))
        total = job.total_files or (ready + pending + failed)
        jobs.append(
            JobOut(
                id=str(job.id),
                name=job.original_filename,
                phase=_job_phase(
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
        from datetime import UTC

        now = datetime.now(UTC)
        jobs.append(
            JobOut(
                id="other",
                name="Other uploads",
                phase=_job_phase(
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


@router.post("/jobs/{job_id}/cancel", response_model=JobOut, operation_id="cancelJob")
async def cancel_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> JobOut:
    """Stop indexing: mark pending tracks + their ML jobs as cancelled."""
    import_job_id: uuid.UUID | None
    job_name: str
    created_at: datetime
    updated_at: datetime

    if job_id == "other":
        import_job_id = None
        job_name = "Other uploads"
        from datetime import UTC

        created_at = updated_at = datetime.now(UTC)
    else:
        try:
            import_uuid = uuid.UUID(job_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
        job = await db.scalar(select(ImportJob).where(ImportJob.id == import_uuid))
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        import_job_id = job.id
        job_name = job.original_filename
        created_at = job.created_at
        updated_at = job.updated_at
        if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
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

    track_ids = list(
        (await db.scalars(select(Track.id).where(track_filter))).all()
    )
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

    return await _job_out(db, job_id, import_job_id, job_name, created_at, updated_at)


@router.post("/jobs/{job_id}/retry-failed", response_model=JobOut, operation_id="retryFailedJob")
async def retry_failed_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> JobOut:
    """Re-queue failed tracks for indexing (skips Cancelled)."""
    import_job_id: uuid.UUID | None
    job_name: str
    created_at: datetime
    updated_at: datetime

    if job_id == "other":
        import_job_id = None
        job_name = "Other uploads"
        from datetime import UTC

        created_at = updated_at = datetime.now(UTC)
    else:
        try:
            import_uuid = uuid.UUID(job_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
        job = await db.scalar(select(ImportJob).where(ImportJob.id == import_uuid))
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        import_job_id = job.id
        job_name = job.original_filename
        created_at = job.created_at
        updated_at = job.updated_at

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

    return await _job_out(db, job_id, import_job_id, job_name, created_at, updated_at)


async def _job_out(
    db: AsyncSession,
    job_id: str,
    import_job_id: uuid.UUID | None,
    job_name: str,
    created_at: datetime,
    updated_at: datetime,
) -> JobOut:
    counts = await _track_counts_by_import(db)
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
        phase=_job_phase(
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


@router.get("/imports/{import_id}", response_model=ImportJobOut, operation_id="getImport")
async def get_import(
    import_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ImportJob:
    job = await db.scalar(select(ImportJob).where(ImportJob.id == import_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")
    return job


@router.get("/tracks", response_model=list[TrackOut], operation_id="listTracks")
async def list_tracks(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    q: str | None = Query(default=None, max_length=200),
    status_filter: TrackStatus | None = Query(default=None, alias="status"),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> list[Track]:
    stmt = select(Track)
    if status_filter is not None:
        stmt = stmt.where(Track.status == status_filter)
    query = (q or "").strip()
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                Track.title.ilike(pattern),
                Track.artist.ilike(pattern),
            )
        )
    stmt = stmt.order_by(Track.imported_at.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await db.scalars(stmt)
    return list(result)


@router.get("/tracks/{track_id}", response_model=TrackOut, operation_id="getTrack")
async def get_track(
    track_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Track:
    track = await db.scalar(select(Track).where(Track.id == track_id))
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
    return track


@router.get("/tracks/{track_id}/cover", operation_id="getTrackCover")
async def get_track_cover(
    track_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Response:
    track = await db.scalar(select(Track).where(Track.id == track_id))
    if track is None or not track.cover_object_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover not found")
    try:
        data, content_type = storage.get_object_bytes(track.cover_object_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cover storage failed: {exc}",
        ) from exc
    return Response(content=data, media_type=content_type)


@router.get("/tracks/{track_id}/audio", operation_id="getTrackAudio")
async def get_track_audio(
    track_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    range_header: str | None = Header(default=None, alias="Range"),
) -> StreamingResponse:
    track = await db.scalar(select(Track).where(Track.id == track_id))
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
    try:
        opened = storage.open_object(track.object_key, range_header)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Audio storage failed: {exc}",
        ) from exc

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(opened.content_length),
    }
    if opened.content_range:
        headers["Content-Range"] = opened.content_range

    def iter_stream():
        try:
            yield from opened.stream.stream(1024 * 64)
        finally:
            opened.stream.close()
            opened.stream.release_conn()

    return StreamingResponse(
        iter_stream(),
        status_code=opened.status_code,
        media_type=track.content_type or opened.content_type,
        headers=headers,
    )


@router.get(
    "/tracks/{track_id}/waveform",
    response_model=WaveformOut,
    operation_id="getTrackWaveform",
)
async def get_track_waveform(
    track_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> WaveformOut:
    track = await db.scalar(select(Track).where(Track.id == track_id))
    if track is None or not track.analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waveform not found")
    waveform = track.analysis.get("waveform") or {}
    samples = waveform.get("samples")
    if not isinstance(samples, list) or not samples:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waveform not found")
    duration = waveform.get("duration_s")
    if duration is None:
        duration = track.analysis.get("duration_s")
    if duration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waveform not found")
    return WaveformOut(
        duration_s=float(duration),
        samples=[float(value) for value in samples],
    )
