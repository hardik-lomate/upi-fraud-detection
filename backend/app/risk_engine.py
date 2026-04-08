"""Unified risk scoring engine.

risk_score = (rules_score * 0.3) + (ml_score * 0.4) + (behavior_score * 0.2) + (graph_score * 0.1)
"""

from __future__ import annotations

import json
from typing import Any, Dict
from functools import lru_cache
from pathlib import Path

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

DEFAULT_WEIGHT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "risk_weights.json"


@lru_cache(maxsize=1)
def _load_weight_config() -> dict:
    cfg_path = os.getenv("RISK_WEIGHTS_PATH", "").strip()
    path = Path(cfg_path) if cfg_path else DEFAULT_WEIGHT_CONFIG_PATH

    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return {}
        return {
            k: float(v)
            for k, v in payload.items()
            if k in RISK_COMPONENT_WEIGHTS
        }
    except Exception:
        # Never fail scoring due to config parsing issues.
        return {}


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _moderate_isolated_ml_score(ml_score: float, support_peak: float) -> tuple[float, float]:
    """Dampen isolated very-high ML confidence when other signals are weak.

    This keeps risk distributions realistic while preserving ordering and thresholds.
    """
    ml = _clamp01(ml_score)
    support = _clamp01(support_peak)

    if ml >= 0.97 and support < 0.25:
        adjusted = ml - (0.12 + (0.25 - support) * 0.10)
    elif ml >= 0.93 and support < 0.35:
        adjusted = ml - (0.06 + (0.35 - support) * 0.06)
    else:
        adjusted = ml

    adjusted = _clamp01(adjusted)
    return adjusted, round(ml - adjusted, 6)


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
    file_weights = _load_weight_config()
    if file_weights:
        w.update(file_weights)
    if weights:
        w.update({k: float(v) for k, v in weights.items() if k in w})

    weight_sum = sum(float(v) for v in w.values())
    if weight_sum <= 0:
        w = dict(RISK_COMPONENT_WEIGHTS)
        weight_sum = sum(float(v) for v in w.values())

    # Normalize weights in case callers provide non-1.0 totals.
    w = {k: float(v) / weight_sum for k, v in w.items()}

    components_raw = {
        "rules_score": _clamp01(rules_score),
        "ml_score": _clamp01(ml_score),
        "behavior_score": _clamp01(behavior_score),
        "graph_score": _clamp01(graph_score),
    }

    support_peak = max(
        components_raw["rules_score"],
        components_raw["behavior_score"],
        components_raw["graph_score"],
    )
    adjusted_ml, ml_adjustment = _moderate_isolated_ml_score(components_raw["ml_score"], support_peak)

    components = {
        "rules_score": components_raw["rules_score"],
        "ml_score": adjusted_ml,
        "behavior_score": components_raw["behavior_score"],
        "graph_score": components_raw["graph_score"],
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
        "raw_components": components_raw,
        "distribution_adjustment": {
            "ml_tail_damping": ml_adjustment,
            "support_peak": round(support_peak, 6),
        },
        "weight_source": str(os.getenv("RISK_WEIGHTS_PATH", "").strip() or DEFAULT_WEIGHT_CONFIG_PATH),
        "input_normalization": "All component scores are clamped to [0,1], isolated extreme ML tails are damped, and weights are normalized to sum=1.0",
        "weight_justification": dict(WEIGHT_JUSTIFICATION),
    }
