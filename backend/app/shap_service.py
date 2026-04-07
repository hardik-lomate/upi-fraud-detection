"""SHAP inference service for per-transaction explainability."""

from __future__ import annotations

from pathlib import Path
import logging
from typing import Any

import joblib
import numpy as np

from .feature_columns import get_feature_columns

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
SHAP_EXPLAINER_PATH = BASE_DIR.parent.parent / "ml" / "models" / "shap_explainer.pkl"

_shap_explainer: Any = None

_FEATURE_HUMAN_LABELS = {
    "amount_deviation": "Amount is unusually high for this user",
    "sender_txn_count_1min": "Multiple payments in under 1 minute",
    "sender_velocity_5min": "Burst of payments in 5 minutes",
    "is_new_device": "Payment from an unrecognized device",
    "is_impossible_travel": "Location physically impossible given last transaction",
    "is_new_receiver": "First payment ever to this UPI ID",
    "receiver_fraud_flag_count": "Receiver previously flagged for fraud",
    "vpa_suffix_risk_score": "Receiver UPI ID looks suspicious or unverified",
    "is_night": "Transaction at unusual late-night hour",
    "geo_distance_km": "Transaction originated from unexpected location",
    "amount_to_avg_ratio": "Amount is much larger than usual for this user",
    "upi_age_days": "Receiver UPI ID is brand new or unknown",
    "cross_bank_flag": "Cross-bank transfer to unknown account",
    "receiver_new_sender_ratio_24h": "Receiver is getting payments from many new users today",
    "sender_unique_receivers_24h": "Paying many different people today",
    "txn_amount_rank_7d": "Largest payment in the last 7 days",
}


def load_shap_explainer() -> Any:
    """Load SHAP explainer once and cache in-memory."""
    global _shap_explainer
    if _shap_explainer is not None:
        return _shap_explainer

    if not SHAP_EXPLAINER_PATH.exists():
        logger.info("SHAP explainer file not found at %s", SHAP_EXPLAINER_PATH)
        return None

    try:
        _shap_explainer = joblib.load(SHAP_EXPLAINER_PATH)
        logger.info("SHAP explainer loaded from %s", SHAP_EXPLAINER_PATH)
    except Exception as exc:
        logger.warning("Failed to load SHAP explainer: %s", exc)
        _shap_explainer = None
    return _shap_explainer


def _to_ordered_vector(features: dict, feature_columns: list[str]) -> np.ndarray:
    ordered = [float(features.get(col, 0.0) or 0.0) for col in feature_columns]
    return np.array(ordered, dtype=float).reshape(1, -1)


def _heuristic_shap_rows(features: dict, feature_columns: list[str]) -> list[dict]:
    rows = []
    for col in feature_columns:
        value = float(features.get(col, 0.0) or 0.0)
        shap_value = abs(value) * 0.001
        direction = "risk_increase" if value >= 0 else "risk_decrease"
        rows.append(
            {
                "feature": col,
                "shap_value": float(shap_value),
                "direction": direction,
                "value": value,
                "human_label": _FEATURE_HUMAN_LABELS.get(col, col.replace("_", " ").title()),
            }
        )
    rows.sort(key=lambda x: abs(float(x["shap_value"])), reverse=True)
    return rows


def get_shap_values(features: dict, top_n: int = 8) -> dict:
    """
    Return structured SHAP values for a single transaction.

    Output format:
    {
      "top_features": [
        {
          "feature": str,
          "shap_value": float,
          "direction": "risk_increase"|"risk_decrease",
          "human_label": str
        }
      ],
      "base_value": float,
      "predicted_value": float
    }
    """
    cols = get_feature_columns()
    explainer = load_shap_explainer()

    if explainer is None:
        rows = _heuristic_shap_rows(features, cols)
        return {
            "top_features": rows[:top_n],
            "base_value": 0.0,
            "predicted_value": float(sum(r["shap_value"] for r in rows[:top_n])),
        }

    try:
        x = _to_ordered_vector(features, cols)
        shap_values = explainer.shap_values(x)
        base_value = getattr(explainer, "expected_value", 0.0)

        if isinstance(shap_values, list):
            sv = np.array(shap_values[-1][0], dtype=float)
            base = float(base_value[-1] if isinstance(base_value, (list, np.ndarray)) else base_value)
        else:
            sv = np.array(shap_values[0], dtype=float)
            base = float(base_value[0] if isinstance(base_value, (list, np.ndarray)) else base_value)

        rows = []
        for idx, col in enumerate(cols):
            shap_val = float(sv[idx]) if idx < len(sv) else 0.0
            direction = "risk_increase" if shap_val >= 0 else "risk_decrease"
            rows.append(
                {
                    "feature": col,
                    "shap_value": shap_val,
                    "direction": direction,
                    "value": float(x[0][idx]),
                    "human_label": _FEATURE_HUMAN_LABELS.get(col, col.replace("_", " ").title()),
                }
            )

        rows.sort(key=lambda r: abs(float(r["shap_value"])), reverse=True)
        predicted = float(base + float(np.sum(sv)))
        return {
            "top_features": rows[:top_n],
            "base_value": base,
            "predicted_value": predicted,
        }
    except Exception as exc:
        logger.warning("SHAP inference failed, using heuristic fallback: %s", exc)
        rows = _heuristic_shap_rows(features, cols)
        return {
            "top_features": rows[:top_n],
            "base_value": 0.0,
            "predicted_value": float(sum(r["shap_value"] for r in rows[:top_n])),
        }


def get_top_risk_reasons(features: dict, n: int = 5) -> list[str]:
    """Return plain-English top positive risk reasons."""
    payload = get_shap_values(features, top_n=max(8, n))
    reasons = []
    for row in payload.get("top_features", []):
        if row.get("direction") != "risk_increase":
            continue
        label = str(row.get("human_label") or row.get("feature") or "Risk signal")
        if label and label not in reasons:
            reasons.append(label)
        if len(reasons) >= n:
            break
    return reasons
