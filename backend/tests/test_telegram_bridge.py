"""Telegram bridge — verifies the message handler maps chats to runs/threads,
streams events through the engine, and edits the reply with accumulated content.

We mock python-telegram-bot's `Update` / `Message` objects, and substitute a
fake graph so the test runs without OpenAI.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy as sa
from langchain_core.messages import AIMessage

from app.channels.telegram_bot import make_message_handler
from app.db.models import Message, Run, Workflow
from app.db.session import get_sessionmaker, reset_engine
from app.engine import checkpointer as checkpointer_module
from app.engine import factory as factory_module


SUPPORT_TRIAGE = Path(__file__).resolve().parent.parent / "app" / "templates" / "support_triage.json"


async def _truncate() -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        await s.execute(
            sa.text(
                "TRUNCATE messages, runs, telegram_links, workflows, agents RESTART IDENTITY CASCADE"
            )
        )
        await s.commit()


def _make_fake_graph(reply_text: str):
    """Build a tiny LangGraph that emits `reply_text` from a single agent node."""
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langgraph.graph import END, START, MessagesState, StateGraph

    model = GenericFakeChatModel(messages=iter([AIMessage(content=reply_text)]))

    async def agent_node(state):
        out = await model.ainvoke(state["messages"])
        return {"messages": [out]}

    b = StateGraph(MessagesState)
    b.add_node("classifier", agent_node)
    b.add_edge(START, "classifier")
    b.add_edge("classifier", END)
    return b.compile()


@pytest.mark.asyncio
async def test_telegram_handler_persists_user_and_assistant_messages(monkeypatch):
    await reset_engine()
    await _truncate()

    # Insert a workflow row to satisfy the FK
    sm = get_sessionmaker()
    async with sm() as s:
        wf = Workflow(
            name="Test WF",
            description="",
            graph_json=json.loads(SUPPORT_TRIAGE.read_text())["graph"],
        )
        s.add(wf)
        await s.commit()
        await s.refresh(wf)
        workflow_id = wf.id

    # Stub the checkpointer + factory so no LLM / postgres-checkpoint roundtrip happens
    async def _fake_cp():
        return None

    monkeypatch.setattr(checkpointer_module, "get_checkpointer", _fake_cp)

    def _fake_build_graph(graph_json, checkpointer=None):
        return _make_fake_graph("This looks like a billing issue.")

    monkeypatch.setattr(factory_module, "build_graph", _fake_build_graph)
    # Also patch the import site used inside telegram_bot
    monkeypatch.setattr("app.channels.telegram_bot.build_graph", _fake_build_graph)
    monkeypatch.setattr("app.channels.telegram_bot.get_checkpointer", _fake_cp)

    # Avoid trying to publish to a real Redis
    async def _noop_publish(*args, **kwargs):
        return None

    monkeypatch.setattr("app.channels.telegram_bot.publish_event", _noop_publish)

    handler = make_message_handler(workflow_id)

    sent_message = SimpleNamespace(edit_text=AsyncMock())
    incoming_message = MagicMock()
    incoming_message.text = "My invoice is wrong"
    incoming_message.reply_text = AsyncMock(return_value=sent_message)

    update = SimpleNamespace(
        message=incoming_message,
        effective_chat=SimpleNamespace(id=987654321),
    )

    await handler(update, None)

    # Verify one user + at least one assistant message landed in the DB
    async with sm() as s:
        result = await s.execute(sa.select(Message).order_by(Message.created_at.asc()))
        msgs = result.scalars().all()
    roles = [m.role.value for m in msgs]
    assert "user" in roles
    assert "assistant" in roles
    user_msg = next(m for m in msgs if m.role.value == "user")
    assert user_msg.content == "My invoice is wrong"
    assert user_msg.thread_id.startswith("telegram:")

    # And the run record exists
    async with sm() as s:
        result = await s.execute(sa.select(Run))
        runs = result.scalars().all()
    assert len(runs) == 1
    assert runs[0].trigger.value == "telegram"
    assert runs[0].status.value == "succeeded"

    # And the bot tried to edit its reply at least once
    assert sent_message.edit_text.await_count >= 1

    await reset_engine()
