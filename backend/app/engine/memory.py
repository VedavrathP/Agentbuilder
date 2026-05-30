"""Memory strategies applied before a workflow run."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import select

from app.config import get_settings
from app.db.models import Message, MessageRole
from app.db.session import session_scope

logger = logging.getLogger(__name__)

SUMMARY_THRESHOLD = 6


async def prepare_thread_input(
    *,
    user_input: str,
    thread_id: str,
    memory_strategy: str,
    interaction_rules: list[str] | None = None,
) -> list[Any]:
    """Return the LangChain messages list to seed the graph run."""
    messages: list[Any] = []

    rules = interaction_rules or []
    if rules:
        rules_text = "\n".join(f"- {r}" for r in rules)
        messages.append(
            SystemMessage(
                content=(
                    "Follow these interaction rules for this conversation:\n"
                    f"{rules_text}"
                )
            )
        )

    if memory_strategy == "none":
        messages.append(HumanMessage(content=user_input))
        return messages

    if memory_strategy == "summary":
        prior = await _fetch_prior_messages(thread_id)
        if len(prior) >= SUMMARY_THRESHOLD:
            summary = await _summarize_messages(prior)
            if summary:
                messages.append(
                    SystemMessage(
                        content=(
                            "Conversation summary from earlier in this thread "
                            f"(for context only):\n{summary}"
                        )
                    )
                )
        messages.append(HumanMessage(content=user_input))
        return messages

    messages.append(HumanMessage(content=user_input))
    return messages


async def _fetch_prior_messages(thread_id: str) -> list[Message]:
    async with session_scope() as s:
        result = await s.execute(
            select(Message)
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())


async def _summarize_messages(msgs: list[Message]) -> str:
    lines: list[str] = []
    for m in msgs[-40:]:
        role = m.role.value if hasattr(m.role, "value") else str(m.role)
        lines.append(f"{role}: {m.content[:500]}")
    transcript = "\n".join(lines)
    settings = get_settings()
    if not settings.openai_api_key:
        return transcript[:2000]

    llm = ChatOpenAI(
        model=settings.default_openai_model,
        temperature=0,
        api_key=settings.openai_api_key,
    )
    try:
        resp = await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "Summarize the following conversation in 5-8 bullet points. "
                        "Preserve facts, decisions, and open questions."
                    )
                ),
                HumanMessage(content=transcript),
            ]
        )
        return str(resp.content)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to summarize thread memory")
        return transcript[:2000]


def memory_strategy_for_workflow(workflow_json: dict[str, Any]) -> str:
    """Pick memory strategy from entry agent node or workflow default."""
    entry = workflow_json.get("entry")
    for node in workflow_json.get("nodes", []):
        if node.get("id") == entry and node.get("type") == "agent":
            return (node.get("data") or {}).get("memory_strategy", "thread")
    return workflow_json.get("memory_strategy", "thread")


def interaction_rules_for_workflow(workflow_json: dict[str, Any]) -> list[str]:
    entry = workflow_json.get("entry")
    rules: list[str] = []
    wf_rules = workflow_json.get("interaction_rules")
    if isinstance(wf_rules, list):
        rules.extend(str(r) for r in wf_rules)
    for node in workflow_json.get("nodes", []):
        if node.get("id") == entry and node.get("type") == "agent":
            node_rules = (node.get("data") or {}).get("interaction_rules")
            if isinstance(node_rules, list):
                rules.extend(str(r) for r in node_rules)
    return rules
