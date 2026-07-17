from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tunelink_backend.api.catalog import TrackOut
from tunelink_backend.auth.deps import get_current_user
from tunelink_backend.db import SessionLocal, get_db
from tunelink_backend.models import Chat, ChatMessage, User
from tunelink_backend.services.chat import (
    ChatCancelled,
    ChatError,
    ChatMessageIn,
    ChatResult,
    ChatStreamStatus,
    ChatStreamToken,
    PlaylistChatOut,
    hydrate_playlists,
    hydrate_tracks,
    run_chat,
    run_chat_stream,
)

router = APIRouter()
logger = logging.getLogger(__name__)

TITLE_MAX = 80


class CreateChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class AppendMessageBody(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class ToolTraceOut(BaseModel):
    name: str
    args: dict[str, Any]
    ok: bool


class ChatSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    tool_traces: list[ToolTraceOut] | None = None
    track_ids: list[str] | None = None
    playlist_ids: list[str] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatDetailOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageOut]
    tracks: list[TrackOut] = []
    playlists: list[PlaylistChatOut] = []


class AppendMessageOut(BaseModel):
    messages: list[ChatMessageOut]
    tracks: list[TrackOut]
    playlists: list[PlaylistChatOut] = []


def _title_from_prompt(message: str) -> str:
    text = " ".join(message.strip().split())
    if len(text) <= TITLE_MAX:
        return text
    return text[: TITLE_MAX - 1].rstrip() + "…"


def _message_out(row: ChatMessage) -> ChatMessageOut:
    traces = None
    if row.tool_traces:
        traces = [ToolTraceOut.model_validate(item) for item in row.tool_traces]
    return ChatMessageOut(
        id=row.id,
        role=row.role,  # type: ignore[arg-type]
        content=row.content,
        tool_traces=traces,
        track_ids=row.track_ids,
        playlist_ids=row.playlist_ids,
        created_at=row.created_at,
    )


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _assistant_row(chat_id: uuid.UUID, result: ChatResult) -> ChatMessage:
    return ChatMessage(
        chat_id=chat_id,
        role="assistant",
        content=result.content.strip(),
        tool_traces=[
            {"name": t.name, "args": t.args, "ok": t.ok} for t in result.tool_traces
        ]
        or None,
        track_ids=result.track_ids or None,
        playlist_ids=result.playlist_ids or None,
    )


async def _get_owned_chat(
    db: AsyncSession,
    chat_id: uuid.UUID,
    user: User,
) -> Chat:
    chat = await db.scalar(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id)
    )
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return chat


async def _load_history(db: AsyncSession, chat_id: uuid.UUID) -> list[ChatMessage]:
    rows = await db.scalars(
        select(ChatMessage)
        .where(ChatMessage.chat_id == chat_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return list(rows)


def _history_for_llm(rows: list[ChatMessage]) -> list[ChatMessageIn]:
    return [
        ChatMessageIn(role=row.role, content=row.content)  # type: ignore[arg-type]
        for row in rows
        if row.role in ("user", "assistant")
    ]


async def _stream_assistant(
    *,
    request: Request,
    db: AsyncSession,
    chat: Chat,
    llm_messages: list[ChatMessageIn],
    user_id: uuid.UUID,
) -> AsyncIterator[str]:
    final: ChatResult | None = None
    try:
        async for event in run_chat_stream(
            llm_messages,
            db,
            user_id,
            is_disconnected=request.is_disconnected,
        ):
            if isinstance(event, ChatStreamStatus):
                yield _sse(
                    {
                        "type": "status",
                        "phase": event.phase,
                        "name": event.name,
                    }
                )
            elif isinstance(event, ChatStreamToken):
                yield _sse({"type": "token", "text": event.text})
            elif isinstance(event, ChatResult):
                final = event
    except ChatCancelled as exc:
        final = exc.partial
        yield _sse({"type": "status", "phase": "cancelled"})
    except ChatError as exc:
        yield _sse({"type": "error", "detail": exc.message, "status": exc.status_code})
        return
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Chat stream failed")
        yield _sse({"type": "error", "detail": "Chat failed", "status": 500})
        return

    if final is None:
        yield _sse({"type": "error", "detail": "Model returned an empty answer", "status": 502})
        return

    if final.cancelled and not final.content.strip():
        await db.commit()
        yield _sse(
            {
                "type": "done",
                "cancelled": True,
                "message": None,
                "tracks": [],
                "playlists": [],
            }
        )
        return

    assistant = _assistant_row(chat.id, final)
    db.add(assistant)
    chat.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(assistant)
    await db.refresh(chat)
    tracks = await hydrate_tracks(db, final.track_ids)
    playlists = await hydrate_playlists(db, user_id, final.playlist_ids)
    yield _sse(
        {
            "type": "done",
            "cancelled": final.cancelled,
            "message": _message_out(assistant).model_dump(mode="json"),
            "tracks": [track.model_dump(mode="json") for track in tracks],
            "playlists": [playlist.model_dump(mode="json") for playlist in playlists],
        }
    )


@router.post("", response_model=ChatDetailOut, operation_id="createChat")
async def create_chat(
    body: CreateChatBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatDetailOut:
    """Create a chat and persist the first user message (reply via stream)."""
    chat = Chat(user_id=user.id, title=_title_from_prompt(body.message))
    db.add(chat)
    await db.flush()

    user_msg = ChatMessage(chat_id=chat.id, role="user", content=body.message.strip())
    db.add(user_msg)
    await db.commit()
    await db.refresh(chat)
    await db.refresh(user_msg)

    return ChatDetailOut(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        messages=[_message_out(user_msg)],
        tracks=[],
    )


@router.get("", response_model=list[ChatSummaryOut], operation_id="listChats")
async def list_chats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Chat]:
    rows = await db.scalars(
        select(Chat)
        .where(Chat.user_id == user.id)
        .order_by(Chat.updated_at.desc())
    )
    return list(rows)


@router.get("/{chat_id}", response_model=ChatDetailOut, operation_id="getChat")
async def get_chat(
    chat_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatDetailOut:
    chat = await _get_owned_chat(db, chat_id, user)
    messages = await _load_history(db, chat.id)
    track_ids: list[str] = []
    seen_tracks: set[str] = set()
    playlist_ids: list[str] = []
    seen_playlists: set[str] = set()
    for message in messages:
        if message.track_ids:
            for track_id in message.track_ids:
                if track_id not in seen_tracks:
                    seen_tracks.add(track_id)
                    track_ids.append(track_id)
        if message.playlist_ids:
            for playlist_id in message.playlist_ids:
                if playlist_id not in seen_playlists:
                    seen_playlists.add(playlist_id)
                    playlist_ids.append(playlist_id)
    tracks = await hydrate_tracks(db, track_ids)
    playlists = await hydrate_playlists(db, user.id, playlist_ids)
    return ChatDetailOut(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        messages=[_message_out(m) for m in messages],
        tracks=tracks,
        playlists=playlists,
    )


@router.post(
    "/{chat_id}/messages",
    response_model=AppendMessageOut,
    operation_id="appendChatMessage",
)
async def append_chat_message(
    chat_id: uuid.UUID,
    body: AppendMessageBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AppendMessageOut:
    chat = await _get_owned_chat(db, chat_id, user)
    history = await _load_history(db, chat.id)

    user_msg = ChatMessage(
        chat_id=chat.id,
        role="user",
        content=body.message.strip(),
    )
    db.add(user_msg)
    await db.flush()

    llm_messages = _history_for_llm(history) + [
        ChatMessageIn(role="user", content=user_msg.content)
    ]
    try:
        result = await run_chat(llm_messages, db, user.id)
    except ChatError as exc:
        await db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    assistant = _assistant_row(chat.id, result)
    db.add(assistant)
    chat.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant)
    await db.refresh(chat)

    tracks = await hydrate_tracks(db, result.track_ids)
    playlists = await hydrate_playlists(db, user.id, result.playlist_ids)
    return AppendMessageOut(
        messages=[_message_out(user_msg), _message_out(assistant)],
        tracks=tracks,
        playlists=playlists,
    )


@router.post("/{chat_id}/reply/stream", operation_id="streamChatReply")
async def stream_chat_reply(
    chat_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    user_id = user.id

    async def events() -> AsyncIterator[str]:
        async with SessionLocal() as db:
            try:
                chat = await db.scalar(
                    select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
                )
                if chat is None:
                    yield _sse({"type": "error", "detail": "Chat not found", "status": 404})
                    return
                history = await _load_history(db, chat.id)
                if not history or history[-1].role != "user":
                    yield _sse(
                        {
                            "type": "error",
                            "detail": "Nothing to reply to",
                            "status": 422,
                        }
                    )
                    return
                llm_messages = _history_for_llm(history)
                async for chunk in _stream_assistant(
                    request=request,
                    db=db,
                    chat=chat,
                    llm_messages=llm_messages,
                    user_id=user_id,
                ):
                    yield chunk
            except asyncio.CancelledError:
                try:
                    await db.rollback()
                except Exception:
                    logger.exception("Failed to rollback reply stream after cancel")
                raise

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{chat_id}/messages/stream", operation_id="streamChatMessage")
async def stream_chat_message(
    chat_id: uuid.UUID,
    body: AppendMessageBody,
    request: Request,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    user_id = user.id
    message = body.message.strip()

    async def events() -> AsyncIterator[str]:
        async with SessionLocal() as db:
            try:
                chat = await db.scalar(
                    select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
                )
                if chat is None:
                    yield _sse({"type": "error", "detail": "Chat not found", "status": 404})
                    return
                history = await _load_history(db, chat.id)
                user_msg = ChatMessage(
                    chat_id=chat.id,
                    role="user",
                    content=message,
                )
                db.add(user_msg)
                chat.updated_at = datetime.now(timezone.utc)
                await db.commit()
                await db.refresh(user_msg)
                yield _sse(
                    {
                        "type": "user",
                        "message": _message_out(user_msg).model_dump(mode="json"),
                    }
                )
                llm_messages = _history_for_llm(history) + [
                    ChatMessageIn(role="user", content=user_msg.content)
                ]
                async for chunk in _stream_assistant(
                    request=request,
                    db=db,
                    chat=chat,
                    llm_messages=llm_messages,
                    user_id=user_id,
                ):
                    yield chunk
            except asyncio.CancelledError:
                try:
                    await db.rollback()
                except Exception:
                    logger.exception("Failed to rollback message stream after cancel")
                raise

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
