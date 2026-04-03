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
MODEL_VERSION = "2.0.0"
ENSEMBLE_DEFAULTS = {
    "xgboost": 0.45,
    "lightgbm": 0.35,
    "isolation_forest": 0.20,
}
