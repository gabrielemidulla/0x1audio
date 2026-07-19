from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ToolContext:
    db: AsyncSession
    user_id: UUID


@dataclass
class ToolResult:
    payload: dict[str, Any]
    track_ids: list[str] = field(default_factory=list)
    playlist_ids: list[str] = field(default_factory=list)

    @classmethod
    def error(cls, message: str) -> ToolResult:
        return cls(payload={"error": message})


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[..., Awaitable[ToolResult]]

    def json_schema(self) -> dict[str, Any]:
        schema = self.args_model.model_json_schema()
        schema.pop("title", None)
        return schema
