from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tunelink_backend.api.catalog import TrackOut
from tunelink_backend.auth.deps import get_current_user
from tunelink_backend.db import get_db
from tunelink_backend.models import Playlist, User
from tunelink_backend.services.chat import hydrate_tracks
from tunelink_backend.services import playlists as playlist_svc

router = APIRouter()


class CreatePlaylistBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    track_ids: list[str] | None = None


class UpdatePlaylistBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    clear_description: bool = False


class PlaylistTracksBody(BaseModel):
    track_ids: list[str] = Field(min_length=1)
    position: int | None = Field(default=None, ge=0)


class RemovePlaylistTracksBody(BaseModel):
    track_ids: list[str] = Field(min_length=1)


class ReorderPlaylistBody(BaseModel):
    track_ids: list[str]


class PlaylistSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    track_count: int
    created_at: datetime
    updated_at: datetime


class PlaylistDetailOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    tracks: list[TrackOut]


def _http_error(exc: playlist_svc.PlaylistError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _summary_out(summary: playlist_svc.PlaylistSummary) -> PlaylistSummaryOut:
    playlist = summary.playlist
    return PlaylistSummaryOut(
        id=playlist.id,
        title=playlist.title,
        description=playlist.description,
        track_count=summary.track_count,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
    )


async def _detail_out(db: AsyncSession, playlist: Playlist) -> PlaylistDetailOut:
    track_ids = await playlist_svc.ordered_track_ids(db, playlist.id)
    tracks = await hydrate_tracks(db, [str(track_id) for track_id in track_ids])
    return PlaylistDetailOut(
        id=playlist.id,
        title=playlist.title,
        description=playlist.description,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
        tracks=tracks,
    )


@router.get("", response_model=list[PlaylistSummaryOut], operation_id="listPlaylists")
async def list_playlists(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PlaylistSummaryOut]:
    summaries = await playlist_svc.list_playlist_summaries(db, user.id)
    return [_summary_out(summary) for summary in summaries]


@router.post("", response_model=PlaylistDetailOut, operation_id="createPlaylist")
async def create_playlist(
    body: CreatePlaylistBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaylistDetailOut:
    try:
        playlist = await playlist_svc.create_playlist(
            db,
            user_id=user.id,
            title=body.title,
            description=body.description,
            track_ids=body.track_ids,
        )
        await db.commit()
        await db.refresh(playlist)
        return await _detail_out(db, playlist)
    except playlist_svc.PlaylistError as exc:
        await db.rollback()
        raise _http_error(exc) from exc


@router.get("/{playlist_id}", response_model=PlaylistDetailOut, operation_id="getPlaylist")
async def get_playlist(
    playlist_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaylistDetailOut:
    try:
        playlist = await playlist_svc.get_owned_playlist(db, playlist_id, user.id)
        return await _detail_out(db, playlist)
    except playlist_svc.PlaylistError as exc:
        raise _http_error(exc) from exc


@router.patch("/{playlist_id}", response_model=PlaylistDetailOut, operation_id="updatePlaylist")
async def update_playlist(
    playlist_id: uuid.UUID,
    body: UpdatePlaylistBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaylistDetailOut:
    if (
        body.title is None
        and body.description is None
        and not body.clear_description
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No updates provided",
        )
    try:
        playlist = await playlist_svc.get_owned_playlist(db, playlist_id, user.id)
        await playlist_svc.update_playlist(
            db,
            playlist,
            title=body.title,
            description=body.description,
            clear_description=body.clear_description,
        )
        await db.commit()
        await db.refresh(playlist)
        return await _detail_out(db, playlist)
    except playlist_svc.PlaylistError as exc:
        await db.rollback()
        raise _http_error(exc) from exc


@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT, operation_id="deletePlaylist")
async def delete_playlist(
    playlist_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        playlist = await playlist_svc.get_owned_playlist(db, playlist_id, user.id)
        await playlist_svc.delete_playlist(db, playlist)
        await db.commit()
    except playlist_svc.PlaylistError as exc:
        await db.rollback()
        raise _http_error(exc) from exc


@router.post(
    "/{playlist_id}/tracks",
    response_model=PlaylistDetailOut,
    operation_id="addPlaylistTracks",
)
async def add_playlist_tracks(
    playlist_id: uuid.UUID,
    body: PlaylistTracksBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaylistDetailOut:
    try:
        playlist = await playlist_svc.get_owned_playlist(db, playlist_id, user.id)
        await playlist_svc.add_tracks(
            db,
            playlist,
            body.track_ids,
            position=body.position,
        )
        await db.commit()
        await db.refresh(playlist)
        return await _detail_out(db, playlist)
    except playlist_svc.PlaylistError as exc:
        await db.rollback()
        raise _http_error(exc) from exc


@router.delete(
    "/{playlist_id}/tracks",
    response_model=PlaylistDetailOut,
    operation_id="removePlaylistTracks",
)
async def remove_playlist_tracks(
    playlist_id: uuid.UUID,
    body: RemovePlaylistTracksBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaylistDetailOut:
    try:
        playlist = await playlist_svc.get_owned_playlist(db, playlist_id, user.id)
        await playlist_svc.remove_tracks(db, playlist, body.track_ids)
        await db.commit()
        await db.refresh(playlist)
        return await _detail_out(db, playlist)
    except playlist_svc.PlaylistError as exc:
        await db.rollback()
        raise _http_error(exc) from exc


@router.put(
    "/{playlist_id}/tracks/order",
    response_model=PlaylistDetailOut,
    operation_id="reorderPlaylistTracks",
)
async def reorder_playlist_tracks(
    playlist_id: uuid.UUID,
    body: ReorderPlaylistBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaylistDetailOut:
    try:
        playlist = await playlist_svc.get_owned_playlist(db, playlist_id, user.id)
        await playlist_svc.reorder_tracks(db, playlist, body.track_ids)
        await db.commit()
        await db.refresh(playlist)
        return await _detail_out(db, playlist)
    except playlist_svc.PlaylistError as exc:
        await db.rollback()
        raise _http_error(exc) from exc
