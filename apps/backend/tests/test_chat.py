from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessageChunk

from ox1audio_backend.config import Settings
from ox1audio_backend.services.chat import (
    ChatError,
    ChatMessageIn,
    ChatResult,
    ChatStreamToken,
    ToolTrace,
    _assistant_stalling_on_playlist_prefs,
    _sanitize_final_answer,
    _user_wants_playlist_created,
    run_chat,
    run_chat_stream,
)
from ox1audio_backend.tools.types import ToolResult


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

    with patch("ox1audio_backend.services.chat.ChatOllama") as chat_cls:
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

    with patch("ox1audio_backend.services.chat.ChatOllama") as chat_cls:
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
        patch("ox1audio_backend.services.chat.ChatOllama") as chat_cls,
        patch(
            "ox1audio_backend.services.chat.execute",
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
        patch("ox1audio_backend.services.chat.ChatOllama") as chat_cls,
        patch(
            "ox1audio_backend.services.chat.execute",
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
        patch("ox1audio_backend.services.chat.ChatOllama") as chat_cls,
        patch(
            "ox1audio_backend.services.chat.execute",
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

    with patch("ox1audio_backend.services.chat.ChatOllama") as chat_cls:
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


def test_sanitize_replaces_playlist_hallucination_after_similar() -> None:
    traces = [ToolTrace(name="similar_tracks", args={}, ok=True)]
    cleaned = _sanitize_final_answer(
        "All retrieved playlists have been updated with the light_blue mood color.",
        traces=traces,
        track_ids=["a", "b", "c"],
        playlist_ids=[],
    )
    assert cleaned == "Here are 3 similar tracks."


def test_sanitize_keeps_real_playlist_confirmation() -> None:
    traces = [ToolTrace(name="create_playlist", args={}, ok=True)]
    text = "Created a playlist with a washed_blue mood color."
    cleaned = _sanitize_final_answer(
        text,
        traces=traces,
        track_ids=["a"],
        playlist_ids=["p1"],
    )
    assert cleaned == text


def test_playlist_create_intent_and_stall_detection() -> None:
    assert _user_wants_playlist_created("Can you create me a playlist?")
    assert _user_wants_playlist_created("please make a playlist of these")
    assert not _user_wants_playlist_created("what is in my playlist?")
    assert _assistant_stalling_on_playlist_prefs(
        "Sure! What would you like to name the playlist, and which mood color "
        "(e.g., light_blue, teal, dark_blue, etc.) should I use for it?"
    )
    assert not _assistant_stalling_on_playlist_prefs("Created the playlist — open the card below.")


@pytest.mark.asyncio
async def test_playlist_pref_stall_auto_creates(settings: Settings, user_id) -> None:
    db = MagicMock()
    stall = AIMessageChunk(
        content=(
            "Sure! What would you like to name the playlist, and which mood color "
            "(e.g., light_blue, teal) should I use?"
        )
    )
    playlist_id = "22222222-2222-2222-2222-222222222222"
    created = ToolResult(
        payload={"playlist": {"id": playlist_id, "title": "New playlist"}},
        playlist_ids=[playlist_id],
    )

    with (
        patch("ox1audio_backend.services.chat.ChatOllama") as chat_cls,
        patch(
            "ox1audio_backend.services.chat.execute",
            new=AsyncMock(return_value=created),
        ) as execute_mock,
    ):
        _bind_astream(chat_cls, [_chunks(stall), _chunks(stall)])
        result = await run_chat(
            [ChatMessageIn(role="user", content="Can you create me a playlist?")],
            db,
            user_id,
            settings=settings,
        )

    assert result.content == "Created the playlist — open the card below."
    assert result.playlist_ids == [playlist_id]
    assert any(trace.name == "create_playlist" and trace.ok for trace in result.tool_traces)
    execute_mock.assert_awaited()
    assert execute_mock.await_args.args[0] == "create_playlist"
    assert execute_mock.await_args.args[1]["color"]
    assert execute_mock.await_args.args[1]["title"] == "New playlist"
