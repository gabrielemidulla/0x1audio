from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from ox1audio_backend.models import Artist
from ox1audio_backend.services import artists as artist_svc
from ox1audio_backend.tools import registry
from ox1audio_backend.tools.serialize import track_payloads
from ox1audio_backend.tools.types import ToolContext, ToolResult, ToolSpec


class SearchArtistsArgs(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=200,
        description="Artist name text to match (case-insensitive substring).",
    )
    limit: int = Field(default=20, ge=1, le=50)


class GetArtistArgs(BaseModel):
    artist_id: str = Field(description="Artist id from a previous tool result.")
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Max tracks to include for this artist.",
    )


def _artist_payload(artist: Artist, track_count: int) -> dict:
    return {
        "id": str(artist.id),
        "name": artist.name,
        "track_count": track_count,
    }


async def search_artists(ctx: ToolContext, args: SearchArtistsArgs) -> ToolResult:
    artists = await artist_svc.search_artists(
        ctx.db, q=args.query, limit=args.limit, offset=0
    )
    counts = await artist_svc.track_counts_by_artist_ids(
        ctx.db, [artist.id for artist in artists]
    )
    return ToolResult(
        payload={
            "artists": [
                _artist_payload(artist, counts.get(artist.id, 0))
                for artist in artists
            ],
            "match": "artists",
        }
    )


async def get_artist(ctx: ToolContext, args: GetArtistArgs) -> ToolResult:
    try:
        artist_id = uuid.UUID(args.artist_id)
    except ValueError:
        return ToolResult.error("Invalid artist_id")
    artist = await artist_svc.get_artist(ctx.db, artist_id)
    if artist is None:
        return ToolResult.error("Artist not found")
    counts = await artist_svc.track_counts_by_artist_ids(ctx.db, [artist.id])
    tracks = await artist_svc.tracks_for_artist(ctx.db, artist.id, limit=args.limit)
    track_dicts = await track_payloads(ctx.db, tracks)
    return ToolResult(
        payload={
            "artist": _artist_payload(artist, counts.get(artist.id, 0)),
            "tracks": track_dicts,
        },
        track_ids=[track["id"] for track in track_dicts],
    )


def register_tools() -> None:
    registry.register(
        ToolSpec(
            name="search_artists",
            description=(
                "Find artist entities by name. Use when the user asks about an artist "
                "as a person/act (how many tracks by X, what do I have by X). "
                "Do NOT use for vibe/mood queries; use get_artist with an id to load tracks."
            ),
            args_model=SearchArtistsArgs,
            handler=search_artists,
        )
    )
    registry.register(
        ToolSpec(
            name="get_artist",
            description=(
                "Load one artist by id and their catalog tracks. "
                "Requires artist_id from search_artists or another tool result."
            ),
            args_model=GetArtistArgs,
            handler=get_artist,
        )
    )
