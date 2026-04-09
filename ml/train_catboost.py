"""
CatBoost Model Training — Native categorical feature handling.

CatBoost handles categorical UPI IDs natively without label encoding,
reducing leakage. Runs as a standalone training script to produce
ml/models/catboost_model.pkl.
"""

import pandas as pd
import numpy as np
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from feature_contract import FEATURE_COLUMNS, MODEL_VERSION

try:
    from catboost import CatBoostClassifier
except ImportError:
    print("[ERROR] CatBoost not installed. Run: pip install catboost")
    sys.exit(1)

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import roc_auc_score, average_precision_score, classification_report
import joblib

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "processed" / "features.csv"
MODELS_DIR = BASE_DIR / "models"

# ========== Load Data ==========
if not DATA_PATH.exists():
    print(f"[ERROR] Data file not found: {DATA_PATH}")
    print("Run ml/generate_data.py and ml/feature_engineering.py first.")
    sys.exit(1)

df = pd.read_csv(DATA_PATH)
X = df[FEATURE_COLUMNS]
y = df["is_fraud"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

neg, pos = (y_train == 0).sum(), (y_train == 1).sum()
print(f"=== CatBoost Training ===")
print(f"Train: {len(X_train)} ({pos} fraud, {neg} legit)")
print(f"Test:  {len(X_test)}")

# ========== CatBoost ==========
# Identify categorical feature indices
cat_feature_indices = [FEATURE_COLUMNS.index("txn_type_encoded")]

cat_model = CatBoostClassifier(
    iterations=500,
    depth=8,
    learning_rate=0.05,
    cat_features=cat_feature_indices,
    auto_class_weights="Balanced",
    eval_metric="AUC",
    random_seed=42,
    verbose=100,
)

cat_model.fit(
    X_train, y_train,
    eval_set=(X_test, y_test),
    early_stopping_rounds=50,
)

cat_proba = cat_model.predict_proba(X_test)[:, 1]
cat_auc = roc_auc_score(y_test, cat_proba)
cat_pr = average_precision_score(y_test, cat_proba)

print(f"\nCatBoost ROC AUC: {cat_auc:.4f}  PR AUC: {cat_pr:.4f}")
print(f"\n{classification_report(y_test, (cat_proba >= 0.5).astype(int))}")

# ========== Cross-Validation ==========
print("=== 5-Fold CV ===")
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_auc = cross_val_score(cat_model, X, y, cv=cv, scoring="roc_auc", n_jobs=-1)
print(f"CatBoost CV ROC AUC: {cv_auc.mean():.4f} ± {cv_auc.std():.4f}")

# ========== Feature Importance ==========
print("\n=== Feature Importance (CatBoost) ===")
importances = cat_model.feature_importances_
feat_imp = sorted(zip(FEATURE_COLUMNS, importances), key=lambda x: -x[1])
for feat, imp in feat_imp:
    print(f"  {feat:35s} {imp:.4f}")

# ========== Save ==========
MODELS_DIR.mkdir(parents=True, exist_ok=True)
out_path = MODELS_DIR / "catboost_model.pkl"
joblib.dump(cat_model, out_path)
print(f"\n[OK] CatBoost model saved to {out_path}")
print(f"     ROC AUC: {cat_auc:.4f}, PR AUC: {cat_pr:.4f}")
