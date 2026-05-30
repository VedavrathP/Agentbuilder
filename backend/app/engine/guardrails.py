"""Workflow guardrail extraction and enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class GuardrailViolation(Exception):
    """Raised when a run exceeds configured limits."""


@dataclass
class WorkflowGuardrails:
    """Aggregated limits for a workflow execution."""

    max_iterations: int | None = None
    max_cost_usd: float | None = None
    max_node_visits: dict[str, int] = field(default_factory=dict)
    forbidden_topics: list[str] = field(default_factory=list)

    node_visits: dict[str, int] = field(default_factory=dict)
    total_iterations: int = 0

    def record_node_visit(self, node_id: str) -> None:
        self.total_iterations += 1
        self.node_visits[node_id] = self.node_visits.get(node_id, 0) + 1
        cap = self.max_node_visits.get(node_id)
        if cap is not None and self.node_visits[node_id] > cap:
            raise GuardrailViolation(
                f"Node '{node_id}' exceeded max visits ({cap}). "
                "Increase loop_max_iterations on the node or edge, or fix the workflow loop."
            )
        if self.max_iterations is not None and self.total_iterations > self.max_iterations:
            raise GuardrailViolation(
                f"Workflow exceeded max_iterations ({self.max_iterations})."
            )

    def check_cost(self, cost_usd: float) -> None:
        if self.max_cost_usd is not None and cost_usd > self.max_cost_usd:
            raise GuardrailViolation(
                f"Run cost ${cost_usd:.6f} exceeded max_cost_usd (${self.max_cost_usd:.6f})."
            )

    def check_input(self, text: str) -> None:
        lower = text.lower()
        for topic in self.forbidden_topics:
            if topic.lower() in lower:
                raise GuardrailViolation(
                    f"Input matches forbidden topic '{topic}' (interaction rule)."
                )


def _merge_guardrail_dict(target: WorkflowGuardrails, g: dict[str, Any]) -> None:
    if not g:
        return
    if g.get("max_iterations") is not None:
        val = int(g["max_iterations"])
        if target.max_iterations is None:
            target.max_iterations = val
        else:
            target.max_iterations = min(target.max_iterations, val)
    if g.get("max_cost_usd") is not None:
        val = float(g["max_cost_usd"])
        if target.max_cost_usd is None:
            target.max_cost_usd = val
        else:
            target.max_cost_usd = min(target.max_cost_usd, val)
    if g.get("loop_max_iterations") is not None:
        # Applied per-node via node id in graph — handled in extract_from_workflow
        pass
    topics = g.get("forbidden_topics")
    if isinstance(topics, list):
        target.forbidden_topics.extend(str(t) for t in topics)


def extract_from_workflow(workflow_json: dict[str, Any]) -> WorkflowGuardrails:
    """Collect guardrails from workflow-level config and every agent node."""
    out = WorkflowGuardrails()
    wf_g = workflow_json.get("guardrails") or {}
    if isinstance(wf_g, dict):
        _merge_guardrail_dict(out, wf_g)

    for node in workflow_json.get("nodes", []):
        if node.get("type") != "agent":
            continue
        data = node.get("data") or {}
        g = data.get("guardrails") or {}
        if isinstance(g, dict):
            _merge_guardrail_dict(out, g)
            loop_max = g.get("loop_max_iterations")
            if loop_max is not None:
                out.max_node_visits[node["id"]] = int(loop_max)

        if data.get("loop_max_iterations") is not None:
            out.max_node_visits[node["id"]] = int(data["loop_max_iterations"])

    return out
