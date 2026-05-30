"""Unit tests for conditional-edge router functions."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from app.engine.routers import json_field_router, keyword_router, regex_router


def _state(ai_text: str) -> dict:
    return {"messages": [HumanMessage(content="hi"), AIMessage(content=ai_text)]}


def test_keyword_router_first_branch_match():
    router = keyword_router(
        {
            "branches": [
                {"keywords": ["billing", "invoice"], "target": "billing_agent"},
                {"keywords": ["bug", "error"], "target": "tech_agent"},
            ],
            "default": "fallback",
        }
    )
    assert router(_state("This is about billing")) == "billing_agent"
    assert router(_state("Got an ERROR on login")) == "tech_agent"
    assert router(_state("Just a normal question")) == "fallback"


def test_regex_router():
    router = regex_router(
        {
            "branches": [{"pattern": r"\bcat\d+", "target": "matched"}],
            "default": "other",
        }
    )
    assert router(_state("Issue is cat42 here")) == "matched"
    assert router(_state("nothing here")) == "other"


def test_json_field_router_with_fenced_json():
    router = json_field_router(
        {
            "field": "category",
            "mapping": {"billing": "billing_agent", "tech": "tech_agent"},
            "default": "fallback",
        }
    )
    fenced = '```json\n{"category": "billing", "confidence": 0.9}\n```'
    assert router(_state(fenced)) == "billing_agent"
    assert router(_state('{"category": "tech"}')) == "tech_agent"
    assert router(_state("not json")) == "fallback"


def test_json_field_router_matches_support_triage_template_shape():
    """The classifier in templates/support_triage.json emits `intent`.

    Verify the router resolves both supported intents and falls back when
    the LLM emits an unknown value.
    """
    router = json_field_router(
        {
            "field": "intent",
            "mapping": {"billing": "billing_agent", "technical": "tech_agent"},
            "default": "tech_agent",
        }
    )
    billing_payload = (
        '{"intent": "billing", "confidence": 0.95, '
        '"reason": "User reports a double charge and requests a refund."}'
    )
    technical_payload = (
        '{"intent": "technical", "confidence": 0.9, '
        '"reason": "Login crash on Android indicates a technical issue."}'
    )
    assert router(_state(billing_payload)) == "billing_agent"
    assert router(_state(technical_payload)) == "tech_agent"
    # Unknown intent → default branch
    assert router(_state('{"intent": "sales"}')) == "tech_agent"


def test_json_field_router_extracts_object_embedded_in_prose():
    """Some models prefix JSON with chatter despite response_format. The
    router must still find and parse the first JSON object in the text."""
    router = json_field_router(
        {
            "field": "intent",
            "mapping": {"billing": "billing_agent"},
            "default": "tech_agent",
        }
    )
    noisy = 'Sure, here you go: {"intent": "billing"}\nLet me know if you need more.'
    assert router(_state(noisy)) == "billing_agent"
