"""
Ensemble Model Training — XGBoost + LightGBM + Isolation Forest.
Includes: k-fold CV, threshold optimization (F0.5/recall), IsoForest calibration.
Imports from feature_contract.py — single source of truth.
"""

import pandas as pd
import numpy as np
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from feature_contract import FEATURE_COLUMNS, ENSEMBLE_DEFAULTS, MODEL_VERSION

from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import (
    classification_report, roc_auc_score, average_precision_score,
    confusion_matrix, precision_recall_curve, f1_score, precision_score, recall_score,
)
import joblib

# ========== Load Data ==========
df = pd.read_csv("ml/data/processed/features.csv")
X = df[FEATURE_COLUMNS]
y = df["is_fraud"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

neg, pos = (y_train == 0).sum(), (y_train == 1).sum()
scale_weight = neg / pos
print(f"=== Data ===")
print(f"Train: {len(X_train)} ({pos} fraud, {neg} legit)")
print(f"Test:  {len(X_test)}")
print(f"scale_pos_weight: {scale_weight:.1f}")

# ========== 1. XGBoost ==========
print("\n=== Training XGBoost ===")
xgb_model = XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.05,
    scale_pos_weight=scale_weight, eval_metric="aucpr",
    random_state=42, use_label_encoder=False,
    subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=1.0,
)
xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=50)
xgb_proba = xgb_model.predict_proba(X_test)[:, 1]
xgb_auc = roc_auc_score(y_test, xgb_proba)
xgb_pr = average_precision_score(y_test, xgb_proba)
print(f"XGBoost ROC AUC: {xgb_auc:.4f}  PR AUC: {xgb_pr:.4f}")

# ========== 2. LightGBM ==========
print("\n=== Training LightGBM ===")
lgbm_model = LGBMClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.05,
    scale_pos_weight=scale_weight, random_state=42,
    subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=1.0, verbose=-1,
)
lgbm_model.fit(X_train, y_train, eval_set=[(X_test, y_test)])
lgbm_proba = lgbm_model.predict_proba(X_test)[:, 1]
lgbm_auc = roc_auc_score(y_test, lgbm_proba)
lgbm_pr = average_precision_score(y_test, lgbm_proba)
print(f"LightGBM ROC AUC: {lgbm_auc:.4f}  PR AUC: {lgbm_pr:.4f}")

# ========== 3. Isolation Forest ==========
print("\n=== Training Isolation Forest ===")
iso_model = IsolationForest(n_estimators=200, contamination=0.03, random_state=42, n_jobs=-1)
iso_model.fit(X_train)

# CALIBRATION: compute min/max from TRAINING set (not test)
iso_train_scores = iso_model.decision_function(X_train)
iso_calib = {"min": float(iso_train_scores.min()), "max": float(iso_train_scores.max())}
print(f"IsoForest calibration: min={iso_calib['min']:.4f}, max={iso_calib['max']:.4f}")

iso_test_raw = iso_model.decision_function(X_test)
iso_proba = np.clip(1 - (iso_test_raw - iso_calib["min"]) / (iso_calib["max"] - iso_calib["min"]), 0, 1)
iso_auc = roc_auc_score(y_test, iso_proba)
print(f"IsoForest ROC AUC: {iso_auc:.4f}")

# ========== 4. Cross-Validation ==========
print("\n=== 5-Fold Stratified CV ===")
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
xgb_cv_auc = cross_val_score(xgb_model, X, y, cv=cv, scoring="roc_auc", n_jobs=-1)
xgb_cv_pr = cross_val_score(xgb_model, X, y, cv=cv, scoring="average_precision", n_jobs=-1)
lgbm_cv_auc = cross_val_score(lgbm_model, X, y, cv=cv, scoring="roc_auc", n_jobs=-1)
lgbm_cv_pr = cross_val_score(lgbm_model, X, y, cv=cv, scoring="average_precision", n_jobs=-1)
print(f"XGBoost  CV ROC AUC: {xgb_cv_auc.mean():.4f} ± {xgb_cv_auc.std():.4f}")
print(f"XGBoost  CV PR AUC:  {xgb_cv_pr.mean():.4f} ± {xgb_cv_pr.std():.4f}")
print(f"LightGBM CV ROC AUC: {lgbm_cv_auc.mean():.4f} ± {lgbm_cv_auc.std():.4f}")
print(f"LightGBM CV PR AUC:  {lgbm_cv_pr.mean():.4f} ± {lgbm_cv_pr.std():.4f}")

# ========== 5. Ensemble ==========
print("\n=== Ensemble ===")
w_raw = dict(ENSEMBLE_DEFAULTS)
active_sum = float(w_raw.get("xgboost", 0.0) + w_raw.get("lightgbm", 0.0) + w_raw.get("isolation_forest", 0.0))
if active_sum <= 0:
    active_sum = 1.0
w = {
    "xgboost": float(w_raw.get("xgboost", 0.0)) / active_sum,
    "lightgbm": float(w_raw.get("lightgbm", 0.0)) / active_sum,
    "isolation_forest": float(w_raw.get("isolation_forest", 0.0)) / active_sum,
}
ensemble_proba = w["xgboost"] * xgb_proba + w["lightgbm"] * lgbm_proba + w["isolation_forest"] * iso_proba
ens_auc = roc_auc_score(y_test, ensemble_proba)
ens_pr = average_precision_score(y_test, ensemble_proba)
print(f"Ensemble ROC AUC: {ens_auc:.4f}  PR AUC: {ens_pr:.4f}")

# ========== 6. Threshold Optimization (F0.5 + Recall ≥ 90%) ==========
print("\n=== Threshold Optimization ===")
precision_arr, recall_arr, thresholds_arr = precision_recall_curve(y_test, ensemble_proba)

# F0.5 score: weights precision 2x over recall
beta = 0.5
f_beta = ((1 + beta**2) * precision_arr[:-1] * recall_arr[:-1]) / \
         (beta**2 * precision_arr[:-1] + recall_arr[:-1] + 1e-10)
best_idx = np.argmax(f_beta)
threshold_block = float(thresholds_arr[best_idx])

# FLAG threshold: recall >= 0.90
recall_90_idx = np.where(recall_arr[:-1] >= 0.90)[0]
threshold_flag = float(thresholds_arr[recall_90_idx[-1]]) if len(recall_90_idx) > 0 else 0.15

print(f"Optimal BLOCK threshold (max F0.5): {threshold_block:.4f}")
print(f"  -> Precision: {precision_arr[best_idx]:.4f}, Recall: {recall_arr[best_idx]:.4f}, F0.5: {f_beta[best_idx]:.4f}")
print(f"Optimal FLAG threshold (recall≥90%): {threshold_flag:.4f}")

# Compute metrics at chosen thresholds
ens_pred_block = (ensemble_proba >= threshold_block).astype(int)
print(f"\n{classification_report(y_test, ens_pred_block)}")
print(f"Confusion Matrix:\n{confusion_matrix(y_test, ens_pred_block)}")

# Feature importance
print("\n=== Feature Importance (XGBoost) ===")
feat_imp = sorted(zip(FEATURE_COLUMNS, xgb_model.feature_importances_), key=lambda x: -x[1])
for feat, imp in feat_imp:
    print(f"  {feat:35s} {imp:.4f}")

# ========== Save Everything ==========
os.makedirs("ml/models", exist_ok=True)
os.makedirs("monitoring", exist_ok=True)

joblib.dump(xgb_model, "ml/models/xgboost_model.pkl")
joblib.dump(lgbm_model, "ml/models/lightgbm_model.pkl")
joblib.dump(iso_model, "ml/models/isolation_forest_model.pkl")
joblib.dump(FEATURE_COLUMNS, "ml/models/feature_columns.pkl")
joblib.dump(w, "ml/models/ensemble_weights.pkl")
joblib.dump(iso_calib, "ml/models/iso_calibration.pkl")

model_bundle = {
    "models": {
        "xgboost": xgb_model,
        "lightgbm": lgbm_model,
        "isolation_forest": iso_model,
    },
    "weights": w,
    "iso_calibration": iso_calib,
    "feature_columns": FEATURE_COLUMNS,
    "threshold_block": float(threshold_block),
    "threshold_flag": float(threshold_flag),
    "trained_at": datetime.now().isoformat(),
}
joblib.dump(model_bundle, "ml/models/model.pkl")
joblib.dump(FEATURE_COLUMNS, "ml/models/features.pkl")

# Thresholds
thresholds_data = {
    "threshold_flag": round(threshold_flag, 4),
    "threshold_block": round(threshold_block, 4),
    "flag_precision": round(float(precision_arr[recall_90_idx[-1]]) if len(recall_90_idx) else 0, 4),
    "flag_recall": 0.9,
    "block_precision": round(float(precision_arr[best_idx]), 4),
    "block_recall": round(float(recall_arr[best_idx]), 4),
    "block_f05": round(float(f_beta[best_idx]), 4),
}
with open("ml/models/thresholds.json", "w") as f:
    json.dump(thresholds_data, f, indent=2)

# Reference distribution
with open("monitoring/reference_distribution.json", "w") as f:
    json.dump(ensemble_proba.tolist(), f)

# Rich metadata
metadata = {
    "model_version": MODEL_VERSION,
    "trained_at": datetime.now().isoformat(),
    "training_data_rows": len(X_train),
    "test_data_rows": len(X_test),
    "training_fraud_rate": round(float(pos / len(y_train)), 4),
    "feature_columns": FEATURE_COLUMNS,
    "ensemble_weights": w,
    "thresholds": thresholds_data,
    "per_model_metrics": {
        "xgboost": {"roc_auc": round(xgb_auc, 4), "pr_auc": round(xgb_pr, 4),
                     "cv_roc_auc_mean": round(float(xgb_cv_auc.mean()), 4),
                     "cv_roc_auc_std": round(float(xgb_cv_auc.std()), 4)},
        "lightgbm": {"roc_auc": round(lgbm_auc, 4), "pr_auc": round(lgbm_pr, 4),
                      "cv_roc_auc_mean": round(float(lgbm_cv_auc.mean()), 4),
                      "cv_roc_auc_std": round(float(lgbm_cv_auc.std()), 4)},
        "isolation_forest": {"roc_auc": round(iso_auc, 4)},
    },
    "ensemble_metrics": {
        "roc_auc": round(ens_auc, 4), "pr_auc": round(ens_pr, 4),
        "f1_at_block": round(float(f1_score(y_test, ens_pred_block)), 4),
        "precision_at_block": round(float(precision_score(y_test, ens_pred_block)), 4),
        "recall_at_block": round(float(recall_score(y_test, ens_pred_block)), 4),
    },
    "top_features": [{"name": f, "importance": round(float(i), 4)} for f, i in feat_imp[:5]],
    "iso_calibration": iso_calib,
    "class_distribution": {"fraud": int(pos), "legit": int(neg)},
}
with open("ml/models/model_metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)

print(f"\n[OK] All saved:")
print(f"  Models: xgboost, lightgbm, isolation_forest")
print(f"  Bundle: model.pkl, features.pkl")
print(f"  Calibration: iso_calibration.pkl")
print(f"  Thresholds: {thresholds_data}")
print(f"  Metadata: model_metadata.json")
