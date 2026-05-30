"""HTTP fetch tool with timeout + optional domain allowlist."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
from langchain_core.tools import BaseTool, tool


def make_http_fetch_tool(config: dict[str, Any] | None = None) -> BaseTool:
    config = config or {}
    timeout_seconds = float(config.get("timeout_seconds", 10.0))
    max_bytes = int(config.get("max_bytes", 10_000))
    allowed_domains: list[str] = list(config.get("allowed_domains", []))

    @tool("http_fetch")
    def http_fetch(url: str) -> str:
        """Fetch a URL and return its response body (truncated to ~10KB).

        Args:
            url: fully-qualified http(s) URL
        """
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return f"Refusing to fetch non-http(s) URL: {url}"
        if allowed_domains and parsed.hostname not in allowed_domains:
            return (
                f"Domain {parsed.hostname!r} is not in the allowlist "
                f"({', '.join(allowed_domains)})."
            )
        try:
            r = httpx.get(url, timeout=timeout_seconds, follow_redirects=True)
            r.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return f"http_fetch failed: {exc}"
        text = r.text[:max_bytes]
        suffix = "\n…[truncated]" if len(r.text) > max_bytes else ""
        return f"HTTP {r.status_code} {url}\n\n{text}{suffix}"

    return http_fetch
