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
    "sender_avg_amount",
    "sender_std_amount",
    "amount_deviation",
    "sender_unique_receivers_24h",
    "is_new_device",
    "is_new_receiver",
]

# Extended features for v3.0 — used by feature store, not in base model input
EXTENDED_FEATURES = [
    "sender_velocity_1min",
    "sender_velocity_5min",
    "vpa_suffix_risk_score",
    "upi_age_days",
    "receiver_new_sender_ratio_24h",
    "amount_percentile_sender",
    "cross_bank_ratio",
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
THRESHOLD_FLAG = 0.3        # score >= 0.3 → FLAG
THRESHOLD_BLOCK = 0.7       # score >= 0.7 → BLOCK

# ======================================================================
# MODEL CONFIG
# ======================================================================
MODEL_VERSION = "3.0.0"
ENSEMBLE_DEFAULTS = {
    "xgboost": 0.30,
    "lightgbm": 0.30,
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
