"""Built-in tool registry for agents."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.tools import BaseTool

from app.engine.tools.handoff import make_handoff_tool
from app.engine.tools.http_fetch import make_http_fetch_tool
from app.engine.tools.web_search import make_web_search_tool

ToolFactory = Callable[[dict[str, Any]], BaseTool]


TOOL_FACTORIES: dict[str, ToolFactory] = {
    "web_search": make_web_search_tool,
    "http_fetch": make_http_fetch_tool,
}


def resolve_tools(
    tool_configs: list[dict[str, Any]],
    handoff_targets: list[str] | None = None,
) -> list[BaseTool]:
    """Translate a list of tool config dicts into instantiated `BaseTool`s."""
    tools: list[BaseTool] = []
    for tc in tool_configs or []:
        kind = tc.get("type")
        config = tc.get("config", {})
        if kind not in TOOL_FACTORIES:
            raise ValueError(f"Unknown tool type: {kind!r}")
        tools.append(TOOL_FACTORIES[kind](config))

    for target in handoff_targets or []:
        tools.append(make_handoff_tool(target))

    return tools


__all__ = ["TOOL_FACTORIES", "resolve_tools", "make_handoff_tool"]
