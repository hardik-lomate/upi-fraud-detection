"""Unified risk scoring engine.

risk_score = (rules_score * 0.3) + (ml_score * 0.4) + (behavior_score * 0.2) + (graph_score * 0.1)
"""

from __future__ import annotations

from typing import Any, Dict

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import RISK_COMPONENT_WEIGHTS


WEIGHT_JUSTIFICATION = {
    "rules": "Hard-coded policy and compliance guardrails.",
    "ml": "Primary probabilistic signal from trained ensemble.",
    "behavior": "Behavioral drift/velocity anomaly signal.",
    "graph": "Graph-topology mule/network-risk signal.",
}


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def compute_rules_score(rule_decision: str | None, rules_triggered: list[Any]) -> float:
    if not rules_triggered:
        return 0.0

    if str(rule_decision or "").upper() == "BLOCK":
        return 1.0

    if str(rule_decision or "").upper() == "FLAG":
        return 0.65

    max_signal = 0.0
    for rule in rules_triggered:
        action = str(getattr(rule, "action", "") or "").upper()
        if action == "BLOCK":
            max_signal = max(max_signal, 1.0)
        elif action == "FLAG":
            max_signal = max(max_signal, 0.65)
        else:
            max_signal = max(max_signal, 0.4)
    return _clamp01(max_signal)


def combine_risk_scores(
    rules_score: float,
    ml_score: float,
    behavior_score: float,
    graph_score: float,
    weights: Dict[str, float] | None = None,
) -> dict:
    w = dict(RISK_COMPONENT_WEIGHTS)
    if weights:
        w.update({k: float(v) for k, v in weights.items() if k in w})

    weight_sum = sum(float(v) for v in w.values())
    if weight_sum <= 0:
        w = dict(RISK_COMPONENT_WEIGHTS)
        weight_sum = sum(float(v) for v in w.values())

    # Normalize weights in case callers provide non-1.0 totals.
    w = {k: float(v) / weight_sum for k, v in w.items()}

    components = {
        "rules_score": _clamp01(rules_score),
        "ml_score": _clamp01(ml_score),
        "behavior_score": _clamp01(behavior_score),
        "graph_score": _clamp01(graph_score),
    }

    risk_score = (
        (components["rules_score"] * w["rules"])
        + (components["ml_score"] * w["ml"])
        + (components["behavior_score"] * w["behavior"])
        + (components["graph_score"] * w["graph"])
    )

    contributions = {
        "rules": round(components["rules_score"] * w["rules"], 6),
        "ml": round(components["ml_score"] * w["ml"], 6),
        "behavior": round(components["behavior_score"] * w["behavior"], 6),
        "graph": round(components["graph_score"] * w["graph"], 6),
    }

    return {
        "risk_score": round(_clamp01(risk_score), 4),
        "components": components,
        "weights": {k: round(v, 6) for k, v in w.items()},
        "contributions": contributions,
        "input_normalization": "All component scores are clamped to [0,1]; weights are normalized to sum=1.0",
        "weight_justification": dict(WEIGHT_JUSTIFICATION),
    }
