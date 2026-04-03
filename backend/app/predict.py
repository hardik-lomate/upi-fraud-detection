"""
Ensemble Prediction — Combines XGBoost + LightGBM + Isolation Forest.
Loads models lazily and enforces feature column ordering.
"""

import joblib
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR.parent.parent / "ml" / "models"

_models = {}
_feature_columns = None
_ensemble_weights = None


def _load_if_exists(name: str, filename: str):
    """Load a model file if it exists, skip otherwise."""
    path = MODELS_DIR / filename
    if path.exists():
        _models[name] = joblib.load(path)
        print(f"  ✅ {name} loaded from {path}")
    else:
        print(f"  ⚠️ {name} not found at {path} — skipping")


def load_all_models():
    """Load all models on startup."""
    global _feature_columns, _ensemble_weights

    print("Loading models...")
    _load_if_exists("xgboost", "xgboost_model.pkl")
    _load_if_exists("lightgbm", "lightgbm_model.pkl")
    _load_if_exists("isolation_forest", "isolation_forest_model.pkl")

    # Feature columns
    fc_path = MODELS_DIR / "feature_columns.pkl"
    if fc_path.exists():
        _feature_columns = joblib.load(fc_path)
        print(f"  ✅ Feature columns: {_feature_columns}")
    else:
        raise FileNotFoundError(f"feature_columns.pkl not found at {fc_path}")

    # Ensemble weights
    ew_path = MODELS_DIR / "ensemble_weights.pkl"
    if ew_path.exists():
        _ensemble_weights = joblib.load(ew_path)
        print(f"  ✅ Ensemble weights: {_ensemble_weights}")
    else:
        _ensemble_weights = {"xgboost": 1.0}
        print("  ⚠️ No ensemble weights found — using XGBoost only")

    print(f"Models ready: {list(_models.keys())}")


def get_feature_columns() -> list:
    if _feature_columns is None:
        load_all_models()
    return _feature_columns


def predict_fraud(features_dict: dict) -> dict:
    """
    Run ensemble prediction.
    Returns dict with individual and combined scores.
    """
    if not _models:
        load_all_models()

    col_order = get_feature_columns()
    ordered_features = [features_dict[col] for col in col_order]
    X = np.array(ordered_features).reshape(1, -1)

    scores = {}
    weighted_sum = 0.0
    total_weight = 0.0

    # XGBoost
    if "xgboost" in _models:
        xgb_score = float(_models["xgboost"].predict_proba(X)[0][1])
        scores["xgboost"] = round(xgb_score, 4)
        w = _ensemble_weights.get("xgboost", 0.45)
        weighted_sum += w * xgb_score
        total_weight += w

    # LightGBM
    if "lightgbm" in _models:
        lgbm_score = float(_models["lightgbm"].predict_proba(X)[0][1])
        scores["lightgbm"] = round(lgbm_score, 4)
        w = _ensemble_weights.get("lightgbm", 0.35)
        weighted_sum += w * lgbm_score
        total_weight += w

    # Isolation Forest
    if "isolation_forest" in _models:
        iso_raw = float(_models["isolation_forest"].decision_function(X)[0])
        # Convert to 0-1 (lower decision_function = more anomalous)
        # Use sigmoid-like transformation
        iso_score = 1.0 / (1.0 + np.exp(iso_raw))
        scores["isolation_forest"] = round(float(iso_score), 4)
        w = _ensemble_weights.get("isolation_forest", 0.20)
        weighted_sum += w * iso_score
        total_weight += w

    # Weighted ensemble score
    ensemble_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    return {
        "ensemble_score": round(ensemble_score, 4),
        "individual_scores": scores,
        "models_used": list(scores.keys()),
        "weights": {k: v for k, v in _ensemble_weights.items() if k in scores},
    }
