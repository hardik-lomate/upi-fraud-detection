"""Explainability engine adapter.

Keeps pipeline imports stable while delegating to the existing SHAP service.
"""

from __future__ import annotations

from .explainability import explain_prediction as _explain_prediction
from .explainability import format_reasons as _format_reasons


def explain_risk_factors(features: dict, feature_columns: list[str], top_n: int = 8):
    """Return raw feature-level risk explanations."""
    return _explain_prediction(features, feature_columns, top_n=top_n)


def format_explanations(explanations):
    """Convert explanations into concise human-readable reasons."""
    return _format_reasons(explanations)


# Backward-compatible aliases expected by pipeline wiring.
explain_prediction = explain_risk_factors
format_reasons = format_explanations
