import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    roc_auc_score,
    confusion_matrix,
    average_precision_score,
)
import joblib
import os

# --- Load data ---
df = pd.read_csv("ml/data/processed/features.csv")

FEATURE_COLS = [
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

X = df[FEATURE_COLS]
y = df["is_fraud"]

# --- Split ---
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# --- Handle imbalance ---
neg = (y_train == 0).sum()
pos = (y_train == 1).sum()
scale_weight = neg / pos
print(f"Class distribution: {neg} negative, {pos} positive")
print(f"scale_pos_weight: {scale_weight:.1f}")

# --- Train ---
model = XGBClassifier(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.1,
    scale_pos_weight=scale_weight,
    eval_metric="aucpr",
    random_state=42,
    use_label_encoder=False,
)

model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=20)

# --- Evaluate ---
y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

print("\n=== Classification Report ===")
print(classification_report(y_test, y_pred))

print(f"ROC AUC: {roc_auc_score(y_test, y_proba):.4f}")
print(f"PR AUC:  {average_precision_score(y_test, y_proba):.4f}")

print("\n=== Confusion Matrix ===")
print(confusion_matrix(y_test, y_pred))

# --- Feature Importance ---
importance = model.feature_importances_
print("\n=== Feature Importance ===")
for feat, imp in sorted(zip(FEATURE_COLS, importance), key=lambda x: -x[1]):
    print(f"  {feat:30s} {imp:.4f}")

# --- Save ---
os.makedirs("ml/models", exist_ok=True)
joblib.dump(model, "ml/models/xgboost_model.pkl")
joblib.dump(FEATURE_COLS, "ml/models/feature_columns.pkl")
print("\nModel saved to ml/models/xgboost_model.pkl")
