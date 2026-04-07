"""Generate model metrics and report artifacts.

Outputs:
- ml/models/metrics.json
- ml/reports/confusion_matrix.png
- ml/reports/shap_summary.png
- ml/reports/precision_recall_curve.png
- ml/reports/roc_curve.png
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split

from feature_contract import FEATURE_COLUMNS, ENSEMBLE_DEFAULTS

try:
    import shap
except Exception:
    shap = None

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "ml" / "models"
REPORTS_DIR = ROOT / "ml" / "reports"
DATA_PATH = ROOT / "ml" / "data" / "processed" / "features.csv"


def _load_model(filename: str):
    path = MODELS_DIR / filename
    if path.exists():
        return joblib.load(path)
    return None


def _iso_to_proba(raw_scores: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(raw_scores))


def _calc_metrics(y_true, y_proba, threshold=0.5):
    y_pred = (y_proba >= threshold).astype(int)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
        "pr_auc": float(average_precision_score(y_true, y_proba)),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_PATH)
    x = df[FEATURE_COLUMNS]
    y = df["is_fraud"]

    _, x_test, _, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    models = {
        "XGBoost": _load_model("xgboost_model.pkl"),
        "LightGBM": _load_model("lightgbm_model.pkl"),
        "CatBoost": _load_model("catboost_model.pkl"),
        "IsolationForest": _load_model("isolation_forest_model.pkl"),
    }

    probs = {}
    for name, model in models.items():
        if model is None:
            continue
        if name == "IsolationForest":
            probs[name] = _iso_to_proba(model.decision_function(x_test))
        else:
            probs[name] = model.predict_proba(x_test)[:, 1]

    if not probs:
        raise RuntimeError("No trained models found in ml/models")

    weights = ENSEMBLE_DEFAULTS
    weights_path = MODELS_DIR / "ensemble_weights.pkl"
    if weights_path.exists():
        try:
            weights = joblib.load(weights_path)
        except Exception:
            pass

    ensemble_num = np.zeros(len(x_test), dtype=float)
    ensemble_den = 0.0
    mapping = {
        "LightGBM": "lightgbm",
        "XGBoost": "xgboost",
        "CatBoost": "catboost",
        "IsolationForest": "isolation_forest",
    }
    for model_name, key in mapping.items():
        if model_name in probs:
            w = float(weights.get(key, 0.0))
            ensemble_num += w * probs[model_name]
            ensemble_den += w
    ensemble = ensemble_num / max(ensemble_den, 1e-9)
    probs["Ensemble"] = ensemble

    metrics_per_model = {name: _calc_metrics(y_test, p) for name, p in probs.items()}

    # Save root metrics as ensemble for dashboard simplicity.
    ensemble_metrics = metrics_per_model["Ensemble"]
    payload = {
        **ensemble_metrics,
        "models_evaluated": list(metrics_per_model.keys()),
        "metrics_per_model": metrics_per_model,
    }

    with open(MODELS_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    cm = np.array(ensemble_metrics["confusion_matrix"])
    fig, ax = plt.subplots(figsize=(5.4, 4.4))
    im = ax.imshow(cm, cmap="YlOrRd")
    ax.set_title("Confusion Matrix (Ensemble)")
    ax.set_xticks([0, 1], labels=["Pred Legit", "Pred Fraud"])
    ax.set_yticks([0, 1], labels=["Actual Legit", "Actual Fraud"])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(int(cm[i, j])), ha="center", va="center", color="black", fontsize=12, fontweight="bold")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "confusion_matrix.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    for name, p in probs.items():
        precision, recall, _ = precision_recall_curve(y_test, p)
        ax.plot(recall, precision, label=f"{name} (AP={average_precision_score(y_test, p):.3f})")
    ax.set_title("Precision-Recall Curve")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "precision_recall_curve.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    for name, p in probs.items():
        fpr, tpr, _ = roc_curve(y_test, p)
        ax.plot(fpr, tpr, label=f"{name} (AUC={roc_auc_score(y_test, p):.3f})")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
    ax.set_title("ROC Curve")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "roc_curve.png", dpi=180)
    plt.close(fig)

    # SHAP summary
    shap_done = False
    if shap is not None:
        explainer_path = MODELS_DIR / "shap_explainer.pkl"
        if explainer_path.exists():
            try:
                explainer = joblib.load(explainer_path)
                sample = x_test.sample(min(1500, len(x_test)), random_state=42)
                shap_values = explainer(sample)
                shap.summary_plot(shap_values, sample, feature_names=FEATURE_COLUMNS, show=False)
                plt.tight_layout()
                plt.savefig(REPORTS_DIR / "shap_summary.png", dpi=180)
                plt.close()
                shap_done = True
            except Exception:
                shap_done = False

    if not shap_done:
        lgbm = models.get("LightGBM")
        fig, ax = plt.subplots(figsize=(6.8, 4.8))
        if lgbm is not None and hasattr(lgbm, "feature_importances_"):
            imps = np.array(lgbm.feature_importances_, dtype=float)
            idx = np.argsort(imps)[::-1][:12]
            ax.barh([FEATURE_COLUMNS[i] for i in idx][::-1], imps[idx][::-1], color="#2d6a4f")
            ax.set_title("Feature Importance (LightGBM)")
        else:
            ax.text(0.5, 0.5, "SHAP artifact unavailable", ha="center", va="center")
            ax.set_axis_off()
        fig.tight_layout()
        fig.savefig(REPORTS_DIR / "shap_summary.png", dpi=180)
        plt.close(fig)

    print("Saved metrics to ml/models/metrics.json")


if __name__ == "__main__":
    main()
