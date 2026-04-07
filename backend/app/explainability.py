"""
SHAP Explainability Module — provides human-readable reasons for each prediction.
Required by regulators (RBI) — you must explain WHY a transaction was flagged.
"""

from .shap_service import get_shap_values


FEATURE_REASON_MAP = {
    "amount_deviation": {
        "positive": "Amount is unusually high for this user",
        "negative": "Amount is within normal range",
    },
    "sender_txn_count_1min": {
        "positive": "Multiple payments in under 1 minute",
        "negative": "Normal payment frequency",
    },
    "sender_velocity_5min": {
        "positive": "Burst of payments in 5 minutes",
        "negative": "Normal pace",
    },
    "is_new_device": {
        "positive": "Payment from an unrecognized device",
        "negative": "Known device",
    },
    "is_impossible_travel": {
        "positive": "Location physically impossible given last transaction",
        "negative": "Location consistent",
    },
    "is_new_receiver": {
        "positive": "First payment ever to this UPI ID",
        "negative": "Known receiver",
    },
    "receiver_fraud_flag_count": {
        "positive": "Receiver previously flagged for fraud",
        "negative": "Receiver has clean history",
    },
    "vpa_suffix_risk_score": {
        "positive": "Receiver UPI ID looks suspicious or unverified",
        "negative": "Receiver UPI ID looks legitimate",
    },
    "is_night": {
        "positive": "Transaction at unusual late-night hour",
        "negative": "Normal business hours",
    },
    "geo_distance_km": {
        "positive": "Transaction originated from unexpected location",
        "negative": "Consistent location",
    },
    "amount_to_avg_ratio": {
        "positive": "Amount is much larger than usual for this user",
        "negative": "Amount matches spending habits",
    },
    "upi_age_days": {
        "positive": "Receiver UPI ID is brand new or unknown",
        "negative": "Receiver UPI ID has history",
    },
    "cross_bank_flag": {
        "positive": "Cross-bank transfer to unknown account",
        "negative": "Same-bank transfer",
    },
    "receiver_new_sender_ratio_24h": {
        "positive": "This receiver is getting payments from many new users today",
        "negative": "",
    },
    "sender_unique_receivers_24h": {
        "positive": "Paying many different people today",
        "negative": "",
    },
    "txn_amount_rank_7d": {
        "positive": "This is the largest payment in the last 7 days",
        "negative": "",
    },
}


def explain_prediction(features_dict: dict, feature_columns: list | None = None, top_n: int = 5) -> list[dict]:
    """Return top SHAP-like feature impacts with direction and value."""
    payload = get_shap_values(features_dict, top_n=max(top_n, 8))
    rows = []
    for item in payload.get("top_features", []):
        direction = "increases_risk" if item.get("direction") == "risk_increase" else "decreases_risk"
        rows.append(
            {
                "feature": item.get("feature"),
                "label": item.get("human_label") or item.get("feature"),
                "value": float(item.get("value", 0.0) or 0.0),
                "shap_value": round(float(item.get("shap_value", 0.0) or 0.0), 6),
                "direction": direction,
            }
        )
    return rows[:top_n]


def format_reasons(explanations: list[dict]) -> list[str]:
    """Convert top SHAP factors into plain-English user-facing reasons."""
    reasons = []
    for exp in explanations:
        if exp.get("direction") != "increases_risk":
            continue

        feat = str(exp.get("feature") or "")
        val = float(exp.get("value", 0.0) or 0.0)
        template = FEATURE_REASON_MAP.get(feat, {})
        reason = template.get("positive") if template else str(exp.get("label") or feat)

        if feat == "sender_txn_count_1min" and val >= 1:
            reason = f"{int(val)} payments in the last 60 seconds"
        elif feat == "amount_to_avg_ratio" and val > 1.0:
            reason = f"Amount is {val:.1f}x higher than usual"
        elif feat == "is_new_receiver" and int(val) == 1:
            reason = "First payment to this UPI ID (new receiver)"
        elif feat == "is_new_device" and int(val) == 1:
            reason = "Payment from a new device not seen before"
        elif feat == "is_night" and int(val) == 1:
            reason = "Transaction at an unusual late-night hour"
        elif feat == "receiver_fraud_flag_count" and val > 0:
            reason = f"Receiver has been flagged {int(val)} times before"

        if reason and reason not in reasons:
            reasons.append(reason)

    return reasons
