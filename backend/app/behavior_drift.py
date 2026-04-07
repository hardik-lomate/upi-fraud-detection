"""User behavior drift detection against 30-day baseline."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from .database import SessionLocal, TransactionRecord


def _hour_hist(rows):
    hist = Counter()
    for r in rows:
        try:
            ts = datetime.fromisoformat(str(r.timestamp).replace("Z", "+00:00"))
        except Exception:
            ts = r.created_at or datetime.utcnow()
        hist[ts.hour] += 1
    total = max(sum(hist.values()), 1)
    return {h: hist.get(h, 0) / total for h in range(24)}


def _jensen_shannon(p: dict, q: dict) -> float:
    # Lightweight divergence approximation without scipy dependency.
    eps = 1e-9
    m = {k: 0.5 * (p.get(k, 0.0) + q.get(k, 0.0)) for k in set(p) | set(q)}

    def kl(a, b):
        s = 0.0
        for key in set(a) | set(b):
            av = max(a.get(key, 0.0), eps)
            bv = max(b.get(key, 0.0), eps)
            s += av * (av / bv)
        return s

    return min(1.0, 0.5 * kl(p, m) + 0.5 * kl(q, m))


def compute_user_behavior_drift(sender_upi: str) -> dict:
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        start_30d = now - timedelta(days=30)
        start_recent = now - timedelta(days=1)

        all_30d = (
            db.query(TransactionRecord)
            .filter(TransactionRecord.sender_upi == sender_upi)
            .filter(TransactionRecord.created_at >= start_30d)
            .all()
        )
        recent_1d = [r for r in all_30d if r.created_at and r.created_at >= start_recent]

        if not all_30d:
            return {
                "drift_score": 0.0,
                "drift_components": {
                    "avg_txn_amount_30d": 0.0,
                    "avg_txns_per_day_30d": 0.0,
                    "typical_hour_distribution": {},
                    "typical_receiver_set": [],
                    "typical_device_ids": [],
                },
                "is_anomalous": False,
            }

        avg_amt_30d = sum(float(r.amount or 0.0) for r in all_30d) / max(len(all_30d), 1)
        avg_amt_recent = sum(float(r.amount or 0.0) for r in recent_1d) / max(len(recent_1d), 1)
        amount_drift = min(1.0, abs(avg_amt_recent - avg_amt_30d) / max(avg_amt_30d, 1.0))

        avg_txns_day_30d = len(all_30d) / 30.0
        txns_recent_day = len(recent_1d)
        velocity_drift = min(1.0, abs(txns_recent_day - avg_txns_day_30d) / max(avg_txns_day_30d, 1.0))

        hour_30d = _hour_hist(all_30d)
        hour_recent = _hour_hist(recent_1d) if recent_1d else {h: 0.0 for h in range(24)}
        hour_drift = _jensen_shannon(hour_30d, hour_recent)

        receivers_30d = {str(r.receiver_upi or "").lower() for r in all_30d}
        receivers_recent = {str(r.receiver_upi or "").lower() for r in recent_1d}
        receiver_shift = 1.0 - (len(receivers_30d & receivers_recent) / max(len(receivers_recent), 1))

        devices_30d = {str(r.device_id or "") for r in all_30d}
        devices_recent = {str(r.device_id or "") for r in recent_1d}
        device_shift = 1.0 - (len(devices_30d & devices_recent) / max(len(devices_recent), 1))

        drift_score = (
            0.25 * amount_drift
            + 0.20 * velocity_drift
            + 0.20 * hour_drift
            + 0.20 * receiver_shift
            + 0.15 * device_shift
        )

        return {
            "drift_score": round(float(min(1.0, max(0.0, drift_score))), 4),
            "drift_components": {
                "avg_txn_amount_30d": round(float(avg_amt_30d), 2),
                "avg_txns_per_day_30d": round(float(avg_txns_day_30d), 2),
                "typical_hour_distribution": hour_30d,
                "typical_receiver_set": sorted(list(receivers_30d))[:100],
                "typical_device_ids": sorted(list(devices_30d))[:20],
                "amount_drift": round(float(amount_drift), 4),
                "velocity_drift": round(float(velocity_drift), 4),
                "hour_drift": round(float(hour_drift), 4),
                "receiver_shift": round(float(receiver_shift), 4),
                "device_shift": round(float(device_shift), 4),
            },
            "is_anomalous": drift_score >= 0.55,
        }
    finally:
        db.close()
