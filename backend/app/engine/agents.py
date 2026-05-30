"""Agent factories — wrap LangChain's `create_agent` with our user config schema."""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.engine.tools import resolve_tools


def _compose_system_prompt(node_data: dict[str, Any]) -> str:
    """Fold the agent's ``skills`` and node-level ``interaction_rules`` into the
    base system prompt so they actually influence behaviour.

    Workflow- and entry-level interaction rules are injected separately as a
    seed ``SystemMessage`` (see ``engine.memory``); these are the per-node rules
    attached to a specific agent definition.
    """
    base = (node_data.get("system_prompt") or "").strip()
    parts: list[str] = [base] if base else []

    skills = [str(s).strip() for s in (node_data.get("skills") or []) if str(s).strip()]
    if skills:
        parts.append("Your skills: " + ", ".join(skills) + ".")

    rules = [str(r).strip() for r in (node_data.get("interaction_rules") or []) if str(r).strip()]
    if rules:
        parts.append(
            "Always follow these interaction rules:\n"
            + "\n".join(f"- {r}" for r in rules)
        )

    return "\n\n".join(parts)


def make_agent_node(node_data: dict[str, Any]) -> Any:
    """Build a compiled agent ready to be added as a node in a parent StateGraph.

    Expected ``node_data`` keys:
        - name (str)
        - role (str, optional, informational)
        - system_prompt (str)
        - model (str, e.g. "gpt-4o-mini")
        - temperature (float, default 0.2)
        - max_tokens (int | None)
        - tools (list[{"type": ..., "config": ...}], default [])
        - skills (list[str], default []) — folded into the system prompt
        - interaction_rules (list[str], default []) — folded into the prompt
        - handoff_targets (list[str], default [])
        - response_format (dict, optional) — passed straight through to
          OpenAI. Use ``{"type": "json_object"}`` to force valid JSON.
        - guardrails (dict, optional)
    """
    settings = get_settings()

    name = node_data["name"]
    system_prompt = _compose_system_prompt(node_data)
    model_name = node_data.get("model") or settings.default_openai_model
    temperature = float(node_data.get("temperature", 0.2))
    max_tokens = node_data.get("max_tokens")
    response_format = node_data.get("response_format")

    llm_kwargs: dict[str, Any] = {
        "model": model_name,
        "temperature": temperature,
        "streaming": True,
    }
    if max_tokens is not None:
        llm_kwargs["max_tokens"] = int(max_tokens)
    if settings.openai_api_key:
        llm_kwargs["api_key"] = settings.openai_api_key
    if response_format:
        # Forces strict structured output (e.g. {"type": "json_object"} or
        # {"type": "json_schema", "json_schema": {...}}). When set together
        # with no tools, OpenAI guarantees parseable JSON output.
        llm_kwargs["model_kwargs"] = {"response_format": response_format}

    llm = ChatOpenAI(**llm_kwargs)

    tools = resolve_tools(
        node_data.get("tools", []),
        handoff_targets=node_data.get("handoff_targets", []),
    )

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt or None,
        name=name,
    )
    return agent
