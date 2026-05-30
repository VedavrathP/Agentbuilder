"""Web search tool — uses DuckDuckGo (free, no API key) via the `ddgs` package."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool


def make_web_search_tool(config: dict[str, Any] | None = None) -> BaseTool:
    config = config or {}
    max_results = int(config.get("max_results", 5))

    @tool("web_search")
    def web_search(query: str) -> str:
        """Search the web for current information.

        Args:
            query: search query string

        Returns a markdown-formatted list of top results (title, url, snippet).
        """
        from ddgs import DDGS

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        except Exception as exc:  # noqa: BLE001
            return f"web_search failed: {exc}"

        if not results:
            return f"No results found for: {query}"

        lines = [f"Search results for: {query}", ""]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            href = r.get("href") or r.get("url", "")
            body = r.get("body", "")
            lines.append(f"{i}. [{title}]({href})\n   {body}")
        return "\n".join(lines)

    return web_search
