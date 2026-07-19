from __future__ import annotations

import logging
import uuid
from enum import StrEnum
from io import BytesIO
from pathlib import PurePosixPath

import grpc
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ox1audio_backend import storage
from ox1audio_backend.api.catalog import _read_upload
from ox1audio_backend.api.http import http_error
from ox1audio_backend.auth.deps import get_current_user
from ox1audio_backend.config import get_settings
from ox1audio_backend.db import get_db
from ox1audio_backend.ml_client import SearchHit, get_ml_client
from ox1audio_backend.models import Track, User
from ox1audio_backend.schemas.tracks import TrackOut
from ox1audio_backend.services.catalog import (
    CatalogError,
    allowed_extensions,
    safe_filename,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class SearchMode(StrEnum):
    TRACKS = "tracks"
    SEGMENTS = "segments"


class SearchTextBody(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    negative_query: str | None = Field(default=None, max_length=500)
    top_k: int = Field(default=6, ge=1, le=20)
    mode: SearchMode = SearchMode.TRACKS


class SearchHitOut(BaseModel):
    track: TrackOut
    score: float
    track_score: float
    best_segment_score: float
    segment_coverage: float
    match_scope: str
    matched_segment_ids: list[str]
    reasons: list[str]


class SearchResponseOut(BaseModel):
    results: list[SearchHitOut]


@router.post("/text", response_model=SearchResponseOut, operation_id="searchText")
async def search_text(
    body: SearchTextBody,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SearchResponseOut:
    client = get_ml_client()
    try:
        hits = client.search_text(
            query=body.query.strip(),
            top_k=body.top_k,
            mode=body.mode.value,
            negative_query=body.negative_query.strip() if body.negative_query else None,
        )
    except grpc.RpcError as exc:
        logger.exception("search_text gRPC failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ML search failed: {exc.details() or exc.code().name}",
        ) from exc
    finally:
        client.close()

    return SearchResponseOut(results=await _hydrate_hits(db, hits))


@router.post("/audio", response_model=SearchResponseOut, operation_id="searchAudio")
async def search_audio(
    file: UploadFile = File(...),
    top_k: int = Query(default=6, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SearchResponseOut:
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename required")

    try:
        safe_name = safe_filename(file.filename)
    except CatalogError as exc:
        raise http_error(exc) from exc
    suffix = PurePosixPath(safe_name).suffix.lower()
    if suffix not in allowed_extensions():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{suffix}'",
        )

    data = await _read_upload(file, settings.max_upload_bytes)
    object_key = f"search-queries/{uuid.uuid4()}/{safe_name}"
    content_type = file.content_type or "application/octet-stream"

    try:
        storage.put_object(object_key, BytesIO(data), len(data), content_type)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Storage upload failed: {exc}",
        ) from exc

    client = get_ml_client()
    try:
        hits = client.search_audio(
            audio_url=storage.presigned_get_url(object_key),
            top_k=top_k,
        )
    except grpc.RpcError as exc:
        logger.exception("search_audio gRPC failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ML search failed: {exc.details() or exc.code().name}",
        ) from exc
    finally:
        client.close()
        storage.remove_object(object_key)

    return SearchResponseOut(results=await _hydrate_hits(db, hits))


@router.get(
    "/similar/{track_id}",
    response_model=SearchResponseOut,
    operation_id="similarTracks",
)
async def similar_tracks(
    track_id: uuid.UUID,
    top_k: int = Query(default=6, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SearchResponseOut:
    track = await db.scalar(select(Track).where(Track.id == track_id))
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    client = get_ml_client()
    try:
        hits = client.similar_tracks(track_id=str(track_id), top_k=top_k)
    except grpc.RpcError as exc:
        logger.exception("similar_tracks gRPC failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ML search failed: {exc.details() or exc.code().name}",
        ) from exc
    finally:
        client.close()

    return SearchResponseOut(results=await _hydrate_hits(db, hits))


async def _hydrate_hits(db: AsyncSession, hits: list[SearchHit]) -> list[SearchHitOut]:
    uuids: list[uuid.UUID] = []
    for hit in hits:
        try:
            uuids.append(uuid.UUID(hit.track_id))
        except ValueError:
            continue
    tracks_by_id: dict[str, Track] = {}
    if uuids:
        rows = await db.scalars(select(Track).where(Track.id.in_(uuids)))
        tracks_by_id = {str(track.id): track for track in rows}

    hydrated: list[SearchHitOut] = []
    for hit in hits:
        track = tracks_by_id.get(hit.track_id)
        if track is None:
            continue
        hydrated.append(
            SearchHitOut(
                track=TrackOut.model_validate(track),
                score=hit.score,
                track_score=hit.track_score,
                best_segment_score=hit.best_segment_score,
                segment_coverage=hit.segment_coverage,
                match_scope=hit.match_scope,
                matched_segment_ids=hit.matched_segment_ids,
                reasons=hit.reasons,
            )
        )
    return hydrated
