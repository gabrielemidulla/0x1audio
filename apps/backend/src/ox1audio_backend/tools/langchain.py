from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import StructuredTool

from ox1audio_backend.tools import registry
from ox1audio_backend.tools.types import ToolContext, ToolResult, ToolSpec


def build_langchain_tools(ctx: ToolContext) -> list[StructuredTool]:
    """Wrap registry specs as LangChain tools for ChatOllama.bind_tools.

    The chat orchestrator executes via registry.execute; these tools supply schemas
    (and remain callable if invoked).
    """
    return [_structured_tool(spec, ctx) for spec in registry.list_specs()]


def _structured_tool(spec: ToolSpec, ctx: ToolContext) -> StructuredTool:
    name = spec.name

    async def _run(**kwargs: Any) -> str:
        result: ToolResult = await registry.execute(name, kwargs, ctx)
        return json.dumps(result.payload)

    return StructuredTool.from_function(
        coroutine=_run,
        name=spec.name,
        description=spec.description,
        args_schema=spec.args_model,
    )
