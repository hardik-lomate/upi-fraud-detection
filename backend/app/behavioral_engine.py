"""Behavioral risk engine.

Computes behavior anomaly score using:
- Historical drift from recent sender behavior
- Pattern-based anomalies in sender transaction history
- Contextual sender feature deviations
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .behavior_drift import compute_user_behavior_drift
from .history_store import get_sender_history
from .pattern_detector import detect_fraud_patterns


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _to_txn_rows(sender_upi: str, history: dict) -> list[dict]:
    rows: list[dict] = []
    for item in history.get("transactions", []):
        try:
            ts, amt, dev, recv = item
            rows.append(
                {
                    "sender_upi": sender_upi,
                    "receiver_upi": str(recv or ""),
                    "amount": float(amt or 0.0),
                    "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                    "sender_device_id": str(dev or ""),
                }
            )
        except Exception:
            continue
    return rows


def analyze_behavioral_risk(sender_upi: str, features: dict, current_txn: dict) -> dict[str, Any]:
    """Return behavior score and explainable factors."""
    sender = str(sender_upi or "").strip().lower()
    drift_payload = compute_user_behavior_drift(sender) if sender else {"drift_score": 0.0}
    drift_score = _clamp01(float(drift_payload.get("drift_score", 0.0) or 0.0))

    history = get_sender_history(sender) if sender else {}
    rows = _to_txn_rows(sender, history)
    rows.append(
        {
            "sender_upi": sender,
            "receiver_upi": str(current_txn.get("receiver_upi") or ""),
            "amount": float(current_txn.get("amount") or 0.0),
            "timestamp": str(current_txn.get("timestamp") or datetime.utcnow().isoformat()),
            "sender_device_id": str(current_txn.get("sender_device_id") or ""),
        }
    )
    pattern_hits = detect_fraud_patterns(rows[-50:]) if rows else []
    pattern_score = _clamp01(len(pattern_hits) / 3.0)

    amount_deviation = abs(float(features.get("amount_deviation", 0.0) or 0.0))
    velocity_1m = float(features.get("sender_txn_count_1min", 0.0) or features.get("_sender_txn_count_60s", 0.0) or 0.0)
    new_device = int(features.get("is_new_device", 0) or 0)

    context_score = _clamp01(
        (0.45 * _clamp01(amount_deviation / 3.0))
        + (0.35 * _clamp01(velocity_1m / 8.0))
        + (0.20 * _clamp01(new_device))
    )

    behavior_score = _clamp01((0.50 * drift_score) + (0.30 * pattern_score) + (0.20 * context_score))

    reasons: list[str] = []
    if drift_score >= 0.55:
        reasons.append("User behavior drift is unusually high")
    if pattern_hits:
        reasons.append(f"Pattern detector matched {len(pattern_hits)} suspicious sequence(s)")
    if context_score >= 0.5 and not reasons:
        reasons.append("Current transaction deviates from sender baseline")
    if not reasons:
        reasons.append("Behavior pattern appears consistent")

    return {
        "behavior_score": round(behavior_score, 4),
        "drift_score": round(drift_score, 4),
        "pattern_score": round(pattern_score, 4),
        "context_score": round(context_score, 4),
        "patterns": pattern_hits,
        "reasons": reasons,
    }
