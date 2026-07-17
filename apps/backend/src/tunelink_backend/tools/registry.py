from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from tunelink_backend.tools.types import ToolContext, ToolResult, ToolSpec

_REGISTRY: dict[str, ToolSpec] = {}


def register(spec: ToolSpec) -> ToolSpec:
    if spec.name in _REGISTRY:
        raise ValueError(f"Tool already registered: {spec.name}")
    _REGISTRY[spec.name] = spec
    return spec


def list_specs() -> list[ToolSpec]:
    return list(_REGISTRY.values())


def get_spec(name: str) -> ToolSpec | None:
    return _REGISTRY.get(name)


async def execute(
    name: str,
    args: dict[str, Any],
    ctx: ToolContext,
) -> ToolResult:
    spec = _REGISTRY.get(name)
    if spec is None:
        raise KeyError(f"Unknown tool: {name}")
    try:
        parsed: BaseModel = spec.args_model.model_validate(args)
    except ValidationError as exc:
        return ToolResult.error(str(exc))
    return await spec.handler(ctx, parsed)
