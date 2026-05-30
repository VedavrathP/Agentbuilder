"""Named routers for conditional edges in user-defined workflows.

A router is a function `(state) -> str | list[Send]` that LangGraph uses to
pick the next node. The factory looks up the router by name from `ROUTERS`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage

RouterFn = Callable[[dict[str, Any]], str]


def _last_ai_text(state: dict[str, Any]) -> str:
    msgs = state.get("messages") or []
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            return m.content if isinstance(m.content, str) else json.dumps(m.content)
        # also handle dict-style messages from invoke shortcuts
        if isinstance(m, dict) and m.get("type") == "ai":
            return str(m.get("content", ""))
    return ""


def keyword_router(spec: dict[str, Any]) -> RouterFn:
    """Pick a branch based on case-insensitive keyword presence in the last AI message.

    `spec` example:
        {"branches": [{"keywords": ["billing", "refund"], "target": "billing_agent"}],
         "default": "tech_agent"}
    """
    branches = spec.get("branches", [])
    default = spec.get("default", "__end__")

    def route(state: dict[str, Any]) -> str:
        text = _last_ai_text(state).lower()
        for b in branches:
            keywords = [k.lower() for k in b.get("keywords", [])]
            if any(k in text for k in keywords):
                return b["target"]
        return default

    return route


def regex_router(spec: dict[str, Any]) -> RouterFn:
    """Pick a branch based on regex match against the last AI message."""
    branches = spec.get("branches", [])
    default = spec.get("default", "__end__")
    compiled = [(re.compile(b["pattern"], re.IGNORECASE), b["target"]) for b in branches]

    def route(state: dict[str, Any]) -> str:
        text = _last_ai_text(state)
        for rx, target in compiled:
            if rx.search(text):
                return target
        return default

    return route


def json_field_router(spec: dict[str, Any]) -> RouterFn:
    """Parse last AI message as JSON, route on a field value.

    spec: {"field": "category", "mapping": {"billing": "billing_agent"}, "default": "tech_agent"}
    """
    field = spec["field"]
    mapping = spec.get("mapping", {})
    default = spec.get("default", "__end__")

    def route(state: dict[str, Any]) -> str:
        text = _last_ai_text(state).strip()
        # Try to extract a JSON object (handles ```json ... ``` fences)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return default
        try:
            obj = json.loads(m.group(0))
        except Exception:  # noqa: BLE001
            return default
        value = str(obj.get(field, "")).lower()
        return mapping.get(value, default)

    return route


ROUTERS: dict[str, Callable[[dict[str, Any]], RouterFn]] = {
    "keyword": keyword_router,
    "regex": regex_router,
    "json_field": json_field_router,
}
