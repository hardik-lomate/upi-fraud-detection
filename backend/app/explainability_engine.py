"""Explainability engine adapter.

Keeps pipeline imports stable while delegating to the existing SHAP service.
"""

from __future__ import annotations

from .explainability import explain_prediction as _explain_prediction
from .explainability import format_reasons as _format_reasons


def explain_risk_factors(features: dict, feature_columns: list[str], top_n: int = 8):
    """Return raw feature-level risk explanations."""
    return _explain_prediction(features, feature_columns, top_n=max(top_n, 8))


def _label(exp: dict) -> str:
    return str(exp.get("label") or exp.get("feature") or "Risk signal").strip()


def _append_unique(target: list[str], value: str) -> None:
    text = str(value or "").strip()
    if text and text not in target:
        target.append(text)


def format_explanations(explanations):
    """Convert explanations into concise, mixed-signal human-readable reasons."""
    rows = list(explanations or [])
    baseline = [r for r in _format_reasons(rows) if r]

    ordered = sorted(rows, key=lambda x: abs(float(x.get("shap_value", 0.0) or 0.0)), reverse=True)
    increasing = [r for r in ordered if str(r.get("direction", "")).lower() == "increases_risk"]
    decreasing = [r for r in ordered if str(r.get("direction", "")).lower() != "increases_risk"]

    reasons: list[str] = []

    if baseline:
        _append_unique(reasons, baseline[0])

    if increasing:
        _append_unique(reasons, f"Primary risk signal: {_label(increasing[0])}")
    if len(increasing) > 1:
        _append_unique(reasons, f"Secondary risk signal: {_label(increasing[1])}")
    if decreasing:
        _append_unique(reasons, f"Counter-signal: {_label(decreasing[0])}")

    for reason in baseline[1:]:
        _append_unique(reasons, reason)

    # Always return 2-3 concise reasons for consistency in demo output.
    if len(reasons) < 2 and increasing:
        for exp in increasing[2:]:
            _append_unique(reasons, _label(exp))
            if len(reasons) >= 2:
                break

    return reasons[:3]


# Backward-compatible aliases expected by pipeline wiring.
explain_prediction = explain_risk_factors
format_reasons = format_explanations
