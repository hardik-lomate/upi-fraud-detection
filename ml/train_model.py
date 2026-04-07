import json
import os
import sys
from datetime import datetime

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from lightgbm import LGBMClassifier
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from feature_contract import ENSEMBLE_DEFAULTS, FEATURE_COLUMNS, validate_feature_schema

try:
    from catboost import CatBoostClassifier
except Exception:
    CatBoostClassifier = None


def _safe_proba(model, x):
    return model.predict_proba(x)[:, 1]


def _validate_training_inputs(df: pd.DataFrame) -> None:
    missing = [col for col in FEATURE_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Training data missing required feature columns: {missing}")
    if "is_fraud" not in df.columns:
        raise ValueError("Training data must include target column: is_fraud")

    if len(df) == 0:
        raise ValueError("Training data is empty")

    sample = {}
    row = df.iloc[0]
    for col in FEATURE_COLUMNS:
        sample[col] = float(pd.to_numeric(row[col], errors="coerce") if pd.notna(row[col]) else 0.0)

    contract = validate_feature_schema(sample, allow_extra=False)
    if not contract.get("is_valid", False):
        raise ValueError(f"Feature contract validation failed for training sample: {contract}")


def main():
    df = pd.read_csv("ml/data/processed/features.csv")
    _validate_training_inputs(df)

    x = df[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y = pd.to_numeric(df["is_fraud"], errors="coerce").fillna(0).astype(int)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    scale_weight = float(neg / max(pos, 1))
    print(f"Class distribution train: neg={neg}, pos={pos}, scale_pos_weight={scale_weight:.2f}")

    lgbm_model = LGBMClassifier(
        n_estimators=500,
        max_depth=7,
        learning_rate=0.05,
        num_leaves=63,
        scale_pos_weight=scale_weight,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=0.1,
        min_child_samples=20,
        random_state=42,
        verbose=-1,
    )
    lgbm_model.fit(x_train, y_train)

    xgb_model = XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        scale_pos_weight=scale_weight,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="aucpr",
        random_state=42,
        use_label_encoder=False,
    )
    xgb_model.fit(x_train, y_train)

    cat_model = None
    if CatBoostClassifier is not None:
        try:
            cat_model = CatBoostClassifier(
                iterations=350,
                depth=6,
                learning_rate=0.05,
                loss_function="Logloss",
                verbose=False,
                random_state=42,
            )
            cat_model.fit(x_train, y_train)
        except Exception as exc:
            print(f"CatBoost training skipped: {exc}")

    iso_model = IsolationForest(n_estimators=200, contamination=0.03, random_state=42, n_jobs=-1)
    iso_model.fit(x_train)

    lgbm_proba = _safe_proba(lgbm_model, x_test)
    xgb_proba = _safe_proba(xgb_model, x_test)
    cat_proba = _safe_proba(cat_model, x_test) if cat_model is not None else None

    iso_train_raw = np.asarray(iso_model.decision_function(x_train), dtype=float)
    iso_min = float(np.min(iso_train_raw))
    iso_max = float(np.max(iso_train_raw))
    iso_denom = max(iso_max - iso_min, 1e-9)
    iso_calibration = {
        "method": "minmax_inverse",
        "min": iso_min,
        "max": iso_max,
    }

    raw_iso = np.asarray(iso_model.decision_function(x_test), dtype=float)
    # Calibrated: lower decision_function means more anomalous (higher risk).
    iso_proba = 1.0 - ((raw_iso - iso_min) / iso_denom)
    iso_proba = np.clip(iso_proba, 0.0, 1.0)

    weights = dict(ENSEMBLE_DEFAULTS)
    used_weights = {
        "lightgbm": weights.get("lightgbm", 0.35),
        "xgboost": weights.get("xgboost", 0.30),
        "isolation_forest": weights.get("isolation_forest", 0.10),
    }
    if cat_proba is not None:
        used_weights["catboost"] = weights.get("catboost", 0.25)

    total_weight = float(sum(used_weights.values()))
    y_proba = (
        used_weights.get("lightgbm", 0.0) * lgbm_proba
        + used_weights.get("xgboost", 0.0) * xgb_proba
        + used_weights.get("isolation_forest", 0.0) * iso_proba
        + (used_weights.get("catboost", 0.0) * cat_proba if cat_proba is not None else 0.0)
    ) / max(total_weight, 1e-6)

    y_pred = (y_proba >= 0.5).astype(int)

    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_test, y_pred)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
        "pr_auc": float(average_precision_score(y_test, y_proba)),
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
        "weights_used": used_weights,
        "iso_calibration": iso_calibration,
    }
    # Backward-compatible alias retained for older readers.
    metrics["f1"] = metrics["f1_score"]

    os.makedirs("ml/models", exist_ok=True)
    os.makedirs("ml/reports", exist_ok=True)

    joblib.dump(lgbm_model, "ml/models/lightgbm_model.pkl")
    joblib.dump(xgb_model, "ml/models/xgboost_model.pkl")
    if cat_model is not None:
        joblib.dump(cat_model, "ml/models/catboost_model.pkl")
    joblib.dump(iso_model, "ml/models/isolation_forest_model.pkl")
    joblib.dump(iso_calibration, "ml/models/iso_calibration.pkl")
    joblib.dump(FEATURE_COLUMNS, "ml/models/feature_columns.pkl")
    joblib.dump(used_weights, "ml/models/ensemble_weights.pkl")

    with open("ml/models/metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    metadata = {
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "training_rows": int(len(df)),
        "feature_count": int(len(FEATURE_COLUMNS)),
        "feature_columns": list(FEATURE_COLUMNS),
        "fraud_ratio": float(y.mean()),
        "metrics": {
            "accuracy": metrics["accuracy"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1_score": metrics["f1_score"],
            "f1": metrics["f1_score"],
            "roc_auc": metrics["roc_auc"],
            "pr_auc": metrics["pr_auc"],
        },
    }
    with open("ml/models/model_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # SHAP export from LightGBM (primary model)
    explainer = shap.TreeExplainer(lgbm_model)
    sample = x_test.sample(min(2000, len(x_test)), random_state=42)
    shap_values = explainer(sample)
    shap.summary_plot(shap_values, sample, feature_names=FEATURE_COLUMNS, show=False)
    plt.tight_layout()
    plt.savefig("ml/reports/shap_summary.png", dpi=180)
    plt.close()

    joblib.dump(explainer, "ml/models/shap_explainer.pkl")

    print("Training complete")
    print(
        json.dumps(
            {
                "accuracy": metrics["accuracy"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1_score": metrics["f1_score"],
                "confusion_matrix": metrics["confusion_matrix"],
                "roc_auc": metrics["roc_auc"],
                "pr_auc": metrics["pr_auc"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
