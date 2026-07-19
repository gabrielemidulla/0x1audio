from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ox1audio_backend import storage
from ox1audio_backend.api.deps import CurrentUser, DbSession
from ox1audio_backend.api.http import http_error
from ox1audio_backend.models import Artist
from ox1audio_backend.services import artists as artist_svc
from ox1audio_backend.services.artist_images import fetch_and_store_artist_image

router = APIRouter()

ArtistSort = Literal["name", "track_count", "created_at"]
SortOrder = Literal["asc", "desc"]


class ArtistOut(BaseModel):
    id: uuid.UUID
    name: str
    track_count: int = 0
    has_image: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ArtistListOut(BaseModel):
    items: list[ArtistOut]
    total: int
    limit: int
    offset: int


class CreateArtistBody(BaseModel):
    name: str = Field(min_length=1, max_length=512)


async def _artists_out(db: DbSession, artists: list[Artist]) -> list[ArtistOut]:
    counts = await artist_svc.track_counts_by_artist_ids(db, [artist.id for artist in artists])
    return [
        ArtistOut(
            id=artist.id,
            name=artist.name,
            track_count=counts.get(artist.id, 0),
            has_image=artist.image_object_key is not None,
            created_at=artist.created_at,
            updated_at=artist.updated_at,
        )
        for artist in artists
    ]


@router.get("/artists", response_model=ArtistListOut, operation_id="listArtists")
async def list_artists(
    db: DbSession,
    _user: CurrentUser,
    q: str | None = Query(default=None, max_length=200),
    sort: ArtistSort = Query(default="name"),
    order: SortOrder = Query(default="asc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ArtistListOut:
    total = await artist_svc.count_artists(db, q=q)
    artists = await artist_svc.search_artists(
        db, q=q, limit=limit, offset=offset, sort=sort, order=order
    )
    return ArtistListOut(
        items=await _artists_out(db, artists),
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/artists/{artist_id}", response_model=ArtistOut, operation_id="getArtist")
async def get_artist(
    artist_id: uuid.UUID,
    db: DbSession,
    _user: CurrentUser,
) -> ArtistOut:
    artist = await artist_svc.get_artist(db, artist_id)
    if artist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found")
    items = await _artists_out(db, [artist])
    return items[0]


@router.get("/artists/{artist_id}/image", operation_id="getArtistImage")
async def get_artist_image(
    artist_id: uuid.UUID,
    db: DbSession,
    _user: CurrentUser,
) -> Response:
    artist = await artist_svc.get_artist(db, artist_id)
    if artist is None or not artist.image_object_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    try:
        data, content_type = storage.get_object_bytes(artist.image_object_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Image storage failed: {exc}",
        ) from exc
    return Response(content=data, media_type=content_type)


@router.post(
    "/artists",
    response_model=ArtistOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="createArtist",
)
async def create_artist(
    body: CreateArtistBody,
    db: DbSession,
    _user: CurrentUser,
) -> ArtistOut:
    name = " ".join(body.name.split()).strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name required")
    existing = await db.scalar(
        select(Artist).where(func.lower(Artist.name) == name.casefold())
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Artist already exists",
        )
    artist = await artist_svc.get_or_create_artist(db, name)
    image_key = fetch_and_store_artist_image(artist.id, artist.name)
    if image_key is not None:
        artist.image_object_key = image_key
    await db.commit()
    await db.refresh(artist)
    items = await _artists_out(db, [artist])
    return items[0]


@router.delete(
    "/artists/{artist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteArtist",
)
async def delete_artist(
    artist_id: uuid.UUID,
    db: DbSession,
    _user: CurrentUser,
) -> None:
    artist = await artist_svc.get_artist(db, artist_id)
    if artist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found")
    image_key = artist.image_object_key
    try:
        deleted = await artist_svc.delete_artist_if_unused(db, artist_id)
    except artist_svc.ArtistError as exc:
        raise http_error(exc) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found")
    await db.commit()
    if image_key:
        storage.remove_object(image_key)
