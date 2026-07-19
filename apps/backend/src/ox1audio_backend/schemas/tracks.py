from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from ox1audio_backend.models import JobStatus, TrackStatus


class ArtistRefOut(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


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
    is_instrumental: bool | None = None
    artists: list[ArtistRefOut] = []

    model_config = {"from_attributes": True}


class TrackListOut(BaseModel):
    items: list[TrackOut]
    total: int
    limit: int
    offset: int


class UpdateTrackBody(BaseModel):
    title: str | None = None
    artist_ids: list[uuid.UUID] | None = None


class DeleteTracksBody(BaseModel):
    track_ids: list[uuid.UUID]


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
