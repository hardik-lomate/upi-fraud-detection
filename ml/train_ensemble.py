"""
Ensemble Model Training — Trains XGBoost + LightGBM + Isolation Forest.
The final score is a weighted average: safety in numbers.
Also generates reference distribution for monitoring.
"""

import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, roc_auc_score, average_precision_score, confusion_matrix,
)
import joblib
import json
import os

# --- Load data ---
df = pd.read_csv("ml/data/processed/features.csv")

FEATURE_COLS = [
    "amount", "hour", "day_of_week", "is_night", "is_weekend",
    "txn_type_encoded", "sender_txn_count_24h", "sender_avg_amount",
    "sender_std_amount", "amount_deviation", "sender_unique_receivers_24h",
    "is_new_device", "is_new_receiver",
]

X = df[FEATURE_COLS]
y = df["is_fraud"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

neg = (y_train == 0).sum()
pos = (y_train == 1).sum()
scale_weight = neg / pos
print(f"=== Data ===")
print(f"Train: {len(X_train)} ({pos} fraud, {neg} legit)")
print(f"Test:  {len(X_test)}")
print(f"scale_pos_weight: {scale_weight:.1f}")

# ==========================================
# 1. XGBoost (Primary)
# ==========================================
print("\n=== Training XGBoost ===")
xgb_model = XGBClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    scale_pos_weight=scale_weight,
    eval_metric="aucpr",
    random_state=42,
    use_label_encoder=False,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=1.0,
)
xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=50)

xgb_proba = xgb_model.predict_proba(X_test)[:, 1]
print(f"XGBoost ROC AUC: {roc_auc_score(y_test, xgb_proba):.4f}")
print(f"XGBoost PR AUC:  {average_precision_score(y_test, xgb_proba):.4f}")

# ==========================================
# 2. LightGBM (Secondary)
# ==========================================
print("\n=== Training LightGBM ===")
lgbm_model = LGBMClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    scale_pos_weight=scale_weight,
    random_state=42,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=1.0,
    verbose=-1,
)
lgbm_model.fit(X_train, y_train, eval_set=[(X_test, y_test)])

lgbm_proba = lgbm_model.predict_proba(X_test)[:, 1]
print(f"LightGBM ROC AUC: {roc_auc_score(y_test, lgbm_proba):.4f}")
print(f"LightGBM PR AUC:  {average_precision_score(y_test, lgbm_proba):.4f}")

# ==========================================
# 3. Isolation Forest (Anomaly Detection)
# ==========================================
print("\n=== Training Isolation Forest ===")
iso_model = IsolationForest(
    n_estimators=200,
    contamination=0.03,
    random_state=42,
    n_jobs=-1,
)
iso_model.fit(X_train)

iso_scores = iso_model.decision_function(X_test)
# Convert to 0-1 range (lower decision_function = more anomalous)
iso_proba = 1 - (iso_scores - iso_scores.min()) / (iso_scores.max() - iso_scores.min())
print(f"IsoForest ROC AUC: {roc_auc_score(y_test, iso_proba):.4f}")

# ==========================================
# 4. Ensemble (Weighted Average)
# ==========================================
print("\n=== Ensemble ===")
WEIGHTS = {"xgboost": 0.45, "lightgbm": 0.35, "isolation_forest": 0.20}

ensemble_proba = (
    WEIGHTS["xgboost"] * xgb_proba +
    WEIGHTS["lightgbm"] * lgbm_proba +
    WEIGHTS["isolation_forest"] * iso_proba
)

print(f"Ensemble ROC AUC: {roc_auc_score(y_test, ensemble_proba):.4f}")
print(f"Ensemble PR AUC:  {average_precision_score(y_test, ensemble_proba):.4f}")

ensemble_pred = (ensemble_proba >= 0.5).astype(int)
print(f"\n{classification_report(y_test, ensemble_pred)}")
print(f"Confusion Matrix:\n{confusion_matrix(y_test, ensemble_pred)}")

# --- Feature Importance (XGBoost) ---
print("\n=== Feature Importance (XGBoost) ===")
for feat, imp in sorted(zip(FEATURE_COLS, xgb_model.feature_importances_), key=lambda x: -x[1]):
    print(f"  {feat:35s} {imp:.4f}")

# ==========================================
# Save Everything
# ==========================================
os.makedirs("ml/models", exist_ok=True)

joblib.dump(xgb_model, "ml/models/xgboost_model.pkl")
joblib.dump(lgbm_model, "ml/models/lightgbm_model.pkl")
joblib.dump(iso_model, "ml/models/isolation_forest_model.pkl")
joblib.dump(FEATURE_COLS, "ml/models/feature_columns.pkl")
joblib.dump(WEIGHTS, "ml/models/ensemble_weights.pkl")

# Save reference distribution for monitoring
ref_scores = ensemble_proba.tolist()
os.makedirs("monitoring", exist_ok=True)
with open("monitoring/reference_distribution.json", "w") as f:
    json.dump(ref_scores, f)
print(f"\nReference distribution saved: {len(ref_scores)} scores")

print("\n✅ All models saved:")
print("  - ml/models/xgboost_model.pkl")
print("  - ml/models/lightgbm_model.pkl")
print("  - ml/models/isolation_forest_model.pkl")
print("  - ml/models/feature_columns.pkl")
print("  - ml/models/ensemble_weights.pkl")
print("  - monitoring/reference_distribution.json")
