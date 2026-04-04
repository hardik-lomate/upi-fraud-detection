"""
SHAP Explainability Module — provides human-readable reasons for each prediction.
Required by regulators (RBI) — you must explain WHY a transaction was flagged.
"""

import shap
import numpy as np
from pathlib import Path
import joblib

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR.parent.parent / "ml" / "models" / "xgboost_model.pkl"

_explainer = None


def get_explainer():
    global _explainer
    if _explainer is None:
        model = joblib.load(MODEL_PATH)
        _explainer = shap.TreeExplainer(model)
        print("SHAP TreeExplainer initialized")
    return _explainer


# Human-readable feature name mapping
FEATURE_LABELS = {
    "amount": "Transaction amount",
    "hour": "Time of day",
    "day_of_week": "Day of week",
    "is_night": "Night-time transaction",
    "is_weekend": "Weekend transaction",
    "txn_type_encoded": "Transaction type",
    "sender_txn_count_24h": "Sender activity (24h)",
    "sender_avg_amount": "Sender avg. transaction amount",
    "sender_std_amount": "Sender amount variability",
    "amount_deviation": "Amount deviation from normal",
    "sender_unique_receivers_24h": "Unique receivers (24h)",
    "is_new_device": "New/unrecognized device",
    "is_new_receiver": "First-time receiver",
}


def explain_prediction(features_dict: dict, feature_columns: list, top_n: int = 5) -> list[dict]:
    """
    Generate SHAP-based explanations for a prediction.
    Returns top N features that drove the fraud score, with direction and magnitude.
    """
    explainer = get_explainer()

    # Build ordered feature array
    ordered = [features_dict[col] for col in feature_columns]
    X = np.array(ordered).reshape(1, -1)

    shap_values = explainer.shap_values(X)

    # For binary classification, shap_values may be a list [class_0, class_1] or single array
    if isinstance(shap_values, list):
        sv = shap_values[1][0]  # class 1 (fraud) explanations
    else:
        sv = shap_values[0]

    # Build explanation list
    explanations = []
    for i, (col, shap_val) in enumerate(zip(feature_columns, sv)):
        explanations.append({
            "feature": col,
            "label": FEATURE_LABELS.get(col, col),
            "value": float(ordered[i]),
            "shap_value": round(float(shap_val), 4),
            "direction": "increases_risk" if shap_val > 0 else "decreases_risk",
        })

    # Sort by absolute SHAP value (most impactful first)
    explanations.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

    return explanations[:top_n]


def format_reasons(explanations: list[dict]) -> list[str]:
    """Convert SHAP explanations into simple human-readable sentences."""
    reasons = []
    for exp in explanations:
        if exp.get("direction") != "increases_risk":
            continue

        label = exp.get("label")
        val = exp.get("value")

        feat = exp.get("feature")
        if feat == "amount":
            reasons.append("High amount")
        elif feat == "is_new_device" and val == 1:
            reasons.append("New device")
        elif feat == "is_new_receiver" and val == 1:
            reasons.append("New receiver")
        elif feat == "is_night" and val == 1:
            reasons.append("Unusual time")
        elif feat == "amount_deviation":
            reasons.append("Amount anomaly")
        elif feat == "sender_txn_count_24h":
            reasons.append("High 24h activity")
        elif feat == "sender_unique_receivers_24h":
            reasons.append("Many receivers")
        else:
            if label:
                reasons.append(str(label))

    return reasons
