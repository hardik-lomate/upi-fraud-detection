"""
Ensemble Prediction — Loads models and enforces feature ordering from contract.
"""

import joblib
import numpy as np
from pathlib import Path
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import FEATURE_COLUMNS, ENSEMBLE_DEFAULTS

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR.parent.parent / "ml" / "models"

_models = {}
_ensemble_weights = None


def _load_if_exists(name: str, filename: str):
    path = MODELS_DIR / filename
    if path.exists():
        _models[name] = joblib.load(path)
        print(f"  ✅ {name} loaded")
    else:
        print(f"  ⚠️  {name} not found — skipping")


def load_all_models():
    global _ensemble_weights
    print("Loading models...")
    _load_if_exists("xgboost", "xgboost_model.pkl")
    _load_if_exists("lightgbm", "lightgbm_model.pkl")
    _load_if_exists("isolation_forest", "isolation_forest_model.pkl")

    ew_path = MODELS_DIR / "ensemble_weights.pkl"
    if ew_path.exists():
        _ensemble_weights = joblib.load(ew_path)
    else:
        _ensemble_weights = ENSEMBLE_DEFAULTS
    print(f"  Weights: {_ensemble_weights}")
    print(f"  Feature order: {FEATURE_COLUMNS}")
    print(f"Models ready: {list(_models.keys())}")


def predict_fraud(features_dict: dict) -> dict:
    if not _models:
        load_all_models()

    # Enforce column order from CONTRACT
    ordered = [features_dict[col] for col in FEATURE_COLUMNS]
    X = np.array(ordered).reshape(1, -1)

    scores = {}
    weighted_sum = 0.0
    total_weight = 0.0

    if "xgboost" in _models:
        s = float(_models["xgboost"].predict_proba(X)[0][1])
        scores["xgboost"] = round(s, 4)
        w = _ensemble_weights.get("xgboost", 0.45)
        weighted_sum += w * s
        total_weight += w

    if "lightgbm" in _models:
        s = float(_models["lightgbm"].predict_proba(X)[0][1])
        scores["lightgbm"] = round(s, 4)
        w = _ensemble_weights.get("lightgbm", 0.35)
        weighted_sum += w * s
        total_weight += w

    if "isolation_forest" in _models:
        raw = float(_models["isolation_forest"].decision_function(X)[0])
        s = 1.0 / (1.0 + np.exp(raw))
        scores["isolation_forest"] = round(float(s), 4)
        w = _ensemble_weights.get("isolation_forest", 0.20)
        weighted_sum += w * s
        total_weight += w

    ensemble_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    return {
        "ensemble_score": round(ensemble_score, 4),
        "individual_scores": scores,
        "models_used": list(scores.keys()),
        "weights": {k: v for k, v in _ensemble_weights.items() if k in scores},
    }
