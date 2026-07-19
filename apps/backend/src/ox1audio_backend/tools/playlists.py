from __future__ import annotations

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select

from ox1audio_backend.models import Track
from ox1audio_backend.services.playlist_colors import PlaylistColor, theme_hexes
from ox1audio_backend.services import playlists as playlist_svc
from ox1audio_backend.tools import registry
from ox1audio_backend.tools.serialize import track_payloads
from ox1audio_backend.tools.types import ToolContext, ToolResult, ToolSpec


class ListPlaylistsArgs(BaseModel):
    pass


class GetPlaylistArgs(BaseModel):
    playlist_id: str


class CreatePlaylistArgs(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=200,
        description='Playlist title. If the user did not name one, use "New playlist".',
    )
    color: PlaylistColor = Field(
        default=PlaylistColor.INDIGO,
        description=(
            "Mood color for the playlist card. Always set this yourself from the enum; "
            "never ask the user or mention color names in chat."
        ),
    )
    description: str | None = Field(default=None, max_length=2000)
    track_ids: list[str] | None = None


class UpdatePlaylistArgs(BaseModel):
    playlist_id: str
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    clear_description: bool = False
    color: PlaylistColor | None = Field(
        default=None,
        description="Optional mood color change. Pick yourself; never ask the user.",
    )


class PlaylistIdArgs(BaseModel):
    playlist_id: str


class AddTracksArgs(BaseModel):
    playlist_id: str
    track_ids: list[str] = Field(min_length=1)
    position: int | None = Field(default=None, ge=0)


class RemoveTracksArgs(BaseModel):
    playlist_id: str
    track_ids: list[str] = Field(min_length=1)


class ReorderTracksArgs(BaseModel):
    playlist_id: str
    track_ids: list[str]


def _parse_playlist_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise playlist_svc.PlaylistError(
            f"Invalid playlist_id: {raw}",
            status_code=422,
        ) from exc


async def _tracks_payload(
    ctx: ToolContext,
    track_ids: list[uuid.UUID],
) -> tuple[list[dict], list[str]]:
    if not track_ids:
        return [], []
    rows = await ctx.db.scalars(select(Track).where(Track.id.in_(track_ids)))
    by_id = {track.id: track for track in rows}
    ordered: list[Track] = []
    ids: list[str] = []
    for track_id in track_ids:
        track = by_id.get(track_id)
        if track is None:
            raise playlist_svc.PlaylistError(
                f"Unknown track_id: {track_id}",
                status_code=422,
            )
        ordered.append(track)
        ids.append(str(track.id))
    payload = await track_payloads(ctx.db, ordered)
    return payload, ids


def _playlist_tool_result(
    *,
    playlist_id: uuid.UUID,
    title: str,
    description: str | None,
    color: str | None,
    track_ids: list[str],
    tracks: list[dict] | None = None,
) -> ToolResult:
    playlist: dict = {
        "id": str(playlist_id),
        "title": title,
        "description": description,
        "color": color,
        "theme_colors": theme_hexes(color),
        "track_count": len(track_ids),
        "track_ids": track_ids,
    }
    if tracks is not None:
        playlist["tracks"] = tracks
    return ToolResult(
        payload={"playlist": playlist},
        playlist_ids=[str(playlist_id)],
    )


async def list_playlists(ctx: ToolContext, _args: ListPlaylistsArgs) -> ToolResult:
    summaries = await playlist_svc.list_playlist_summaries(ctx.db, ctx.user_id)
    return ToolResult(
        payload={
            "playlists": [
                {
                    "id": str(summary.playlist.id),
                    "title": summary.playlist.title,
                    "description": summary.playlist.description,
                    "color": summary.playlist.color,
                    "track_count": summary.track_count,
                    "updated_at": summary.playlist.updated_at.isoformat(),
                }
                for summary in summaries
            ]
        },
        # Listing is for the model — do not attach playlist widgets.
        # Call get_playlist / create_playlist to show a card in chat.
        playlist_ids=[],
    )


async def get_playlist(ctx: ToolContext, args: GetPlaylistArgs) -> ToolResult:
    try:
        playlist_id = _parse_playlist_id(args.playlist_id)
        playlist = await playlist_svc.get_owned_playlist(
            ctx.db, playlist_id, ctx.user_id
        )
        ordered = await playlist_svc.ordered_track_ids(ctx.db, playlist.id)
        tracks, track_ids = await _tracks_payload(ctx, ordered)
        return _playlist_tool_result(
            playlist_id=playlist.id,
            title=playlist.title,
            description=playlist.description,
            color=playlist.color,
            track_ids=track_ids,
            tracks=tracks,
        )
    except playlist_svc.PlaylistError as exc:
        return ToolResult.error(exc.message)


async def create_playlist(ctx: ToolContext, args: CreatePlaylistArgs) -> ToolResult:
    try:
        playlist = await playlist_svc.create_playlist(
            ctx.db,
            user_id=ctx.user_id,
            title=args.title,
            color=args.color.value,
            description=args.description,
            track_ids=args.track_ids,
        )
        await ctx.db.commit()
        ordered = await playlist_svc.ordered_track_ids(ctx.db, playlist.id)
        tracks, track_ids = await _tracks_payload(ctx, ordered)
        return _playlist_tool_result(
            playlist_id=playlist.id,
            title=playlist.title,
            description=playlist.description,
            color=playlist.color,
            track_ids=track_ids,
            tracks=tracks,
        )
    except playlist_svc.PlaylistError as exc:
        await ctx.db.rollback()
        return ToolResult.error(exc.message)


async def update_playlist(ctx: ToolContext, args: UpdatePlaylistArgs) -> ToolResult:
    if (
        args.title is None
        and args.description is None
        and not args.clear_description
        and args.color is None
    ):
        return ToolResult.error("No updates provided")
    try:
        playlist_id = _parse_playlist_id(args.playlist_id)
        playlist = await playlist_svc.get_owned_playlist(
            ctx.db, playlist_id, ctx.user_id
        )
        await playlist_svc.update_playlist(
            ctx.db,
            playlist,
            title=args.title,
            description=args.description,
            clear_description=args.clear_description,
            color=args.color.value if args.color is not None else None,
        )
        await ctx.db.commit()
        ordered = await playlist_svc.ordered_track_ids(ctx.db, playlist.id)
        return _playlist_tool_result(
            playlist_id=playlist.id,
            title=playlist.title,
            description=playlist.description,
            color=playlist.color,
            track_ids=[str(track_id) for track_id in ordered],
        )
    except playlist_svc.PlaylistError as exc:
        await ctx.db.rollback()
        return ToolResult.error(exc.message)


async def delete_playlist(ctx: ToolContext, args: PlaylistIdArgs) -> ToolResult:
    try:
        playlist_id = _parse_playlist_id(args.playlist_id)
        playlist = await playlist_svc.get_owned_playlist(
            ctx.db, playlist_id, ctx.user_id
        )
        title = playlist.title
        await playlist_svc.delete_playlist(ctx.db, playlist)
        await ctx.db.commit()
        return ToolResult(
            payload={"deleted": True, "id": str(playlist_id), "title": title}
        )
    except playlist_svc.PlaylistError as exc:
        await ctx.db.rollback()
        return ToolResult.error(exc.message)


async def add_tracks_to_playlist(ctx: ToolContext, args: AddTracksArgs) -> ToolResult:
    try:
        playlist_id = _parse_playlist_id(args.playlist_id)
        playlist = await playlist_svc.get_owned_playlist(
            ctx.db, playlist_id, ctx.user_id
        )
        ordered = await playlist_svc.add_tracks(
            ctx.db,
            playlist,
            args.track_ids,
            position=args.position,
        )
        await ctx.db.commit()
        tracks, track_ids = await _tracks_payload(ctx, ordered)
        return _playlist_tool_result(
            playlist_id=playlist.id,
            title=playlist.title,
            description=playlist.description,
            color=playlist.color,
            track_ids=track_ids,
            tracks=tracks,
        )
    except playlist_svc.PlaylistError as exc:
        await ctx.db.rollback()
        return ToolResult.error(exc.message)


async def remove_tracks_from_playlist(
    ctx: ToolContext,
    args: RemoveTracksArgs,
) -> ToolResult:
    try:
        playlist_id = _parse_playlist_id(args.playlist_id)
        playlist = await playlist_svc.get_owned_playlist(
            ctx.db, playlist_id, ctx.user_id
        )
        ordered = await playlist_svc.remove_tracks(ctx.db, playlist, args.track_ids)
        await ctx.db.commit()
        tracks, track_ids = await _tracks_payload(ctx, ordered)
        return _playlist_tool_result(
            playlist_id=playlist.id,
            title=playlist.title,
            description=playlist.description,
            color=playlist.color,
            track_ids=track_ids,
            tracks=tracks,
        )
    except playlist_svc.PlaylistError as exc:
        await ctx.db.rollback()
        return ToolResult.error(exc.message)


async def reorder_playlist(ctx: ToolContext, args: ReorderTracksArgs) -> ToolResult:
    try:
        playlist_id = _parse_playlist_id(args.playlist_id)
        playlist = await playlist_svc.get_owned_playlist(
            ctx.db, playlist_id, ctx.user_id
        )
        ordered = await playlist_svc.reorder_tracks(ctx.db, playlist, args.track_ids)
        await ctx.db.commit()
        return _playlist_tool_result(
            playlist_id=playlist.id,
            title=playlist.title,
            description=playlist.description,
            color=playlist.color,
            track_ids=[str(track_id) for track_id in ordered],
        )
    except playlist_svc.PlaylistError as exc:
        await ctx.db.rollback()
        return ToolResult.error(exc.message)


def register_tools() -> None:
    registry.register(
        ToolSpec(
            name="list_playlists",
            description=(
                "List the current user's playlists (ids/titles for the model). "
                "Does not show widgets — call get_playlist to attach a playlist card."
            ),
            args_model=ListPlaylistsArgs,
            handler=list_playlists,
        )
    )
    registry.register(
        ToolSpec(
            name="get_playlist",
            description=(
                "Get one owned playlist by id. Call this to show a playlist widget "
                "in chat — never paste playlist ids in prose."
            ),
            args_model=GetPlaylistArgs,
            handler=get_playlist,
        )
    )
    registry.register(
        ToolSpec(
            name="create_playlist",
            description=(
                "Create a playlist for the current user and optionally seed it with "
                "track_ids from prior search/similar results. "
                "Only when the user explicitly asks to create/build/save a playlist or mix. "
                "Always pick color yourself (default indigo is fine) — never ask or list colors. "
                "If they gave no title, use \"New playlist\". "
                "The playlist card is attached automatically."
            ),
            args_model=CreatePlaylistArgs,
            handler=create_playlist,
        )
    )
    registry.register(
        ToolSpec(
            name="update_playlist",
            description=(
                "Rename a playlist, update/clear its description, and/or change its "
                "mood color (optional)."
            ),
            args_model=UpdatePlaylistArgs,
            handler=update_playlist,
        )
    )
    registry.register(
        ToolSpec(
            name="add_tracks_to_playlist",
            description="Add catalog track_ids to an owned playlist (append or insert at position).",
            args_model=AddTracksArgs,
            handler=add_tracks_to_playlist,
        )
    )
    registry.register(
        ToolSpec(
            name="remove_tracks_from_playlist",
            description="Remove track_ids from an owned playlist.",
            args_model=RemoveTracksArgs,
            handler=remove_tracks_from_playlist,
        )
    )
    registry.register(
        ToolSpec(
            name="reorder_playlist",
            description="Replace playlist order with a full permutation of its current track_ids.",
            args_model=ReorderTracksArgs,
            handler=reorder_playlist,
        )
    )
    registry.register(
        ToolSpec(
            name="delete_playlist",
            description="Permanently delete an owned playlist.",
            args_model=PlaylistIdArgs,
            handler=delete_playlist,
        )
    )
