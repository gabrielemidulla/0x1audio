from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid

import httpx
from sqlalchemy import select

from ox1audio_backend.config import Settings, get_settings
from ox1audio_backend.db import SessionLocal
from ox1audio_backend.models import Chat, ChatMessage

logger = logging.getLogger(__name__)

TITLE_MAX = 80
_PROMPT_SNIPPET = 400
_TITLE_NUM_CTX = 512
_TITLE_NUM_PREDICT = 64
_BACKFILL_CONCURRENCY = 2
_BACKFILL_BATCH = 200

_TITLE_SYSTEM = (
    "Create a short chat title for the user's first message. "
    'Return JSON only: {"title": "..."}. '
    "The title must be 2 to 6 words, no quotes inside the value."
)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_TITLE_FORMAT = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
}

_tasks: dict[uuid.UUID, asyncio.Task[str]] = {}


def fallback_title(message: str) -> str:
    text = " ".join(message.strip().split())
    if not text:
        return "New chat"
    if len(text) <= TITLE_MAX:
        return text
    return text[: TITLE_MAX - 1].rstrip() + "…"


def _clean_title(raw: str, *, fallback: str) -> str:
    text = _THINK_BLOCK.sub("", raw)
    if "</think>" in text.lower():
        text = re.split(r"</think>", text, flags=re.IGNORECASE)[-1]
    text = text.strip()
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and isinstance(parsed.get("title"), str):
                text = parsed["title"]
        except json.JSONDecodeError:
            pass
    text = " ".join(text.strip().split())
    text = text.strip("\"'`“”‘’")
    text = re.sub(r"^(title|chat title)\s*:\s*", "", text, flags=re.IGNORECASE)
    text = text.strip(" .")
    if not text:
        return fallback
    if len(text) > TITLE_MAX:
        text = text[: TITLE_MAX - 1].rstrip() + "…"
    return text


async def generate_chat_title(
    message: str,
    settings: Settings | None = None,
) -> str:
    """Ask Ollama for a title with thinking disabled; fall back to a truncated prompt."""
    settings = settings or get_settings()
    snippet = " ".join(message.strip().split())[:_PROMPT_SNIPPET]
    fallback = fallback_title(snippet)
    if not snippet:
        return fallback

    model_name = (settings.ollama_title_model or settings.ollama_model).strip()
    url = settings.ollama_base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model_name,
        "stream": False,
        "think": False,
        "format": _TITLE_FORMAT,
        "options": {
            "temperature": 0.2,
            "num_ctx": _TITLE_NUM_CTX,
            "num_predict": _TITLE_NUM_PREDICT,
        },
        "messages": [
            {"role": "system", "content": _TITLE_SYSTEM},
            {"role": "user", "content": snippet},
        ],
    }
    try:
        timeout = httpx.Timeout(settings.ollama_title_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        content = (data.get("message") or {}).get("content") or ""
        title = _clean_title(content, fallback=fallback)
        if title == fallback and content.strip() == "":
            logger.warning("Chat title model returned empty content; using fallback")
        return title
    except Exception:
        logger.exception("Chat title generation failed; using fallback")
        return fallback


async def persist_chat_title(
    chat_id: uuid.UUID,
    title: str,
    *,
    force: bool = False,
) -> str:
    async with SessionLocal() as db:
        chat = await db.get(Chat, chat_id)
        if chat is None:
            return title
        if chat.title_llm and chat.title.strip() and not force:
            return chat.title
        chat.title = title
        chat.title_llm = True
        await db.commit()
        return title


async def assign_chat_title(
    chat_id: uuid.UUID,
    message: str,
    settings: Settings | None = None,
    *,
    force: bool = False,
) -> str:
    title = await generate_chat_title(message, settings=settings)
    return await persist_chat_title(chat_id, title, force=force)


def schedule_chat_title(
    chat_id: uuid.UUID,
    message: str,
    settings: Settings | None = None,
) -> asyncio.Task[str]:
    existing = _tasks.get(chat_id)
    if existing is not None and not existing.done():
        return existing

    task = asyncio.create_task(
        assign_chat_title(chat_id, message, settings=settings),
        name=f"chat-title-{chat_id}",
    )
    _tasks[chat_id] = task

    def _cleanup(done: asyncio.Task[str]) -> None:
        current = _tasks.get(chat_id)
        if current is done:
            _tasks.pop(chat_id, None)

    task.add_done_callback(_cleanup)
    return task


async def backfill_chat_titles(
    *,
    settings: Settings | None = None,
    limit: int = _BACKFILL_BATCH,
) -> int:
    """Fill LLM titles for chats that never got one (`title_llm` is false)."""
    settings = settings or get_settings()
    async with SessionLocal() as db:
        rows = await db.scalars(
            select(Chat)
            .where(Chat.title_llm.is_(False))
            .order_by(Chat.created_at.asc())
            .limit(limit)
        )
        chats = list(rows)
        jobs: list[tuple[uuid.UUID, str]] = []
        for chat in chats:
            first = await db.scalar(
                select(ChatMessage)
                .where(ChatMessage.chat_id == chat.id, ChatMessage.role == "user")
                .order_by(ChatMessage.created_at.asc())
                .limit(1)
            )
            if first is None or not first.content.strip():
                continue
            jobs.append((chat.id, first.content))

    if not jobs:
        return 0

    sem = asyncio.Semaphore(_BACKFILL_CONCURRENCY)

    async def _one(chat_id: uuid.UUID, message: str) -> None:
        async with sem:
            try:
                await assign_chat_title(chat_id, message, settings=settings)
            except Exception:
                logger.exception("Chat title backfill failed for %s", chat_id)

    await asyncio.gather(*[_one(chat_id, message) for chat_id, message in jobs])
    logger.info("Backfilled %s chat titles", len(jobs))
    return len(jobs)


def start_title_backfill() -> asyncio.Task[int]:
    async def _run() -> int:
        try:
            return await backfill_chat_titles()
        except Exception:
            logger.exception("Chat title backfill crashed")
            return 0

    return asyncio.create_task(_run(), name="chat-title-backfill")
