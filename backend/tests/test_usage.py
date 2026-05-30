"""Tests for token/cost aggregation."""

from __future__ import annotations

from app.engine.usage import aggregate_usage, estimate_cost


def test_estimate_cost_known_model():
    cost = estimate_cost("gpt-4o-mini", input_tokens=1_000_000, output_tokens=1_000_000)
    assert round(cost, 4) == round(0.15 + 0.60, 4)


def test_estimate_cost_unknown_model_is_zero():
    assert estimate_cost("totally-unknown-model", 1000, 1000) == 0.0


def test_aggregate_usage_sums_across_models():
    raw = {
        "gpt-4o-mini": {"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500},
        "gpt-4o": {"input_tokens": 200, "output_tokens": 100, "total_tokens": 300},
    }
    agg = aggregate_usage(raw)
    assert agg["input_tokens"] == 1200
    assert agg["output_tokens"] == 600
    assert agg["total_tokens"] == 1800
    assert agg["cost_usd"] > 0
    assert set(agg["per_model"].keys()) == {"gpt-4o-mini", "gpt-4o"}
