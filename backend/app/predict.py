"""Ensemble Prediction.

Loads models + calibration and enforces training-time feature ordering.
"""

import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import ENSEMBLE_DEFAULTS, validate_feature_schema

from .feature_columns import get_feature_columns

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR.parent.parent / "ml" / "models"

_models = {}
_ensemble_weights = None
_iso_calibration = None
_thresholds = None
_metadata = None


def _load_if_exists(name: str, filename: str):
    path = MODELS_DIR / filename
    if path.exists():
        _models[name] = joblib.load(path)
        print(f"  [OK] {name} loaded")
    else:
        print(f"  [WARN] {name} not found -- skipping")


def load_all_models():
    global _ensemble_weights, _iso_calibration, _thresholds, _metadata
    print("Loading models...")
    _load_if_exists("xgboost", "xgboost_model.pkl")
    _load_if_exists("lightgbm", "lightgbm_model.pkl")
    _load_if_exists("isolation_forest", "isolation_forest_model.pkl")

    ew_path = MODELS_DIR / "ensemble_weights.pkl"
    _ensemble_weights = joblib.load(ew_path) if ew_path.exists() else ENSEMBLE_DEFAULTS

    calib_path = MODELS_DIR / "iso_calibration.pkl"
    if calib_path.exists():
        _iso_calibration = joblib.load(calib_path)
        print(f"  [OK] IsoForest calibration: min={_iso_calibration['min']:.4f}, max={_iso_calibration['max']:.4f}")
    else:
        _iso_calibration = None
        print("  [WARN] No IsoForest calibration -- using sigmoid fallback")

    thresh_path = MODELS_DIR / "thresholds.json"
    if thresh_path.exists():
        with open(thresh_path) as f:
            _thresholds = json.load(f)
        print(f"  [OK] Thresholds: FLAG={_thresholds['threshold_flag']}, BLOCK={_thresholds['threshold_block']}")
    else:
        _thresholds = None

    meta_path = MODELS_DIR / "model_metadata.json"
    if meta_path.exists():
        with open(meta_path) as f:
            _metadata = json.load(f)

    print(f"  Feature order: {get_feature_columns()}")
    print(f"Models ready: {list(_models.keys())}")


def get_metadata() -> dict:
    return _metadata or {}


def get_thresholds() -> dict:
    return _thresholds or {}


def predict_fraud(features_dict: dict) -> dict:
    if not _models:
        load_all_models()
    if not _models:
        raise RuntimeError(
            "No trained model artifacts were loaded. Run `python setup_and_train.py` to generate models."
        )

    contract = validate_feature_schema(features_dict or {}, allow_extra=True)
    if not contract.get("is_valid", False):
        raise ValueError(f"Prediction feature contract violation: missing {contract.get('missing', [])}")

    feature_columns = get_feature_columns()
    missing = [c for c in feature_columns if c not in features_dict]
    if missing:
        raise ValueError(f"Missing required features for prediction: {missing}")

    ordered = [features_dict[c] for c in feature_columns]
    x = np.array(ordered).reshape(1, -1)

    scores = {}
    anomaly_score = None
    weighted_sum = 0.0
    total_weight = 0.0

    if "xgboost" in _models:
        s = float(_models["xgboost"].predict_proba(x)[0][1])
        scores["xgboost"] = round(s, 4)
        w = _ensemble_weights.get("xgboost", 0.45)
        weighted_sum += w * s
        total_weight += w

    if "lightgbm" in _models:
        s = float(_models["lightgbm"].predict_proba(x)[0][1])
        scores["lightgbm"] = round(s, 4)
        w = _ensemble_weights.get("lightgbm", 0.35)
        weighted_sum += w * s
        total_weight += w

    if "isolation_forest" in _models:
        raw = float(_models["isolation_forest"].decision_function(x)[0])
        if _iso_calibration:
            s = 1 - (raw - _iso_calibration["min"]) / (_iso_calibration["max"] - _iso_calibration["min"])
            s = max(0.0, min(1.0, s))
        else:
            s = 1.0 / (1.0 + np.exp(raw))
        scores["isolation_forest"] = round(float(s), 4)
        anomaly_score = float(s)
        w = _ensemble_weights.get("isolation_forest", 0.15)
        weighted_sum += w * s
        total_weight += w

    ensemble_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    return {
        "ensemble_score": round(ensemble_score, 4),
        "anomaly_score": round(float(anomaly_score), 4) if anomaly_score is not None else None,
        "individual_scores": scores,
        "models_used": list(scores.keys()),
        "weights": {k: v for k, v in _ensemble_weights.items() if k in scores},
    }
