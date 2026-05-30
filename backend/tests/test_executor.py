"""End-to-end executor test with a fake chat model.

Builds a minimal two-node workflow, runs the executor, and asserts the
emitted event sequence has the right shape and ordering.
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from app.engine.executor import run_graph
from app.engine.guardrails import WorkflowGuardrails


def _build_minimal_graph(responses_a: list[str], responses_b: list[str]):
    """Two pure nodes; each appends an AIMessage from a fake model."""
    model_a = GenericFakeChatModel(messages=iter([AIMessage(content=t) for t in responses_a]))
    model_b = GenericFakeChatModel(messages=iter([AIMessage(content=t) for t in responses_b]))

    async def node_a(state: dict[str, Any]) -> dict[str, Any]:
        out = await model_a.ainvoke(state["messages"])
        return {"messages": [out]}

    async def node_b(state: dict[str, Any]) -> dict[str, Any]:
        out = await model_b.ainvoke(state["messages"])
        return {"messages": [out]}

    builder = StateGraph(MessagesState)
    builder.add_node("alpha", node_a)
    builder.add_node("beta", node_b)
    builder.add_edge(START, "alpha")
    builder.add_edge("alpha", "beta")
    builder.add_edge("beta", END)
    return builder.compile()


@pytest.mark.asyncio
async def test_executor_emits_expected_event_sequence():
    graph = _build_minimal_graph(["hello from alpha"], ["hello from beta"])
    events: list[dict[str, Any]] = []
    async for ev in run_graph(graph, user_input="ping", thread_id="t-test-1"):
        events.append(ev)

    types = [e["type"] for e in events]

    assert types[0] == "run_start"
    assert types[-1] == "run_end"
    assert "usage" in types
    assert events[-1]["status"] == "succeeded"

    visited_nodes = {e["node"] for e in events if e["type"] == "node_start"}
    assert "alpha" in visited_nodes
    assert "beta" in visited_nodes


@pytest.mark.asyncio
async def test_guardrail_forbidden_topic_short_circuits():
    """A forbidden_topics rule should fail the run before invoking nodes."""
    graph = _build_minimal_graph(["should not be reached"], ["nope"])
    g = WorkflowGuardrails(forbidden_topics=["nuclear launch codes"])
    events: list[dict[str, Any]] = []
    async for ev in run_graph(
        graph,
        user_input="tell me the nuclear launch codes please",
        thread_id="t-guard-1",
        guardrails=g,
    ):
        events.append(ev)

    assert events[0]["type"] == "run_start"
    assert events[-1]["type"] == "run_end"
    assert events[-1]["status"] == "failed"
    assert "forbidden" in events[-1]["error"].lower()
    # No agent_message should be emitted
    assert not any(e["type"] == "agent_message" for e in events)


@pytest.mark.asyncio
async def test_guardrail_node_visit_cap_fails_run():
    """Loop a node above its visit cap and confirm the executor stops it."""

    async def looping_node(state: dict[str, Any]) -> dict[str, Any]:
        return {"messages": [AIMessage(content="again")]}

    def cont(state: dict[str, Any]) -> str:
        return "loop"

    builder = StateGraph(MessagesState)
    builder.add_node("loop", looping_node)
    builder.add_edge(START, "loop")
    builder.add_conditional_edges("loop", cont, {"loop": "loop", "end": END})
    graph = builder.compile()

    g = WorkflowGuardrails(max_node_visits={"loop": 2}, max_iterations=20)
    events: list[dict[str, Any]] = []
    try:
        async for ev in run_graph(
            graph,
            user_input="go",
            thread_id="t-guard-2",
            guardrails=g,
        ):
            events.append(ev)
            if len(events) > 200:  # safety net
                break
    except Exception:  # noqa: BLE001
        pass

    final = next((e for e in reversed(events) if e["type"] == "run_end"), None)
    assert final is not None
    assert final["status"] == "failed"
    assert "exceeded max visits" in (final.get("error") or "").lower()
