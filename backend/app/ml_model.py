"""ML model facade for pipeline inference.

This module centralizes model loading and probability prediction so the
pipeline does not depend on lower-level ensemble implementation details.
"""

from __future__ import annotations

from .predict import load_all_models, predict_fraud


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
      "individual_scores": dict,
      "models_used": list[str],
      "weights": dict
    }
    """
    _ensure_models_loaded()
    raw = predict_fraud(features)
    return {
        "ml_score": float(raw.get("ensemble_score", 0.0) or 0.0),
        "individual_scores": dict(raw.get("individual_scores", {})),
        "models_used": list(raw.get("models_used", [])),
        "weights": dict(raw.get("weights", {})),
    }
