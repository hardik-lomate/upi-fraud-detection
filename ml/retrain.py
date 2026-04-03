"""
Retraining Pipeline — Closes the monitoring feedback loop.

Usage:
    python ml/retrain.py                    # retrain from scratch
    python ml/retrain.py --incremental      # incremental retrain

Steps:
    1. Load labeled data (original + any new confirmed labels)
    2. Re-run feature engineering
    3. Train ensemble models
    4. Generate new reference distribution
    5. Save models with version bump
"""

import pandas as pd
import numpy as np
import json
import os
import sys
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from feature_contract import FEATURE_COLUMNS, ENSEMBLE_DEFAULTS

from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, average_precision_score
import joblib


def load_training_data():
    """Load feature-engineered data. In production, merge with feedback labels."""
    base_path = "ml/data/processed/features.csv"
    if not os.path.exists(base_path):
        print("ERROR: No processed features found. Run feature_engineering.py first.")
        sys.exit(1)

    df = pd.read_csv(base_path)

    # Check for feedback data (confirmed fraud labels from production)
    feedback_path = "ml/data/feedback/confirmed_labels.csv"
    if os.path.exists(feedback_path):
        feedback = pd.read_csv(feedback_path)
        print(f"Merging {len(feedback)} feedback labels...")
        df = pd.concat([df, feedback[FEATURE_COLUMNS + ["is_fraud"]]], ignore_index=True)

    return df


def train_and_save(df, version_tag=None):
    X = df[FEATURE_COLUMNS]
    y = df["is_fraud"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    neg, pos = (y_train == 0).sum(), (y_train == 1).sum()
    scale_weight = neg / pos
    print(f"\nData: {len(X_train)} train ({pos} fraud), {len(X_test)} test")

    # XGBoost
    print("\n--- XGBoost ---")
    xgb = XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        scale_pos_weight=scale_weight, eval_metric="aucpr",
        random_state=42, use_label_encoder=False,
        subsample=0.8, colsample_bytree=0.8,
    )
    xgb.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=50)
    xgb_proba = xgb.predict_proba(X_test)[:, 1]
    print(f"  ROC AUC: {roc_auc_score(y_test, xgb_proba):.4f}")
    print(f"  PR AUC:  {average_precision_score(y_test, xgb_proba):.4f}")

    # LightGBM
    print("\n--- LightGBM ---")
    lgbm = LGBMClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        scale_pos_weight=scale_weight, random_state=42,
        subsample=0.8, colsample_bytree=0.8, verbose=-1,
    )
    lgbm.fit(X_train, y_train, eval_set=[(X_test, y_test)])
    lgbm_proba = lgbm.predict_proba(X_test)[:, 1]
    print(f"  ROC AUC: {roc_auc_score(y_test, lgbm_proba):.4f}")
    print(f"  PR AUC:  {average_precision_score(y_test, lgbm_proba):.4f}")

    # Isolation Forest
    print("\n--- Isolation Forest ---")
    iso = IsolationForest(n_estimators=200, contamination=0.03, random_state=42, n_jobs=-1)
    iso.fit(X_train)
    iso_raw = iso.decision_function(X_test)
    iso_proba = 1 - (iso_raw - iso_raw.min()) / (iso_raw.max() - iso_raw.min())

    # Ensemble
    w = ENSEMBLE_DEFAULTS
    ensemble = w["xgboost"] * xgb_proba + w["lightgbm"] * lgbm_proba + w["isolation_forest"] * iso_proba
    print(f"\n=== Ensemble ROC AUC: {roc_auc_score(y_test, ensemble):.4f} ===")
    print(f"=== Ensemble PR AUC:  {average_precision_score(y_test, ensemble):.4f} ===")
    print(classification_report(y_test, (ensemble >= 0.5).astype(int)))

    # Save
    os.makedirs("ml/models", exist_ok=True)
    os.makedirs("monitoring", exist_ok=True)

    joblib.dump(xgb, "ml/models/xgboost_model.pkl")
    joblib.dump(lgbm, "ml/models/lightgbm_model.pkl")
    joblib.dump(iso, "ml/models/isolation_forest_model.pkl")
    joblib.dump(FEATURE_COLUMNS, "ml/models/feature_columns.pkl")
    joblib.dump(ENSEMBLE_DEFAULTS, "ml/models/ensemble_weights.pkl")

    ref_scores = ensemble.tolist()
    with open("monitoring/reference_distribution.json", "w") as f:
        json.dump(ref_scores, f)

    # Save metadata
    version = version_tag or datetime.now().strftime("%Y%m%d_%H%M%S")
    meta = {
        "version": version,
        "trained_at": datetime.now().isoformat(),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "fraud_rate": float(pos / len(y_train)),
        "ensemble_auc": float(roc_auc_score(y_test, ensemble)),
        "feature_columns": FEATURE_COLUMNS,
        "weights": ENSEMBLE_DEFAULTS,
    }
    with open("ml/models/model_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n✅ Models saved (version: {version})")
    print("   Restart the backend to load new models.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrain fraud detection models")
    parser.add_argument("--version", type=str, help="Version tag for this training run")
    args = parser.parse_args()

    print(f"=== Retraining Pipeline ({datetime.now().isoformat()}) ===")
    df = load_training_data()
    train_and_save(df, version_tag=args.version)
