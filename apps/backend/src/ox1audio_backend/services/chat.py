from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ox1audio_backend.config import Settings, get_settings
from ox1audio_backend.exceptions import AppError
from ox1audio_backend.models import Track
from ox1audio_backend.schemas.tracks import TrackOut
from ox1audio_backend.tools import ensure_registered, execute
from ox1audio_backend.tools.langchain import build_langchain_tools
from ox1audio_backend.tools.types import ToolContext

logger = logging.getLogger(__name__)

DisconnectCheck = Callable[[], Awaitable[bool]]

SYSTEM_PROMPT = """\
You are 0x1audio's catalog librarian. Use tools for library questions. Never invent
tracks, artists, playlists, or actions you did not perform with tools.

Tool choice:
- search_metadata: resolve a song/artist title to track_ids (text match only).
- similar_tracks: sonic neighbors of a track_id (NOT same-artist lookup). Needs track_id.
- search_vibe: abstract mood only when no named seed track (e.g. "dark techno").
- search_artists / get_artist: artist entity questions.
- Playlist tools: ONLY if the user explicitly asks to create/build/save/edit a playlist.

"Similar songs to [title]" / "tracks like Ghost Town":
1) search_metadata once → track_id
2) similar_tracks
3) Stop. Reply in one short sentence that similar tracks are ready.
Do NOT create or update playlists. Do NOT mention colors, themes, or UI.
Do NOT follow up with more metadata/artist searches.

Creating a playlist:
- Call create_playlist with title and color. color is mandatory — you decide it.
- Never ask the user to choose a color. Never list color names or enums in chat.
- If they did not give a title, use a short default like "New playlist" and create it.
- Confirm in one short sentence; the playlist card appears automatically.

After tools run, be honest: only describe what the tools actually returned.
Tracks/playlists from tools appear as cards automatically — do not dump ids or full lists.
Keep answers brief.\
"""


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


@dataclass
class ToolTrace:
    name: str
    args: dict[str, Any]
    ok: bool


@dataclass
class ChatResult:
    content: str
    tool_traces: list[ToolTrace] = field(default_factory=list)
    track_ids: list[str] = field(default_factory=list)
    playlist_ids: list[str] = field(default_factory=list)
    cancelled: bool = False


@dataclass
class ChatStreamStatus:
    phase: Literal["thinking", "tool"]
    name: str | None = None


@dataclass
class ChatStreamToken:
    text: str


ChatStreamEvent = ChatStreamStatus | ChatStreamToken | ChatResult


class ChatError(AppError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message, status_code=status_code)


class ChatCancelled(Exception):
    def __init__(self, partial: ChatResult) -> None:
        super().__init__("cancelled")
        self.partial = partial


def _history_messages(
    messages: list[ChatMessageIn],
    *,
    max_messages: int,
) -> list[BaseMessage]:
    trimmed = messages[-max_messages:]
    out: list[BaseMessage] = []
    for message in trimmed:
        if message.role == "user":
            out.append(HumanMessage(content=message.content))
        else:
            out.append(AIMessage(content=message.content))
    return out


def _text_from_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
                elif "text" in block:
                    parts.append(str(block.get("text") or ""))
        return "".join(parts)
    return str(content)


_PLAYLIST_HALLUCINATION = re.compile(
    r"\b("
    r"playlist|playlists|mood\s*color|light_?blue|washed_?blue|theme|palette|"
    r"updated with|have been updated|color you.?d like|vibe or color|for your ui"
    r")\b",
    re.IGNORECASE,
)

_PLAYLIST_MUTATION_TOOLS = frozenset(
    {
        "create_playlist",
        "update_playlist",
        "add_tracks_to_playlist",
        "remove_tracks_from_playlist",
        "reorder_playlist",
        "delete_playlist",
    }
)


def _sanitize_final_answer(
    content: str,
    *,
    traces: list[ToolTrace],
    track_ids: list[str],
    playlist_ids: list[str],
) -> str:
    """Replace invented playlist/color claims when tools never did that."""
    text = content.strip()
    if not text:
        return text

    mutated_playlist = any(
        trace.ok and trace.name in _PLAYLIST_MUTATION_TOOLS for trace in traces
    )
    ran_similar = any(trace.ok and trace.name == "similar_tracks" for trace in traces)

    if mutated_playlist or playlist_ids:
        return text

    if ran_similar and _PLAYLIST_HALLUCINATION.search(text):
        n = len(track_ids)
        if n:
            return f"Here are {n} similar tracks."
        return "Here are similar tracks."

    if _PLAYLIST_HALLUCINATION.search(text) and track_ids and not playlist_ids:
        n = len(track_ids)
        return f"Here are {n} matching tracks."

    return text


async def _disconnected(check: DisconnectCheck | None) -> bool:
    if check is None:
        return False
    return await check()


async def run_chat_stream(
    messages: list[ChatMessageIn],
    db: AsyncSession,
    user_id: uuid.UUID,
    settings: Settings | None = None,
    *,
    is_disconnected: DisconnectCheck | None = None,
) -> AsyncIterator[ChatStreamEvent]:
    ensure_registered()
    settings = settings or get_settings()
    if not messages:
        raise ChatError("messages must not be empty", status_code=422)
    if messages[-1].role != "user":
        raise ChatError("last message must be from user", status_code=422)

    ctx = ToolContext(db=db, user_id=user_id)
    tools = build_langchain_tools(ctx)
    model = ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        temperature=0.2,
        client_kwargs={"timeout": settings.ollama_timeout_seconds},
    ).bind_tools(tools)

    lc_messages: list[BaseMessage] = [
        SystemMessage(content=SYSTEM_PROMPT),
        *_history_messages(
            messages,
            max_messages=settings.chat_max_history_messages,
        ),
    ]

    traces: list[ToolTrace] = []
    cited: list[str] = []
    seen_ids: set[str] = set()
    similar_cited: list[str] = []
    similar_seen: set[str] = set()
    cited_playlists: list[str] = []
    seen_playlist_ids: set[str] = set()
    partial_text = ""

    def attached_track_ids() -> list[str]:
        # Similarity answers must show graph/ML neighbors only — never metadata lookups.
        return similar_cited if similar_cited else cited

    for _ in range(settings.chat_max_tool_rounds):
        if await _disconnected(is_disconnected):
            raise ChatCancelled(
                ChatResult(
                    content=partial_text.strip(),
                    tool_traces=traces,
                    track_ids=attached_track_ids(),
                    playlist_ids=cited_playlists,
                    cancelled=True,
                )
            )

        yield ChatStreamStatus(phase="thinking")

        assembled: AIMessageChunk | None = None
        round_text = ""
        try:
            async for chunk in model.astream(lc_messages):
                if await _disconnected(is_disconnected):
                    raise ChatCancelled(
                        ChatResult(
                            content=(partial_text + round_text).strip(),
                            tool_traces=traces,
                            track_ids=attached_track_ids(),
                            playlist_ids=cited_playlists,
                            cancelled=True,
                        )
                    )
                if not isinstance(chunk, AIMessageChunk):
                    continue
                assembled = chunk if assembled is None else assembled + chunk
                if chunk.tool_call_chunks:
                    continue
                text = _text_from_content(chunk.content)
                if not text:
                    continue
                round_text += text
                partial_text += text
                yield ChatStreamToken(text=text)
        except ChatCancelled:
            raise
        except Exception as exc:
            logger.exception("Ollama chat stream failed")
            raise ChatError(
                f"Ollama unavailable: {exc}",
                status_code=503,
            ) from exc

        if assembled is None:
            raise ChatError("Unexpected model response", status_code=502)

        ai_msg = AIMessage(
            content=assembled.content,
            tool_calls=assembled.tool_calls or [],
            id=assembled.id,
        )
        lc_messages.append(ai_msg)
        tool_calls = ai_msg.tool_calls or []
        if not tool_calls:
            content = _text_from_content(ai_msg.content).strip()
            if not content:
                raise ChatError("Model returned an empty answer", status_code=502)
            content = _sanitize_final_answer(
                content,
                traces=traces,
                track_ids=attached_track_ids(),
                playlist_ids=cited_playlists,
            )
            yield ChatResult(
                content=content,
                tool_traces=traces,
                track_ids=attached_track_ids(),
                playlist_ids=cited_playlists,
            )
            return

        # Tool-call rounds should not keep streamed text as the answer.
        partial_text = partial_text[: len(partial_text) - len(round_text)]

        for call in tool_calls:
            if await _disconnected(is_disconnected):
                raise ChatCancelled(
                    ChatResult(
                        content="",
                        tool_traces=traces,
                        track_ids=attached_track_ids(),
                        playlist_ids=cited_playlists,
                        cancelled=True,
                    )
                )
            name = call.get("name") or ""
            args = call.get("args") or {}
            call_id = call.get("id") or name
            if not name:
                raise ChatError(
                    "Model issued a tool call without a name",
                    status_code=502,
                )
            yield ChatStreamStatus(phase="tool", name=name)
            try:
                result = await execute(name, args, ctx)
            except KeyError as exc:
                raise ChatError(str(exc), status_code=502) from exc

            ok = "error" not in result.payload
            traces.append(ToolTrace(name=name, args=args, ok=ok))
            if ok:
                if name == "similar_tracks":
                    for track_id in result.track_ids:
                        if track_id not in similar_seen:
                            similar_seen.add(track_id)
                            similar_cited.append(track_id)
                else:
                    for track_id in result.track_ids:
                        if track_id not in seen_ids:
                            seen_ids.add(track_id)
                            cited.append(track_id)
                for playlist_id in result.playlist_ids:
                    if playlist_id not in seen_playlist_ids:
                        seen_playlist_ids.add(playlist_id)
                        cited_playlists.append(playlist_id)

            lc_messages.append(
                ToolMessage(
                    content=json.dumps(result.payload),
                    tool_call_id=call_id,
                )
            )

    fallback = _tool_limit_fallback(
        traces=traces,
        playlist_ids=cited_playlists,
        track_ids=attached_track_ids(),
    )
    if fallback:
        yield ChatResult(
            content=fallback,
            tool_traces=traces,
            track_ids=attached_track_ids(),
            playlist_ids=cited_playlists,
        )
        return

    raise ChatError(
        "Tool round limit reached without a final answer",
        status_code=502,
    )


def _tool_limit_fallback(
    *,
    traces: list[ToolTrace],
    playlist_ids: list[str],
    track_ids: list[str],
) -> str:
    created = any(trace.name == "create_playlist" and trace.ok for trace in traces)
    if playlist_ids:
        if created:
            return "Created the playlist — open the card below."
        return "Here’s the playlist."
    if track_ids:
        return "Here are the matching tracks."
    return ""


async def run_chat(
    messages: list[ChatMessageIn],
    db: AsyncSession,
    user_id: uuid.UUID,
    settings: Settings | None = None,
) -> ChatResult:
    result: ChatResult | None = None
    async for event in run_chat_stream(
        messages,
        db,
        user_id,
        settings=settings,
    ):
        if isinstance(event, ChatResult):
            result = event
    if result is None:
        raise ChatError("Model returned an empty answer", status_code=502)
    return result


async def hydrate_tracks(db: AsyncSession, track_ids: list[str]) -> list[TrackOut]:
    uuids: list[uuid.UUID] = []
    for value in track_ids:
        try:
            uuids.append(uuid.UUID(value))
        except ValueError:
            continue
    if not uuids:
        return []
    rows = await db.scalars(select(Track).where(Track.id.in_(uuids)))
    by_id = {str(track.id): track for track in rows}
    return [
        TrackOut.model_validate(by_id[track_id])
        for track_id in track_ids
        if track_id in by_id
    ]


class PlaylistChatOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    color: str | None = None
    theme_colors: list[str] = Field(default_factory=list)
    track_count: int
    preview_tracks: list[TrackOut] = Field(default_factory=list)


async def hydrate_playlists(
    db: AsyncSession,
    user_id: uuid.UUID,
    playlist_ids: list[str],
) -> list[PlaylistChatOut]:
    from sqlalchemy import func

    from ox1audio_backend.models import Playlist, PlaylistItem
    from ox1audio_backend.services.playlist_colors import theme_hexes

    uuids: list[uuid.UUID] = []
    for value in playlist_ids:
        try:
            uuids.append(uuid.UUID(value))
        except ValueError:
            continue
    if not uuids:
        return []

    rows = await db.scalars(
        select(Playlist).where(Playlist.id.in_(uuids), Playlist.user_id == user_id)
    )
    by_id = {playlist.id: playlist for playlist in rows}
    counts = {
        playlist_id: int(count)
        for playlist_id, count in (
            await db.execute(
                select(PlaylistItem.playlist_id, func.count())
                .where(PlaylistItem.playlist_id.in_(list(by_id.keys()) or uuids))
                .group_by(PlaylistItem.playlist_id)
            )
        ).all()
    }

    out: list[PlaylistChatOut] = []
    for playlist_id in uuids:
        playlist = by_id.get(playlist_id)
        if playlist is None:
            continue
        preview_ids = list(
            await db.scalars(
                select(PlaylistItem.track_id)
                .where(PlaylistItem.playlist_id == playlist.id)
                .order_by(PlaylistItem.position.asc())
                .limit(3)
            )
        )
        preview_tracks: list[TrackOut] = []
        if preview_ids:
            tracks = {
                track.id: track
                for track in await db.scalars(
                    select(Track).where(Track.id.in_(preview_ids))
                )
            }
            preview_tracks = [
                TrackOut.model_validate(tracks[track_id])
                for track_id in preview_ids
                if track_id in tracks
            ]
        out.append(
            PlaylistChatOut(
                id=playlist.id,
                title=playlist.title,
                description=playlist.description,
                color=playlist.color,
                theme_colors=theme_hexes(playlist.color),
                track_count=counts.get(playlist.id, 0),
                preview_tracks=preview_tracks,
            )
        )
    return out
