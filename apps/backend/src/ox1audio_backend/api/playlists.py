from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ox1audio_backend.api.deps import CurrentUser, DbSession
from ox1audio_backend.api.http import http_error
from ox1audio_backend.models import Playlist
from ox1audio_backend.schemas.tracks import TrackOut
from ox1audio_backend.services import playlists as playlist_svc
from ox1audio_backend.services.chat import hydrate_tracks
from ox1audio_backend.services.playlist_colors import PlaylistColor, theme_hexes

router = APIRouter()


class CreatePlaylistBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    color: PlaylistColor
    description: str | None = Field(default=None, max_length=2000)
    track_ids: list[str] | None = None


class UpdatePlaylistBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    clear_description: bool = False
    color: PlaylistColor | None = None


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
    color: PlaylistColor | None = None
    theme_colors: list[str] = []
    track_count: int
    cover_colors: list[str] = []
    created_at: datetime
    updated_at: datetime


class PlaylistDetailOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    color: PlaylistColor | None = None
    theme_colors: list[str] = []
    created_at: datetime
    updated_at: datetime
    tracks: list[TrackOut]


def _color_out(raw: str | None) -> PlaylistColor | None:
    if not raw:
        return None
    try:
        return PlaylistColor(raw)
    except ValueError:
        return None


def _summary_out(summary: playlist_svc.PlaylistSummary) -> PlaylistSummaryOut:
    playlist = summary.playlist
    color = _color_out(playlist.color)
    return PlaylistSummaryOut(
        id=playlist.id,
        title=playlist.title,
        description=playlist.description,
        color=color,
        theme_colors=theme_hexes(color),
        track_count=summary.track_count,
        cover_colors=summary.cover_colors,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
    )


async def _detail_out(db: DbSession, playlist: Playlist) -> PlaylistDetailOut:
    track_ids = await playlist_svc.ordered_track_ids(db, playlist.id)
    tracks = await hydrate_tracks(db, [str(track_id) for track_id in track_ids])
    color = _color_out(playlist.color)
    return PlaylistDetailOut(
        id=playlist.id,
        title=playlist.title,
        description=playlist.description,
        color=color,
        theme_colors=theme_hexes(color),
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
        tracks=tracks,
    )


@router.get("", response_model=list[PlaylistSummaryOut], operation_id="listPlaylists")
async def list_playlists(
    db: DbSession,
    user: CurrentUser,
) -> list[PlaylistSummaryOut]:
    summaries = await playlist_svc.list_playlist_summaries(db, user.id)
    return [_summary_out(summary) for summary in summaries]


@router.post("", response_model=PlaylistDetailOut, operation_id="createPlaylist")
async def create_playlist(
    body: CreatePlaylistBody,
    db: DbSession,
    user: CurrentUser,
) -> PlaylistDetailOut:
    try:
        playlist = await playlist_svc.create_playlist(
            db,
            user_id=user.id,
            title=body.title,
            color=body.color.value,
            description=body.description,
            track_ids=body.track_ids,
        )
        await db.commit()
        await db.refresh(playlist)
        return await _detail_out(db, playlist)
    except playlist_svc.PlaylistError as exc:
        await db.rollback()
        raise http_error(exc) from exc


@router.get("/{playlist_id}", response_model=PlaylistDetailOut, operation_id="getPlaylist")
async def get_playlist(
    playlist_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> PlaylistDetailOut:
    try:
        playlist = await playlist_svc.get_owned_playlist(db, playlist_id, user.id)
        return await _detail_out(db, playlist)
    except playlist_svc.PlaylistError as exc:
        raise http_error(exc) from exc


@router.patch("/{playlist_id}", response_model=PlaylistDetailOut, operation_id="updatePlaylist")
async def update_playlist(
    playlist_id: uuid.UUID,
    body: UpdatePlaylistBody,
    db: DbSession,
    user: CurrentUser,
) -> PlaylistDetailOut:
    if (
        body.title is None
        and body.description is None
        and not body.clear_description
        and body.color is None
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
            color=body.color.value if body.color is not None else None,
        )
        await db.commit()
        await db.refresh(playlist)
        return await _detail_out(db, playlist)
    except playlist_svc.PlaylistError as exc:
        await db.rollback()
        raise http_error(exc) from exc


@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT, operation_id="deletePlaylist")
async def delete_playlist(
    playlist_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> None:
    try:
        playlist = await playlist_svc.get_owned_playlist(db, playlist_id, user.id)
        await playlist_svc.delete_playlist(db, playlist)
        await db.commit()
    except playlist_svc.PlaylistError as exc:
        await db.rollback()
        raise http_error(exc) from exc


@router.post(
    "/{playlist_id}/tracks",
    response_model=PlaylistDetailOut,
    operation_id="addPlaylistTracks",
)
async def add_playlist_tracks(
    playlist_id: uuid.UUID,
    body: PlaylistTracksBody,
    db: DbSession,
    user: CurrentUser,
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
        raise http_error(exc) from exc


@router.delete(
    "/{playlist_id}/tracks",
    response_model=PlaylistDetailOut,
    operation_id="removePlaylistTracks",
)
async def remove_playlist_tracks(
    playlist_id: uuid.UUID,
    body: RemovePlaylistTracksBody,
    db: DbSession,
    user: CurrentUser,
) -> PlaylistDetailOut:
    try:
        playlist = await playlist_svc.get_owned_playlist(db, playlist_id, user.id)
        await playlist_svc.remove_tracks(db, playlist, body.track_ids)
        await db.commit()
        await db.refresh(playlist)
        return await _detail_out(db, playlist)
    except playlist_svc.PlaylistError as exc:
        await db.rollback()
        raise http_error(exc) from exc


@router.put(
    "/{playlist_id}/tracks/order",
    response_model=PlaylistDetailOut,
    operation_id="reorderPlaylistTracks",
)
async def reorder_playlist_tracks(
    playlist_id: uuid.UUID,
    body: ReorderPlaylistBody,
    db: DbSession,
    user: CurrentUser,
) -> PlaylistDetailOut:
    try:
        playlist = await playlist_svc.get_owned_playlist(db, playlist_id, user.id)
        await playlist_svc.reorder_tracks(db, playlist, body.track_ids)
        await db.commit()
        await db.refresh(playlist)
        return await _detail_out(db, playlist)
    except playlist_svc.PlaylistError as exc:
        await db.rollback()
        raise http_error(exc) from exc
