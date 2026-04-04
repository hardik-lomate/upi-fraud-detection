"""
Feature Extraction — Serving-time (single transaction).
Uses feature_contract.py for definitions and history_store.py for persistence.
"""

from datetime import datetime, timedelta
import sys, os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import TXN_TYPE_MAP, NIGHT_HOUR_CUTOFF, WEEKEND_DAY_CUTOFF
from .history_store import get_sender_history, save_sender_history
from .feature_columns import validate_feature_dict

logger = logging.getLogger(__name__)

WINDOW_1H = timedelta(hours=1)
WINDOW_24H = timedelta(hours=24)
WINDOW_7D = timedelta(days=7)


def _filter_window(transactions: list, now: datetime, window: timedelta) -> list:
    cutoff = now - window
    return [(ts, amt, dev, recv) for ts, amt, dev, recv in transactions if ts >= cutoff]


def extract_features(txn: dict) -> dict:
    """
    Extract features from a raw transaction dict.
    Returns a dict keyed by FEATURE_COLUMNS names.
    """
    try:
        ts = datetime.fromisoformat(txn.get("timestamp", datetime.now().isoformat()))
    except (TypeError, ValueError):
        ts = datetime.now()
    hour = ts.hour
    day_of_week = ts.weekday()
    is_night = 1 if hour <= NIGHT_HOUR_CUTOFF else 0
    is_weekend = 1 if day_of_week >= WEEKEND_DAY_CUTOFF else 0
    txn_type_encoded = TXN_TYPE_MAP.get(txn.get("transaction_type") or "purchase", 0)

    sender = txn.get("sender_upi")
    receiver = txn.get("receiver_upi")
    amount = float(txn.get("amount") or 0)
    device = txn.get("sender_device_id") or ""

    if not sender or not receiver:
        raise ValueError("sender_upi and receiver_upi are required")
    if amount <= 0:
        raise ValueError("amount must be > 0")

    hist = get_sender_history(sender)

    # Real time-windowed counts
    txns_24h = _filter_window(hist["transactions"], ts, WINDOW_24H)
    txns_1h = _filter_window(hist["transactions"], ts, WINDOW_1H)

    sender_txn_count_24h = len(txns_24h)
    amounts_24h = [amt for _, amt, _, _ in txns_24h]

    if amounts_24h:
        sender_avg_amount = sum(amounts_24h) / len(amounts_24h)
        n = len(amounts_24h)
        sender_std_amount = (
            (sum((a - sender_avg_amount) ** 2 for a in amounts_24h) / n) ** 0.5
            if n > 1 else 0.0
        )
    else:
        sender_avg_amount = amount
        sender_std_amount = 0.0

    amount_deviation = (
        (amount - sender_avg_amount) / sender_std_amount
        if sender_std_amount > 0 else 0.0
    )

    receivers_24h = {recv for _, _, _, recv in txns_24h}
    sender_unique_receivers_24h = len(receivers_24h)

    is_new_device = 0 if device in hist["devices"] else 1
    is_new_receiver = 0 if receiver in hist["receivers"] else 1

    # Update history
    hist["transactions"].append((ts, amount, device, receiver))
    hist["devices"].add(device)
    hist["receivers"].add(receiver)

    # Prune to 7 days
    cutoff_7d = ts - WINDOW_7D
    hist["transactions"] = [
        (t, a, d, r) for t, a, d, r in hist["transactions"] if t >= cutoff_7d
    ]

    # Persist to Redis/memory
    save_sender_history(sender, hist)

    # Build feature dict — must match FEATURE_COLUMNS exactly
    features = {
        "amount": amount,
        "hour": hour,
        "day_of_week": day_of_week,
        "is_night": is_night,
        "is_weekend": is_weekend,
        "txn_type_encoded": txn_type_encoded,
        "sender_txn_count_24h": sender_txn_count_24h,
        "sender_avg_amount": sender_avg_amount,
        "sender_std_amount": sender_std_amount,
        "amount_deviation": amount_deviation,
        "sender_unique_receivers_24h": sender_unique_receivers_24h,
        "is_new_device": is_new_device,
        "is_new_receiver": is_new_receiver,
    }

    missing = validate_feature_dict(features)
    if missing:
        raise ValueError(f"Feature contract violation! Missing: {missing}")

    # Expose 1h count for rules engine (not a model feature)
    features["_sender_txn_count_1h"] = len(txns_1h)

    return features
