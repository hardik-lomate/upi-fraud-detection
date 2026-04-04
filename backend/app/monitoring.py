"""
Model Monitoring — Track prediction distribution and detect data drift.
Uses Population Stability Index (PSI) to alert when model may be degrading.
"""

import numpy as np
from collections import deque
from datetime import datetime
import json
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import THRESHOLD_FLAG, THRESHOLD_BLOCK

# Rolling window of recent predictions for monitoring
WINDOW_SIZE = 1000
prediction_window = deque(maxlen=WINDOW_SIZE)

# Reference distribution from training (populated on startup)
reference_distribution = None

MONITOR_DIR = Path(__file__).resolve().parent.parent.parent / "monitoring"
MONITOR_DIR.mkdir(exist_ok=True)


def record_prediction(fraud_score: float, features: dict):
    """Record a prediction for monitoring."""
    prediction_window.append({
        "score": fraud_score,
        "features": features,
        "timestamp": datetime.utcnow().isoformat(),
    })


def compute_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """
    Population Stability Index (PSI).
    PSI < 0.1: No significant change
    PSI 0.1-0.25: Moderate change — investigate
    PSI > 0.25: Significant change — retrain model
    """
    min_val = min(expected.min(), actual.min())
    max_val = max(expected.max(), actual.max())
    bin_edges = np.linspace(min_val, max_val, bins + 1)

    expected_hist = np.histogram(expected, bins=bin_edges)[0] / len(expected)
    actual_hist = np.histogram(actual, bins=bin_edges)[0] / len(actual)

    # Avoid log(0) — add small epsilon
    expected_hist = np.clip(expected_hist, 1e-6, None)
    actual_hist = np.clip(actual_hist, 1e-6, None)

    psi = np.sum((actual_hist - expected_hist) * np.log(actual_hist / expected_hist))
    return round(float(psi), 4)


def set_reference_distribution(scores: list[float]):
    """Set the reference score distribution from training data."""
    global reference_distribution
    reference_distribution = np.array(scores)
    # Save to disk
    ref_file = MONITOR_DIR / "reference_distribution.json"
    ref_file.write_text(json.dumps(scores))
    print(f"Reference distribution set: {len(scores)} scores")


def load_reference_distribution():
    """Load reference distribution from disk."""
    global reference_distribution
    ref_file = MONITOR_DIR / "reference_distribution.json"
    if ref_file.exists():
        scores = json.loads(ref_file.read_text())
        reference_distribution = np.array(scores)
        print(f"Reference distribution loaded: {len(scores)} scores")


def get_drift_report() -> dict:
    """
    Generate a drift report comparing current predictions to reference distribution.
    """
    if reference_distribution is None:
        return {"status": "NO_REFERENCE", "message": "No reference distribution set. Run setup first."}

    if len(prediction_window) < 100:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": f"Need at least 100 predictions, have {len(prediction_window)}",
        }

    current_scores = np.array([p["score"] for p in prediction_window])

    psi = compute_psi(reference_distribution, current_scores)

    # Score distribution stats
    ref_mean = float(reference_distribution.mean())
    cur_mean = float(current_scores.mean())
    ref_std = float(reference_distribution.std())
    cur_std = float(current_scores.std())

    if psi > 0.25:
        status = "CRITICAL"
        message = "Significant drift detected. Model retraining recommended."
    elif psi > 0.1:
        status = "WARNING"
        message = "Moderate drift detected. Monitor closely."
    else:
        status = "STABLE"
        message = "No significant drift detected."

    return {
        "status": status,
        "message": message,
        "psi": psi,
        "psi_thresholds": {"stable": "< 0.1", "warning": "0.1 - 0.25", "critical": "> 0.25"},
        "reference": {"mean": round(ref_mean, 4), "std": round(ref_std, 4), "count": len(reference_distribution)},
        "current": {"mean": round(cur_mean, 4), "std": round(cur_std, 4), "count": len(current_scores)},
        "prediction_window_size": len(prediction_window),
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }


def get_prediction_stats() -> dict:
    """Get current prediction statistics."""
    if not prediction_window:
        return {"total": 0}

    scores = [p["score"] for p in prediction_window]
    decisions = {"ALLOW": 0, "REQUIRE_BIOMETRIC": 0, "BLOCK": 0}
    for s in scores:
        if s < THRESHOLD_FLAG:
            decisions["ALLOW"] += 1
        elif s < THRESHOLD_BLOCK:
            decisions["REQUIRE_BIOMETRIC"] += 1
        else:
            decisions["BLOCK"] += 1

    return {
        "total": len(scores),
        "mean_score": round(np.mean(scores), 4),
        "std_score": round(np.std(scores), 4),
        "min_score": round(min(scores), 4),
        "max_score": round(max(scores), 4),
        "decision_distribution": decisions,
        "fraud_rate_pct": round(decisions["BLOCK"] / len(scores) * 100, 2),
    }
