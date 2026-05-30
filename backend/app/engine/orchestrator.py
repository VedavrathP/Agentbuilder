"""High-level orchestration — ties together graph factory, executor, Redis bus,
and message persistence.

`start_run` is the entry point used by the FastAPI runs endpoint AND by the
Telegram bot. It runs a workflow as a background asyncio task and streams
events into Redis (so SSE subscribers see them) and into the messages table
(so the UI history endpoint and Telegram conversation history survive
restarts).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, MessageRole, Run, RunStatus, RunTrigger, Workflow
from app.db.session import session_scope
from app.engine.checkpointer import get_checkpointer
from app.engine.executor import run_graph
from app.engine.factory import build_graph
from app.engine.guardrails import extract_from_workflow
from app.engine.memory import (
    interaction_rules_for_workflow,
    memory_strategy_for_workflow,
    prepare_thread_input,
)
from app.events.bus import publish_event

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


_graph_cache: dict[tuple[str, int], Any] = {}


async def _get_or_build_graph(workflow: Workflow):
    key = (str(workflow.id), workflow.version)
    if key in _graph_cache:
        return _graph_cache[key]
    cp = await get_checkpointer()
    graph = build_graph(workflow.graph_json, checkpointer=cp)
    _graph_cache[key] = graph
    return graph


def invalidate_graph_cache(workflow_id: str) -> None:
    for key in list(_graph_cache.keys()):
        if key[0] == workflow_id:
            del _graph_cache[key]


async def _persist_user_message(
    session: AsyncSession, *, run_id: uuid.UUID, thread_id: str, content: str
) -> None:
    msg = Message(
        run_id=run_id,
        thread_id=thread_id,
        role=MessageRole.user,
        content=content,
    )
    session.add(msg)


async def _persist_assistant_message(
    session: AsyncSession,
    *,
    run_id: uuid.UUID | None,
    thread_id: str,
    node: str | None,
    content: str,
    token_usage: dict[str, Any] | None,
) -> None:
    msg = Message(
        run_id=run_id,
        thread_id=thread_id,
        source_node=node,
        role=MessageRole.assistant,
        content=content,
        token_usage=token_usage,
    )
    session.add(msg)


async def _persist_tool_message(
    session: AsyncSession,
    *,
    run_id: uuid.UUID | None,
    thread_id: str,
    node: str | None,
    name: str,
    content: str,
    tool_call_id: str | None,
) -> None:
    msg = Message(
        run_id=run_id,
        thread_id=thread_id,
        source_node=node,
        role=MessageRole.tool,
        content=content,
        tool_calls=[{"name": name, "tool_call_id": tool_call_id}],
    )
    session.add(msg)


async def execute_run(
    *,
    run_id: uuid.UUID,
    workflow_id: uuid.UUID,
    workflow_graph_json: dict[str, Any],
    workflow_version: int,
    thread_id: str,
    user_input: str,
) -> None:
    """Background task: run the workflow, publish events, persist messages."""
    cp = await get_checkpointer()
    graph = build_graph(workflow_graph_json, checkpointer=cp)

    async with session_scope() as s:
        await _persist_user_message(
            s, run_id=run_id, thread_id=thread_id, content=user_input
        )

    final_usage: dict[str, Any] | None = None
    final_status = "succeeded"
    final_error: str | None = None

    guardrails = extract_from_workflow(workflow_graph_json)
    memory_strategy = memory_strategy_for_workflow(workflow_graph_json)
    interaction_rules = interaction_rules_for_workflow(workflow_graph_json)
    seed_messages = await prepare_thread_input(
        user_input=user_input,
        thread_id=thread_id,
        memory_strategy=memory_strategy,
        interaction_rules=interaction_rules,
    )

    try:
        async for event in run_graph(
            graph,
            user_input=user_input,
            thread_id=thread_id,
            run_id=str(run_id),
            workflow_id=str(workflow_id),
            guardrails=guardrails,
            seed_messages=seed_messages,
        ):
            await publish_event(str(run_id), event)

            et = event.get("type")
            if et == "agent_message":
                async with session_scope() as s:
                    await _persist_assistant_message(
                        s,
                        run_id=run_id,
                        thread_id=thread_id,
                        node=event.get("node"),
                        content=event.get("content", ""),
                        token_usage=event.get("token_usage"),
                    )
            elif et == "tool_result":
                async with session_scope() as s:
                    await _persist_tool_message(
                        s,
                        run_id=run_id,
                        thread_id=thread_id,
                        node=event.get("node"),
                        name=event.get("name", ""),
                        content=event.get("content", ""),
                        tool_call_id=event.get("tool_call_id"),
                    )
            elif et == "usage":
                final_usage = event
            elif et == "run_end":
                final_status = event.get("status", "succeeded")
                final_error = event.get("error")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Run %s failed", run_id)
        final_status = "failed"
        final_error = str(exc)
        await publish_event(
            str(run_id),
            {"type": "run_end", "status": "failed", "error": str(exc)},
        )

    async with session_scope() as s:
        run = await s.get(Run, run_id)
        if run is not None:
            run.status = RunStatus(final_status) if final_status in RunStatus._value2member_map_ else RunStatus.succeeded
            run.error = final_error
            run.finished_at = datetime.now(UTC)
            if final_usage:
                run.total_input_tokens = int(final_usage.get("input_tokens", 0))
                run.total_output_tokens = int(final_usage.get("output_tokens", 0))
                run.total_cost_usd = float(final_usage.get("cost_usd", 0.0))


async def start_run(
    *,
    workflow: Workflow,
    user_input: str,
    trigger: RunTrigger = RunTrigger.manual,
    thread_id: str | None = None,
) -> Run:
    """Create a Run row in the DB and schedule its execution. Returns the Run."""
    thread_id = thread_id or f"run-{uuid.uuid4()}"

    async with session_scope() as s:
        run = Run(
            workflow_id=workflow.id,
            thread_id=thread_id,
            status=RunStatus.running,
            trigger=trigger,
            input_text=user_input,
        )
        s.add(run)
        await s.flush()
        run_id = run.id
        wf_graph = workflow.graph_json
        wf_version = workflow.version
        wf_id = workflow.id

    asyncio.create_task(
        execute_run(
            run_id=run_id,
            workflow_id=wf_id,
            workflow_graph_json=wf_graph,
            workflow_version=wf_version,
            thread_id=thread_id,
            user_input=user_input,
        )
    )

    async with session_scope() as s:
        return await s.get(Run, run_id)


def load_template_files() -> list[dict[str, Any]]:
    """Load all *.json templates from `backend/app/templates/`."""
    out: list[dict[str, Any]] = []
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        out.append(json.loads(path.read_text()))
    return out
