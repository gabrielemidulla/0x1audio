from __future__ import annotations

import asyncio
import logging
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import PurePosixPath

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tunelink_backend.audio_tags import read_audio_tags
from tunelink_backend.config import get_settings
from tunelink_backend.covers import store_track_cover
from tunelink_backend.db import SessionLocal, init_db
from tunelink_backend.ingest.retry import (
    MAX_ML_ATTEMPTS,
    backoff_seconds,
    is_permanent_ml_error,
)
from tunelink_backend.ingest.zip_safe import SafeAudioZip, ZipSafetyError
from tunelink_backend.models import ImportJob, JobStatus, MlJob, Track, TrackStatus
from tunelink_backend import storage

logger = logging.getLogger(__name__)


def _allowed_extensions() -> set[str]:
    settings = get_settings()
    return {
        ext.strip().lower()
        for ext in settings.allowed_audio_extensions.split(",")
        if ext.strip()
    }


def _title_from_filename(filename: str) -> str:
    stem = PurePosixPath(filename).stem.strip() or "Untitled"
    return stem[:512]


async def claim_next_import_job(session: AsyncSession) -> ImportJob | None:
    result = await session.execute(
        select(ImportJob)
        .where(ImportJob.status == JobStatus.QUEUED)
        .order_by(ImportJob.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None
    job.status = JobStatus.RUNNING
    job.error_message = None
    await session.commit()
    await session.refresh(job)
    return job


async def process_import_job(session: AsyncSession, job: ImportJob) -> None:
    settings = get_settings()
    try:
        if not storage.object_exists(job.object_key):
            raise FileNotFoundError(f"Archive missing: {job.object_key}")

        with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
            storage.fget_object(job.object_key, tmp.name)
            with SafeAudioZip(
                tmp.name,
                allowed_extensions=_allowed_extensions(),
                max_files=settings.max_zip_files,
                max_uncompressed_bytes=settings.max_zip_uncompressed_bytes,
                max_file_bytes=settings.max_upload_bytes,
            ) as archive:
                job.total_files = archive.total_files
                job.processed_files = 0
                job.failed_files = 0
                await session.commit()

                # One entry in memory at a time: extract → tag → MinIO → track + ml_job.
                for entry in archive:
                    track_id = uuid.uuid4()
                    object_key = f"tracks/{track_id}/{entry.safe_filename}"
                    tags = read_audio_tags(entry.data, entry.safe_filename)
                    try:
                        storage.put_object(
                            object_key,
                            BytesIO(entry.data),
                            len(entry.data),
                            entry.content_type,
                        )
                        track = Track(
                            id=track_id,
                            title=tags.title or _title_from_filename(entry.safe_filename),
                            artist=tags.artist or "",
                            original_filename=entry.safe_filename,
                            object_key=object_key,
                            content_type=entry.content_type,
                            size_bytes=len(entry.data),
                            status=TrackStatus.QUEUED,
                            import_job_id=job.id,
                        )
                        if tags.cover is not None:
                            cover_key, cover_color = store_track_cover(track_id, tags.cover)
                            track.cover_object_key = cover_key
                            track.cover_color = cover_color
                        session.add(track)
                        await session.flush()
                        session.add(MlJob(track_id=track.id, status=JobStatus.QUEUED))
                        job.processed_files += 1
                    except Exception:
                        logger.exception(
                            "import_job %s failed on file %s", job.id, entry.safe_filename
                        )
                        job.failed_files += 1
                    await session.commit()

        if job.processed_files == 0:
            job.status = JobStatus.FAILED
            job.error_message = "No files were imported"
        else:
            job.status = JobStatus.COMPLETE
            job.error_message = None
            storage.remove_object(job.object_key)
        await session.commit()
        logger.info(
            "import_job %s complete processed=%s failed=%s",
            job.id,
            job.processed_files,
            job.failed_files,
        )
    except (ZipSafetyError, FileNotFoundError, OSError) as exc:
        logger.warning("import_job %s failed: %s", job.id, exc)
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
        await session.commit()
    except Exception as exc:
        logger.exception("import_job %s failed", job.id)
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
        await session.commit()


async def claim_next_ml_job(session: AsyncSession) -> MlJob | None:
    now = datetime.now(UTC)
    result = await session.execute(
        select(MlJob)
        .where(MlJob.status == JobStatus.QUEUED)
        .where(or_(MlJob.available_at.is_(None), MlJob.available_at <= now))
        .order_by(MlJob.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None

    job.status = JobStatus.RUNNING
    job.attempt_count += 1
    job.available_at = None
    track = await session.scalar(select(Track).where(Track.id == job.track_id))
    if track is not None:
        track.status = TrackStatus.INDEXING
        track.error_message = None
    await session.commit()
    await session.refresh(job)
    return job


async def process_ml_job(session: AsyncSession, job: MlJob) -> None:
    from tunelink_backend.ml_client import get_ml_client

    track = await session.scalar(select(Track).where(Track.id == job.track_id))
    if track is None:
        job.status = JobStatus.FAILED
        job.error_message = "Track missing"
        await session.commit()
        return

    client = get_ml_client()
    try:
        if not storage.object_exists(track.object_key):
            raise FileNotFoundError(f"Object missing: {track.object_key}")

        result = client.analyze_track(
            job_id=str(job.id),
            track_id=str(track.id),
            audio_url=storage.presigned_get_url(track.object_key),
            filename=track.original_filename,
        )
        track.analysis = result.analysis
        track.model_provider = result.model_provider
        track.model_version = result.model_version
        track.status = TrackStatus.READY
        track.indexed_at = datetime.now(UTC)
        track.error_message = None
        job.status = JobStatus.COMPLETE
        job.error_message = None
        await session.commit()
        logger.info("ml_job %s complete for track %s", job.id, track.id)
    except Exception as exc:
        message = str(exc)
        permanent = is_permanent_ml_error(exc)
        can_retry = not permanent and job.attempt_count < MAX_ML_ATTEMPTS
        if can_retry:
            delay = backoff_seconds(job.attempt_count)
            logger.warning(
                "ml_job %s attempt %s/%s failed, retry in %ss: %s",
                job.id,
                job.attempt_count,
                MAX_ML_ATTEMPTS,
                delay,
                message,
            )
            track.status = TrackStatus.QUEUED
            track.error_message = None
            job.status = JobStatus.QUEUED
            job.error_message = message
            job.available_at = datetime.now(UTC) + timedelta(seconds=delay)
        else:
            logger.exception("ml_job %s failed", job.id)
            track.status = TrackStatus.FAILED
            track.error_message = message
            job.status = JobStatus.FAILED
            job.error_message = message
            job.available_at = None
        await session.commit()
    finally:
        client.close()


async def run_forever() -> None:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    await init_db()
    storage.ensure_bucket()
    logger.info("ingest worker started (poll=%.1fs)", settings.worker_poll_seconds)

    while True:
        async with SessionLocal() as session:
            import_job = await claim_next_import_job(session)
            if import_job is not None:
                await process_import_job(session, import_job)
                continue

            ml_job = await claim_next_ml_job(session)
            if ml_job is not None:
                await process_ml_job(session, ml_job)
                continue

        await asyncio.sleep(settings.worker_poll_seconds)
