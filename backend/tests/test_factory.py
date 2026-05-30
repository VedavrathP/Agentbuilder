"""Tests for the workflow → LangGraph factory.

We avoid real LLM calls by replacing `make_agent_node` with a simple identity
function via monkeypatch — the goal here is to assert the graph *shape* is
correctly built from JSON (entry, edges, conditional routing), not the agent
internals.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.engine import factory
from app.engine.factory import build_graph

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"


@pytest.fixture(autouse=True)
def stub_agent(monkeypatch):
    """Replace agent construction with a no-op callable for graph-shape tests."""

    def _fake(node_data):
        def _node(state):
            return {"messages": state.get("messages", [])}

        return _node

    monkeypatch.setattr(factory, "make_agent_node", _fake)


def _load(name: str) -> dict:
    return json.loads((TEMPLATES / name).read_text())["graph"]


def test_research_and_write_graph_shape():
    g = build_graph(_load("research_and_write.json"))
    nodes = set(g.nodes.keys())
    assert {"researcher", "writer"}.issubset(nodes)


def test_support_triage_graph_excludes_condition_node():
    g = build_graph(_load("support_triage.json"))
    nodes = set(g.nodes.keys())
    assert {"classifier", "billing_agent", "tech_agent"}.issubset(nodes)
    # The condition node must NOT be in the compiled graph — it becomes routing
    assert "route" not in nodes


def test_support_triage_uses_json_router_and_strict_response_format():
    """Pin the deterministic-routing contract: the classifier must emit
    structured JSON and the router must consume the `intent` field, so the
    template cannot silently regress back to fuzzy keyword routing."""
    raw = json.loads((TEMPLATES / "support_triage.json").read_text())
    graph = raw["graph"]

    classifier = next(n for n in graph["nodes"] if n["id"] == "classifier")
    assert classifier["data"]["response_format"] == {"type": "json_object"}
    assert classifier["data"]["temperature"] == 0.0

    route = next(n for n in graph["nodes"] if n["id"] == "route")
    assert route["data"]["router"] == "json_field"
    assert route["data"]["spec"]["field"] == "intent"
    assert route["data"]["spec"]["mapping"] == {
        "billing": "billing_agent",
        "technical": "tech_agent",
    }

    for sid in ("billing_agent", "tech_agent"):
        specialist = next(n for n in graph["nodes"] if n["id"] == sid)
        assert not specialist["data"].get("handoff_targets")


def test_factory_rejects_missing_entry_and_no_agents():
    bogus = {"nodes": [], "edges": []}
    with pytest.raises(ValueError):
        build_graph(bogus)


def test_draft_and_critic_loops_back_through_router():
    """The critic loop template must wire writer → critic → route, with the
    route able to send control back to writer (loop) or onward to finalizer.
    """
    raw = json.loads((TEMPLATES / "draft_and_critic.json").read_text())
    graph_def = raw["graph"]

    g = build_graph(graph_def)
    nodes = set(g.nodes.keys())
    assert {"writer", "critic", "finalizer"}.issubset(nodes)
    assert "route" not in nodes

    route = next(n for n in graph_def["nodes"] if n["id"] == "route")
    assert route["data"]["router"] == "json_field"
    assert route["data"]["spec"]["mapping"]["true"] == "finalizer"
    assert route["data"]["spec"]["mapping"]["false"] == "writer"

    writer = next(n for n in graph_def["nodes"] if n["id"] == "writer")
    critic = next(n for n in graph_def["nodes"] if n["id"] == "critic")
    assert writer["data"].get("loop_max_iterations")
    assert critic["data"].get("loop_max_iterations")

    assert raw["guardrails"]["max_iterations"] > 0
    assert raw["guardrails"]["max_cost_usd"] > 0
