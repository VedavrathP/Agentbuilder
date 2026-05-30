"""Token-usage and rough cost estimation.

Costs are computed from `UsageMetadataCallbackHandler.usage_metadata` against a
static price table. Pricing is approximate (USD per 1M tokens) and easily
extended.
"""

from __future__ import annotations

from typing import Any

# Prices in USD per 1M tokens (input, output). Update as needed.
PRICING_USD_PER_M_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4.1": (3.00, 12.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "o1-mini": (1.10, 4.40),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated USD cost. Unknown models return 0.0."""
    base = model.split(":")[-1]  # strip provider prefix if any
    prices = PRICING_USD_PER_M_TOKENS.get(base)
    if prices is None:
        # Try a prefix match
        for k, v in PRICING_USD_PER_M_TOKENS.items():
            if base.startswith(k):
                prices = v
                break
    if prices is None:
        return 0.0
    in_price, out_price = prices
    return (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price


def aggregate_usage(usage_metadata: dict[str, Any]) -> dict[str, Any]:
    """Summarize the per-model dict from `UsageMetadataCallbackHandler`.

    Returns: {input_tokens, output_tokens, total_tokens, cost_usd, per_model: {...}}
    """
    total_in = 0
    total_out = 0
    total_cost = 0.0
    per_model: dict[str, Any] = {}
    for model, usage in (usage_metadata or {}).items():
        in_tok = int(usage.get("input_tokens", 0) or 0)
        out_tok = int(usage.get("output_tokens", 0) or 0)
        cost = estimate_cost(model, in_tok, out_tok)
        total_in += in_tok
        total_out += out_tok
        total_cost += cost
        per_model[model] = {
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "total_tokens": in_tok + out_tok,
            "cost_usd": round(cost, 6),
        }
    return {
        "input_tokens": total_in,
        "output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "cost_usd": round(total_cost, 6),
        "per_model": per_model,
    }
