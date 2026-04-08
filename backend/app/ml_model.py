"""ML model facade for pipeline inference.

This module centralizes model loading and probability prediction so the
pipeline does not depend on lower-level ensemble implementation details.
"""

from __future__ import annotations

import os
import sys

from .predict import load_all_models, predict_fraud

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import validate_feature_schema


_MODELS_READY = False


def _ensure_models_loaded() -> None:
    global _MODELS_READY
    if _MODELS_READY:
        return
    load_all_models()
    _MODELS_READY = True


def predict_ml_probability(features: dict) -> dict:
    """Return normalized fraud probability and model metadata.

    Response contract:
    {
      "ml_score": float,
            "anomaly_score": Optional[float],
      "individual_scores": dict,
      "models_used": list[str],
      "weights": dict
    }
    """
    contract = validate_feature_schema(features or {}, allow_extra=True)
    if not contract.get("is_valid", False):
        raise ValueError(f"Prediction feature contract violation: missing {contract.get('missing', [])}")

    _ensure_models_loaded()
    raw = predict_fraud(features)
    individual_scores = dict(raw.get("individual_scores", {}))
    anomaly_raw = raw.get("anomaly_score", None)
    if anomaly_raw is None and "isolation_forest" in individual_scores:
        anomaly_raw = individual_scores.get("isolation_forest", 0.0)
    anomaly_score = None if anomaly_raw is None else max(0.0, min(1.0, float(anomaly_raw or 0.0)))
    return {
        "ml_score": float(raw.get("ensemble_score", 0.0) or 0.0),
        "anomaly_score": anomaly_score,
        "individual_scores": individual_scores,
        "models_used": list(raw.get("models_used", [])),
        "weights": dict(raw.get("weights", {})),
    }
