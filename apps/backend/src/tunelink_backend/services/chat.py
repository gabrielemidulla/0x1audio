from __future__ import annotations

import json
import logging
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

from tunelink_backend.api.catalog import TrackOut
from tunelink_backend.config import Settings, get_settings
from tunelink_backend.models import Track
from tunelink_backend.tools import ensure_registered, execute
from tunelink_backend.tools.langchain import build_langchain_tools
from tunelink_backend.tools.types import ToolContext

logger = logging.getLogger(__name__)

DisconnectCheck = Callable[[], Awaitable[bool]]

SYSTEM_PROMPT = """\
You are Tunelink's catalog librarian. Answer using only information from tool results.
Use tools for any question about the user's music library, similarity, vibes, or playlists.
Never invent tracks, artists, playlists, or metadata that tools did not return.

Search tools — pick the right one:
- search_metadata: when the user names a title, artist, or exact phrase (text match).
- search_vibe: when the user describes mood, vibe, genre feel, or sonic qualities (AI/ML).
- similar_tracks: when finding songs that sound like a known track_id (AI/ML).

Playlist requests (create / build / make a mix / assemble a list):
- You MUST finish by calling create_playlist (or add_tracks_to_playlist on an existing id).
- Typical flow: search_vibe / similar_tracks → collect track ids → create_playlist with those ids.
- Request top_k close to the size the user asked for (cap 20).
- list_playlists / get_playlist before editing an existing list.
- Never invent playlist_id or track_id values — only use ids returned by tools.
- After creating, your next message must be a short confirmation only — no more tools.
- To show a playlist in the UI, call get_playlist (or create/update tools). Never paste playlist ids.

Tool results are machine data for you — never describe their schema fields to the user
(no talk of scores, segment coverage, match scopes, statuses, or “shared entries”).

Tracks and playlists returned by tools are attached automatically in the UI — do not list
track/playlist ids, and do not dump full track lists in prose. Prefer a short summary
(count, vibe, what you found) and optionally name at most one or two tracks if that helps.
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


class ChatError(Exception):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


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
    cited_playlists: list[str] = []
    seen_playlist_ids: set[str] = set()
    partial_text = ""

    for _ in range(settings.chat_max_tool_rounds):
        if await _disconnected(is_disconnected):
            raise ChatCancelled(
                ChatResult(
                    content=partial_text.strip(),
                    tool_traces=traces,
                    track_ids=cited,
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
                            track_ids=cited,
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
            yield ChatResult(
                content=content,
                tool_traces=traces,
                track_ids=cited,
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
                        track_ids=cited,
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
        track_ids=cited,
    )
    if fallback:
        yield ChatResult(
            content=fallback,
            tool_traces=traces,
            track_ids=cited,
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
    track_count: int
    preview_tracks: list[TrackOut] = Field(default_factory=list)


async def hydrate_playlists(
    db: AsyncSession,
    user_id: uuid.UUID,
    playlist_ids: list[str],
) -> list[PlaylistChatOut]:
    from sqlalchemy import func

    from tunelink_backend.models import Playlist, PlaylistItem

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
                track_count=counts.get(playlist.id, 0),
                preview_tracks=preview_tracks,
            )
        )
    return out
