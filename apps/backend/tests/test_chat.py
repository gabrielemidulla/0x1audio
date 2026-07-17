from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessageChunk

from tunelink_backend.config import Settings
from tunelink_backend.services.chat import (
    ChatError,
    ChatMessageIn,
    ChatResult,
    ChatStreamToken,
    run_chat,
    run_chat_stream,
)
from tunelink_backend.tools.types import ToolResult


@pytest.fixture
def settings() -> Settings:
    return Settings(
        ollama_base_url="http://ollama.test",
        ollama_model="lfm2.5:8b",
        chat_max_tool_rounds=3,
        chat_max_history_messages=20,
    )


@pytest.fixture
def user_id():
    return uuid4()


def _bind_astream(chat_cls: MagicMock, streams: list[AsyncIterator[AIMessageChunk]]) -> None:
    bound = MagicMock()
    bound.astream = MagicMock(side_effect=streams)
    instance = MagicMock()
    instance.bind_tools.return_value = bound
    chat_cls.return_value = instance


async def _chunks(*parts: AIMessageChunk) -> AsyncIterator[AIMessageChunk]:
    for part in parts:
        yield part


@pytest.mark.asyncio
async def test_run_chat_final_answer_without_tools(settings: Settings, user_id) -> None:
    db = MagicMock()

    with patch("tunelink_backend.services.chat.ChatOllama") as chat_cls:
        _bind_astream(
            chat_cls,
            [_chunks(AIMessageChunk(content="Your library looks healthy."))],
        )
        result = await run_chat(
            [ChatMessageIn(role="user", content="How is my library?")],
            db,
            user_id,
            settings=settings,
        )

    assert result.content == "Your library looks healthy."
    assert result.tool_traces == []
    assert result.track_ids == []


@pytest.mark.asyncio
async def test_run_chat_stream_yields_tokens(settings: Settings, user_id) -> None:
    db = MagicMock()
    tokens: list[str] = []

    with patch("tunelink_backend.services.chat.ChatOllama") as chat_cls:
        _bind_astream(
            chat_cls,
            [
                _chunks(
                    AIMessageChunk(content="Hello "),
                    AIMessageChunk(content="there."),
                )
            ],
        )
        async for event in run_chat_stream(
            [ChatMessageIn(role="user", content="Hi")],
            db,
            user_id,
            settings=settings,
        ):
            if isinstance(event, ChatStreamToken):
                tokens.append(event.text)
            elif isinstance(event, ChatResult):
                assert event.content == "Hello there."

    assert tokens == ["Hello ", "there."]


@pytest.mark.asyncio
async def test_run_chat_tool_then_answer(settings: Settings, user_id) -> None:
    db = MagicMock()
    tool_chunk = AIMessageChunk(
        content="",
        tool_call_chunks=[
            {
                "name": "library_stats",
                "args": "{}",
                "id": "call_1",
                "index": 0,
                "type": "tool_call_chunk",
            }
        ],
    )
    final_chunk = AIMessageChunk(content="You have 12 ready tracks.")

    with (
        patch("tunelink_backend.services.chat.ChatOllama") as chat_cls,
        patch(
            "tunelink_backend.services.chat.execute",
            new=AsyncMock(
                return_value=ToolResult(
                    payload={"total": 12, "by_status": {"ready": 12}},
                    track_ids=[],
                )
            ),
        ) as execute_mock,
    ):
        _bind_astream(chat_cls, [_chunks(tool_chunk), _chunks(final_chunk)])
        result = await run_chat(
            [ChatMessageIn(role="user", content="Stats?")],
            db,
            user_id,
            settings=settings,
        )

    assert result.content == "You have 12 ready tracks."
    assert len(result.tool_traces) == 1
    assert result.tool_traces[0].name == "library_stats"
    assert result.tool_traces[0].ok is True
    execute_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_chat_round_limit_errors(settings: Settings, user_id) -> None:
    settings = settings.model_copy(update={"chat_max_tool_rounds": 1})
    db = MagicMock()
    tool_chunk = AIMessageChunk(
        content="",
        tool_call_chunks=[
            {
                "name": "library_stats",
                "args": "{}",
                "id": "call_1",
                "index": 0,
                "type": "tool_call_chunk",
            }
        ],
    )

    with (
        patch("tunelink_backend.services.chat.ChatOllama") as chat_cls,
        patch(
            "tunelink_backend.services.chat.execute",
            new=AsyncMock(return_value=ToolResult(payload={"total": 1})),
        ),
    ):
        _bind_astream(chat_cls, [_chunks(tool_chunk)])
        with pytest.raises(ChatError) as exc_info:
            await run_chat(
                [ChatMessageIn(role="user", content="Stats?")],
                db,
                user_id,
                settings=settings,
            )

    assert exc_info.value.status_code == 502
    assert "round limit" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_run_chat_round_limit_falls_back_with_playlist(
    settings: Settings, user_id
) -> None:
    settings = settings.model_copy(update={"chat_max_tool_rounds": 1})
    db = MagicMock()
    tool_chunk = AIMessageChunk(
        content="",
        tool_call_chunks=[
            {
                "name": "create_playlist",
                "args": "{}",
                "id": "call_1",
                "index": 0,
                "type": "tool_call_chunk",
            }
        ],
    )
    playlist_id = "11111111-1111-1111-1111-111111111111"

    with (
        patch("tunelink_backend.services.chat.ChatOllama") as chat_cls,
        patch(
            "tunelink_backend.services.chat.execute",
            new=AsyncMock(
                return_value=ToolResult(
                    payload={"playlist": {"id": playlist_id, "title": "Rain"}},
                    playlist_ids=[playlist_id],
                )
            ),
        ),
    ):
        _bind_astream(chat_cls, [_chunks(tool_chunk)])
        result = await run_chat(
            [ChatMessageIn(role="user", content="Make a rainy playlist")],
            db,
            user_id,
            settings=settings,
        )

    assert "playlist" in result.content.lower()
    assert result.playlist_ids == [playlist_id]
    assert result.tool_traces[0].name == "create_playlist"


@pytest.mark.asyncio
async def test_run_chat_ollama_down_is_503(settings: Settings, user_id) -> None:
    db = MagicMock()

    with patch("tunelink_backend.services.chat.ChatOllama") as chat_cls:
        bound = MagicMock()
        bound.astream = MagicMock(side_effect=ConnectionError("refused"))
        instance = MagicMock()
        instance.bind_tools.return_value = bound
        chat_cls.return_value = instance

        with pytest.raises(ChatError) as exc_info:
            await run_chat(
                [ChatMessageIn(role="user", content="Hi")],
                db,
                user_id,
                settings=settings,
            )

    assert exc_info.value.status_code == 503
