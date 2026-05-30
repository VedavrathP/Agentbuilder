"""Tests for workflow guardrail extraction and enforcement."""

from __future__ import annotations

import pytest

from app.engine.guardrails import (
    GuardrailViolation,
    WorkflowGuardrails,
    extract_from_workflow,
)


def test_extract_merges_workflow_and_agent_guardrails_with_strictest_winning():
    wf = {
        "guardrails": {"max_iterations": 20, "max_cost_usd": 1.0},
        "nodes": [
            {
                "id": "a",
                "type": "agent",
                "data": {"guardrails": {"max_cost_usd": 0.25, "loop_max_iterations": 3}},
            },
            {
                "id": "b",
                "type": "agent",
                "data": {"loop_max_iterations": 2},
            },
        ],
        "edges": [],
    }
    g = extract_from_workflow(wf)
    assert g.max_iterations == 20
    assert g.max_cost_usd == 0.25  # strictest wins
    assert g.max_node_visits == {"a": 3, "b": 2}


def test_record_node_visit_raises_on_per_node_cap():
    g = WorkflowGuardrails(max_node_visits={"writer": 2})
    g.record_node_visit("writer")
    g.record_node_visit("writer")
    with pytest.raises(GuardrailViolation):
        g.record_node_visit("writer")


def test_record_node_visit_raises_on_total_iterations():
    g = WorkflowGuardrails(max_iterations=2)
    g.record_node_visit("a")
    g.record_node_visit("b")
    with pytest.raises(GuardrailViolation):
        g.record_node_visit("c")


def test_check_cost_raises_when_exceeded():
    g = WorkflowGuardrails(max_cost_usd=0.10)
    g.check_cost(0.05)  # below threshold, no raise
    with pytest.raises(GuardrailViolation):
        g.check_cost(0.50)


def test_check_input_matches_forbidden_topics_case_insensitive():
    g = WorkflowGuardrails(forbidden_topics=["Internal Pricing"])
    g.check_input("Just say hi")  # ok
    with pytest.raises(GuardrailViolation):
        g.check_input("Tell me about your internal pricing structure")
