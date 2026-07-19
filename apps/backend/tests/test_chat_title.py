from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ox1audio_backend.config import Settings
from ox1audio_backend.services.chat_title import (
    _clean_title,
    fallback_title,
    generate_chat_title,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        ollama_base_url="http://ollama.test",
        ollama_model="lfm2.5:8b",
        ollama_title_model="LiquidAI/lfm2.5-1.2b-instruct",
        ollama_title_timeout_seconds=5.0,
    )


def test_fallback_title_truncates() -> None:
    long = "x" * 120
    title = fallback_title(long)
    assert len(title) <= 80
    assert title.endswith("…")


def test_clean_title_strips_quotes_and_prefix() -> None:
    assert _clean_title('"Ghost Town Similar Tracks"', fallback="fallback") == (
        "Ghost Town Similar Tracks"
    )
    assert _clean_title("Title: Chill sunset mix", fallback="fallback") == (
        "Chill sunset mix"
    )


def test_clean_title_parses_json_and_think_blocks() -> None:
    assert _clean_title(
        '<think>planning...</think>\n{"title": "Ghost Town Similar Tracks"}',
        fallback="fallback",
    ) == "Ghost Town Similar Tracks"


@pytest.mark.asyncio
async def test_generate_chat_title_uses_ollama_chat_api(settings: Settings) -> None:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "message": {"content": '{"title": "Similar to Ghost Town"}'}
    }

    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "ox1audio_backend.services.chat_title.httpx.AsyncClient",
        return_value=client,
    ):
        title = await generate_chat_title(
            "find similar songs to Ghost Town of Arcando",
            settings=settings,
        )

    assert title == "Similar to Ghost Town"
    kwargs = client.post.call_args
    assert kwargs.args[0] == "http://ollama.test/api/chat"
    body = kwargs.kwargs["json"]
    assert body["think"] is False
    assert body["format"]["required"] == ["title"]
    assert body["options"]["num_predict"] == 64
    assert body["model"] == "LiquidAI/lfm2.5-1.2b-instruct"


@pytest.mark.asyncio
async def test_generate_chat_title_falls_back_on_error(settings: Settings) -> None:
    client = AsyncMock()
    client.post = AsyncMock(side_effect=RuntimeError("ollama down"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "ox1audio_backend.services.chat_title.httpx.AsyncClient",
        return_value=client,
    ):
        title = await generate_chat_title("hello world", settings=settings)

    assert title == "hello world"
