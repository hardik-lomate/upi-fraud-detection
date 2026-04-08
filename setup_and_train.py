"""One-step bootstrap for training fraud models after a fresh clone.

Run:
  python setup_and_train.py

This script will:
1. Generate raw ML dataset if missing.
2. Engineer model-ready features if missing.
3. Train the ensemble model stack.
4. Verify required artifacts (including model.pkl/features.pkl).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RAW_DATASET = ROOT / "ml" / "data" / "raw" / "transactions.csv"
PROCESSED_DATASET = ROOT / "ml" / "data" / "processed" / "features.csv"

MODEL_ARTIFACTS = [
    ROOT / "ml" / "models" / "model.pkl",
    ROOT / "ml" / "models" / "features.pkl",
    ROOT / "ml" / "models" / "xgboost_model.pkl",
    ROOT / "ml" / "models" / "lightgbm_model.pkl",
    ROOT / "ml" / "models" / "isolation_forest_model.pkl",
    ROOT / "ml" / "models" / "feature_columns.pkl",
    ROOT / "ml" / "models" / "ensemble_weights.pkl",
    ROOT / "ml" / "models" / "iso_calibration.pkl",
]


def _run_step(args: list[str], label: str) -> None:
    cmd = [sys.executable, *args]
    print(f"[setup] {label}: {' '.join(args)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def _ensure_dataset() -> None:
    if not RAW_DATASET.exists():
        _run_step(["ml/generate_data.py"], "Generating raw dataset")
    else:
        print(f"[setup] Raw dataset exists: {RAW_DATASET.relative_to(ROOT)}")

    if not PROCESSED_DATASET.exists():
        _run_step(["ml/feature_engineering.py"], "Generating processed feature dataset")
    else:
        print(f"[setup] Processed dataset exists: {PROCESSED_DATASET.relative_to(ROOT)}")


def _train_models() -> None:
    _run_step(["ml/train_ensemble.py"], "Training ensemble models")


def _verify_artifacts() -> None:
    missing = [str(path.relative_to(ROOT)) for path in MODEL_ARTIFACTS if not path.exists()]
    if missing:
        raise RuntimeError(f"Training completed but required artifacts are missing: {missing}")
    print("[setup] Verified required artifacts:")
    for path in MODEL_ARTIFACTS:
        print(f"  - {path.relative_to(ROOT)}")


def main() -> None:
    print("[setup] Starting one-step model bootstrap")
    _ensure_dataset()
    _train_models()
    _verify_artifacts()
    print("[setup] Done. Backend is ready to load trained models.")


if __name__ == "__main__":
    main()
