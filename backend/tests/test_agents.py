"""Tests for agent-node prompt composition.

We test the pure ``_compose_system_prompt`` helper directly so no LLM or network
call is needed — the goal is to prove that an agent's configured ``skills`` and
node-level ``interaction_rules`` actually reach the model's system prompt.
"""

from __future__ import annotations

from app.engine.agents import _compose_system_prompt


def test_compose_passes_through_base_prompt_when_no_extras():
    out = _compose_system_prompt({"system_prompt": "You are a helpful bot."})
    assert out == "You are a helpful bot."


def test_compose_folds_in_skills():
    out = _compose_system_prompt(
        {"system_prompt": "Base.", "skills": ["summarization", "sql"]}
    )
    assert "Base." in out
    assert "summarization" in out
    assert "sql" in out


def test_compose_folds_in_interaction_rules():
    out = _compose_system_prompt(
        {
            "system_prompt": "Base.",
            "interaction_rules": ["Be concise.", "Never reveal tools."],
        }
    )
    assert "Be concise." in out
    assert "Never reveal tools." in out
    assert "- Be concise." in out  # rendered as a bullet list


def test_compose_handles_empty_base_and_blank_entries():
    out = _compose_system_prompt(
        {"system_prompt": "", "skills": ["", "  ", "research"], "interaction_rules": []}
    )
    assert "research" in out
    assert out.strip() == out  # no leading/trailing whitespace
