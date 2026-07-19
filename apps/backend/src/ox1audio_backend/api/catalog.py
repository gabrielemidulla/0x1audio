from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select

from ox1audio_backend import storage
from ox1audio_backend.api.deps import CurrentUser, DbSession
from ox1audio_backend.api.http import http_error
from ox1audio_backend.config import get_settings
from ox1audio_backend.models import ImportJob, Track, TrackStatus
from ox1audio_backend.schemas.tracks import (
    DeleteTracksBody,
    ImportJobOut,
    JobOut,
    TrackListOut,
    TrackOut,
    UpdateTrackBody,
    WaveformOut,
)
from ox1audio_backend.services import catalog as catalog_svc
from ox1audio_backend.services import tracks as track_svc
from ox1audio_backend.services.catalog import CatalogError, SortOrder, TrackSort

router = APIRouter()

_READ_CHUNK = 1024 * 1024


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
    db: DbSession,
    _user: CurrentUser,
    file: UploadFile = File(...),
) -> TrackOut:
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename required")

    try:
        safe_name = catalog_svc.safe_filename(file.filename)
        suffix = PurePosixPath(safe_name).suffix.lower()
        allowed = catalog_svc.allowed_extensions()
        if suffix not in allowed:
            raise CatalogError(
                f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(allowed))}"
            )
    except CatalogError as exc:
        raise http_error(exc) from exc

    data = await _read_upload(file, settings.max_upload_bytes)
    try:
        track = await catalog_svc.upload_track(
            db,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            data=data,
        )
    except CatalogError as exc:
        raise http_error(exc) from exc
    return await track_svc.track_out(db, track)


@router.post(
    "/uploads/zip",
    response_model=ImportJobOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="uploadZip",
)
async def upload_zip(
    db: DbSession,
    _user: CurrentUser,
    file: UploadFile = File(...),
) -> ImportJob:
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename required")

    try:
        safe_name = catalog_svc.safe_filename(file.filename)
        if PurePosixPath(safe_name).suffix.lower() != ".zip":
            raise CatalogError("Expected a .zip file")
    except CatalogError as exc:
        raise http_error(exc) from exc

    spool_path = await _spool_upload(file, settings.max_zip_bytes)
    try:
        try:
            return await catalog_svc.upload_zip(
                db,
                filename=file.filename,
                content_type=file.content_type or "application/zip",
                spool_path=str(spool_path),
            )
        except CatalogError as exc:
            raise http_error(exc) from exc
    finally:
        spool_path.unlink(missing_ok=True)


@router.get("/imports", response_model=list[ImportJobOut], operation_id="listImports")
async def list_imports(
    db: DbSession,
    _user: CurrentUser,
) -> list[ImportJob]:
    result = await db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()))
    return list(result)


@router.get("/jobs", response_model=list[JobOut], operation_id="listJobs")
async def list_jobs(
    db: DbSession,
    _user: CurrentUser,
) -> list[JobOut]:
    return await catalog_svc.list_jobs(db)


@router.post("/jobs/{job_id}/cancel", response_model=JobOut, operation_id="cancelJob")
async def cancel_job(
    job_id: str,
    db: DbSession,
    _user: CurrentUser,
) -> JobOut:
    try:
        return await catalog_svc.cancel_job(db, job_id)
    except CatalogError as exc:
        raise http_error(exc) from exc


@router.post("/jobs/{job_id}/retry-failed", response_model=JobOut, operation_id="retryFailedJob")
async def retry_failed_job(
    job_id: str,
    db: DbSession,
    _user: CurrentUser,
) -> JobOut:
    try:
        return await catalog_svc.retry_failed_job(db, job_id)
    except CatalogError as exc:
        raise http_error(exc) from exc


@router.get("/imports/{import_id}", response_model=ImportJobOut, operation_id="getImport")
async def get_import(
    import_id: uuid.UUID,
    db: DbSession,
    _user: CurrentUser,
) -> ImportJob:
    try:
        return await catalog_svc.get_import_or_404(db, import_id)
    except CatalogError as exc:
        raise http_error(exc) from exc


@router.get("/tracks", response_model=TrackListOut, operation_id="listTracks")
async def list_tracks(
    db: DbSession,
    _user: CurrentUser,
    q: str | None = Query(default=None, max_length=200),
    artist: str | None = Query(default=None, max_length=200),
    artist_id: uuid.UUID | None = Query(default=None),
    status_filter: TrackStatus | None = Query(default=None, alias="status"),
    sort: TrackSort = Query(default="imported_at"),
    order: SortOrder = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TrackListOut:
    return await catalog_svc.list_tracks(
        db,
        q=q,
        artist=artist,
        artist_id=artist_id,
        status_filter=status_filter,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/tracks/bulk-delete",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteTracks",
    summary="Delete tracks",
)
async def delete_tracks(
    body: DeleteTracksBody,
    db: DbSession,
    _user: CurrentUser,
) -> None:
    if not body.track_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tracks selected")
    await track_svc.delete_tracks(db, body.track_ids)
    await db.commit()


@router.delete(
    "/tracks/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteTrack",
    summary="Delete a track",
)
async def delete_track(
    track_id: uuid.UUID,
    db: DbSession,
    _user: CurrentUser,
) -> None:
    deleted = await track_svc.delete_tracks(db, [track_id])
    if deleted == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
    await db.commit()


@router.patch("/tracks/{track_id}", response_model=TrackOut, operation_id="updateTrack")
async def update_track(
    track_id: uuid.UUID,
    body: UpdateTrackBody,
    db: DbSession,
    _user: CurrentUser,
) -> TrackOut:
    try:
        track = await catalog_svc.update_track(
            db,
            track_id,
            title=body.title,
            artist_ids=body.artist_ids,
        )
    except CatalogError as exc:
        raise http_error(exc) from exc
    return await track_svc.track_out(db, track)


@router.get("/tracks/{track_id}", response_model=TrackOut, operation_id="getTrack")
async def get_track(
    track_id: uuid.UUID,
    db: DbSession,
    _user: CurrentUser,
) -> TrackOut:
    try:
        track = await catalog_svc.get_track_or_404(db, track_id)
    except CatalogError as exc:
        raise http_error(exc) from exc
    return await track_svc.track_out(db, track)


@router.put("/tracks/{track_id}/cover", response_model=TrackOut, operation_id="updateTrackCover")
async def update_track_cover(
    track_id: uuid.UUID,
    db: DbSession,
    _user: CurrentUser,
    file: UploadFile = File(...),
) -> TrackOut:
    data = await _read_upload(file, 8 * 1024 * 1024)
    try:
        track = await catalog_svc.update_track_cover(
            db,
            track_id,
            data=data,
            content_type=file.content_type or "",
        )
    except CatalogError as exc:
        raise http_error(exc) from exc
    return await track_svc.track_out(db, track)


@router.get("/tracks/{track_id}/cover", operation_id="getTrackCover")
async def get_track_cover(
    track_id: uuid.UUID,
    db: DbSession,
    _user: CurrentUser,
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
    db: DbSession,
    _user: CurrentUser,
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
    db: DbSession,
    _user: CurrentUser,
) -> WaveformOut:
    track = await db.scalar(select(Track).where(Track.id == track_id))
    try:
        if track is None:
            raise CatalogError("Waveform not found", status_code=404)
        return catalog_svc.waveform_out(track)
    except CatalogError as exc:
        raise http_error(exc) from exc
