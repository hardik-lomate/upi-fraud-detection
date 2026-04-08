"""
Feature Contract — THE SINGLE SOURCE OF TRUTH.

Every feature name, order, and transformation rule lives here.
Both training (ml/) and serving (backend/) MUST import from this file.
If this file changes, retrain the model.

DO NOT define feature names, column order, or encoding maps anywhere else.
"""

# ======================================================================
# FEATURE COLUMN ORDER — exactly matches training
# ======================================================================
FEATURE_COLUMNS = [
    "amount",
    "hour",
    "day_of_week",
    "is_night",
    "is_weekend",
    "txn_type_encoded",
    "sender_txn_count_24h",
    "sender_txn_count_1h",
    "sender_txn_count_1min",
    "sender_avg_amount",
    "sender_std_amount",
    "sender_max_amount_7d",
    "amount_deviation",
    "amount_to_avg_ratio",
    "amount_percentile_sender",
    "sender_unique_receivers_24h",
    "sender_unique_receivers_7d",
    "is_new_device",
    "is_new_receiver",
    "receiver_seen_count",
    "receiver_new_sender_ratio_24h",
    "sender_velocity_1min",
    "sender_velocity_5min",
    "geo_distance_km",
    "is_impossible_travel",
    "vpa_suffix_risk_score",
    "upi_age_days",
    "cross_bank_flag",
    "is_high_risk_hour",
    "txn_amount_rank_7d",
    "sender_fraud_score_history",
    "receiver_fraud_flag_count",
]

# Extended features for UI and adaptive logic
EXTENDED_FEATURES = [
    "shap_top_feature_1",
    "shap_top_feature_2",
    "shap_top_feature_3",
    "adaptive_risk_score",
    "user_behavior_drift_score",
]

# ======================================================================
# TRANSACTION TYPE ENCODING — alphabetical to match LabelEncoder
# ======================================================================
# LabelEncoder sorts alphabetically, so:
#   bill_payment=0, purchase=1, recharge=2, transfer=3
TXN_TYPE_MAP = {
    "bill_payment": 0,
    "purchase": 1,
    "recharge": 2,
    "transfer": 3,
}

# ======================================================================
# TIME RULES — consistent between training and serving
# ======================================================================
NIGHT_HOUR_CUTOFF = 5      # hour <= 5 → is_night = 1
WEEKEND_DAY_CUTOFF = 5     # day_of_week >= 5 → is_weekend = 1

# ======================================================================
# DECISION THRESHOLDS
# ======================================================================
THRESHOLD_LOW = 0.30
THRESHOLD_MEDIUM = 0.55
THRESHOLD_HIGH = 0.75
THRESHOLD_BLOCK = 0.75
THRESHOLD_WARN = 0.40

# Bank-side decision thresholds (single risk-score decision contract)
BANK_STEP_UP_THRESHOLD = 0.60
BANK_BLOCK_THRESHOLD = 0.80

# Unified risk score component weights
RISK_COMPONENT_WEIGHTS = {
    "rules": 0.27,
    "ml": 0.33,
    "behavior": 0.18,
    "graph": 0.10,
    "anomaly": 0.12,
}

# Backward-compatible aliases used by older code paths
THRESHOLD_FLAG = THRESHOLD_WARN

RISK_TIER_MAP = {
    "LOW": {
        "min": 0.0,
        "max": 0.39,
        "action": "ALLOW",
        "ui_color": "#22c55e",
        "user_message": "Transaction looks safe. Proceed!",
    },
    "MEDIUM": {
        "min": 0.40,
        "max": 0.74,
        "action": "WARN",
        "ui_color": "#f59e0b",
        "user_message": "This transaction has some unusual signals. Review before proceeding.",
    },
    "HIGH": {
        "min": 0.75,
        "max": 1.0,
        "action": "BLOCK",
        "ui_color": "#ef4444",
        "user_message": "High fraud risk detected. Payment blocked for your protection.",
    },
}


def get_risk_tier(score: float) -> str:
    """Map model score to LOW/MEDIUM/HIGH tier."""
    if score >= THRESHOLD_HIGH:
        return "HIGH"
    if score >= THRESHOLD_WARN:
        return "MEDIUM"
    return "LOW"


def validate_feature_schema(features: dict, allow_extra: bool = True) -> dict:
    """Validate runtime features against canonical FEATURE_COLUMNS.

    Returns a normalized validation payload so callers can decide whether to
    hard-fail or soft-fail based on environment.
    """
    features = features or {}
    missing = [col for col in FEATURE_COLUMNS if col not in features]
    extra = [key for key in features.keys() if key not in FEATURE_COLUMNS]
    is_valid = (len(missing) == 0) and (allow_extra or len(extra) == 0)
    return {
        "is_valid": is_valid,
        "missing": missing,
        "extra": extra,
        "required_count": len(FEATURE_COLUMNS),
        "provided_count": len(features),
    }

# ======================================================================
# MODEL CONFIG
# ======================================================================
MODEL_VERSION = "4.0.0"
ENSEMBLE_DEFAULTS = {
    "lightgbm": 0.35,
    "xgboost": 0.30,
    "catboost": 0.25,
    "isolation_forest": 0.15,
}

# ======================================================================
# NPCI FRAUD TAXONOMY — maps decisions to official fraud type codes
# ======================================================================
NPCI_TAXONOMY = {
    "ALLOW": "Legitimate",
    "VERIFY_MEDIUM": "Social Engineering Suspect",
    "VERIFY_HIGH": "UPI Credential Theft Suspect",
    "BLOCK_VELOCITY": "Technical Fraud — Velocity Attack",
    "BLOCK_MULE": "Money Mule Network",
    "BLOCK_DEVICE": "Device Compromise",
    "BLOCK_RULES": "Rule-Based Block",
    "BLOCK_ML": "ML-Detected Anomaly",
}
