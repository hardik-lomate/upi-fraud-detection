"""
Online Learning Model — River HalfSpaceTrees.

Continuously updates from confirmed fraud feedback without full retraining.
Runs alongside the ensemble as a recency signal. Gracefully degrades if
the `river` package is not installed.
"""

import logging
import time

logger = logging.getLogger(__name__)

_online_model = None
_model_stats = {
    "samples_learned": 0,
    "last_update_at": None,
    "created_at": None,
    "is_available": False,
}

try:
    from river import anomaly

    def _create_model():
        return anomaly.HalfSpaceTrees(
            n_trees=25,
            height=8,
            window_size=250,
            seed=42,
        )

    _online_model = _create_model()
    _model_stats["is_available"] = True
    _model_stats["created_at"] = time.time()
    logger.info("[OnlineModel] River HalfSpaceTrees initialized (25 trees, window=250)")

except ImportError:
    logger.warning("[OnlineModel] `river` package not installed — online learning disabled")


def score_one(features: dict) -> float:
    """Score a single transaction. Returns anomaly score 0.0-1.0 (higher = more anomalous).

    Returns 0.0 if River is not available.
    """
    if _online_model is None:
        return 0.0

    try:
        # River anomaly detectors return a score where higher = more anomalous
        raw_score = _online_model.score_one(features)
        return min(max(float(raw_score), 0.0), 1.0)
    except Exception as e:
        logger.warning(f"[OnlineModel] score_one failed: {e}")
        return 0.0


def learn_one(features: dict, is_fraud: bool = True):
    """Update the online model with a confirmed sample.

    Called when analyst feedback is submitted via /feedback endpoint.
    """
    if _online_model is None:
        return

    try:
        _online_model.learn_one(features)
        _model_stats["samples_learned"] += 1
        _model_stats["last_update_at"] = time.time()
        logger.info(
            f"[OnlineModel] Learned sample (fraud={is_fraud}), "
            f"total_samples={_model_stats['samples_learned']}"
        )
    except Exception as e:
        logger.warning(f"[OnlineModel] learn_one failed: {e}")


def get_online_model_stats() -> dict:
    """Return online model status for the monitoring dashboard."""
    stats = dict(_model_stats)

    if stats["last_update_at"]:
        hours_since = (time.time() - stats["last_update_at"]) / 3600
        stats["hours_since_last_update"] = round(hours_since, 2)
    else:
        stats["hours_since_last_update"] = None

    return stats


def reset_model():
    """Reset the online model (for testing or after major drift)."""
    global _online_model
    if _model_stats["is_available"]:
        _online_model = _create_model()
        _model_stats["samples_learned"] = 0
        _model_stats["last_update_at"] = None
        _model_stats["created_at"] = time.time()
        logger.info("[OnlineModel] Model reset")
