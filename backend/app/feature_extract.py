"""
Feature Extraction — Serving-time feature extraction (single transaction).
Imports all definitions from feature_contract.py (single source of truth).
"""

from datetime import datetime, timedelta
import sys
import os

# Add project root to path so we can import feature_contract
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import FEATURE_COLUMNS, TXN_TYPE_MAP, NIGHT_HOUR_CUTOFF, WEEKEND_DAY_CUTOFF

# In-memory store for behavioral features.
# On startup, this is hydrated from the DB (see main.py).
sender_history: dict = {}

WINDOW_24H = timedelta(hours=24)


def _get_or_create_history(sender: str) -> dict:
    if sender not in sender_history:
        sender_history[sender] = {
            "transactions": [],  # list of (timestamp, amount, device, receiver)
            "devices": set(),
            "receivers": set(),
        }
    return sender_history[sender]


def _filter_last_24h(transactions: list, now: datetime) -> list:
    cutoff = now - WINDOW_24H
    return [(ts, amt, dev, recv) for ts, amt, dev, recv in transactions if ts >= cutoff]


def extract_features(txn: dict) -> dict:
    """
    Extract features from a raw transaction dict.
    Returns a dict keyed by FEATURE_COLUMNS names — guarantees
    exact same feature names as training.
    """
    ts = datetime.fromisoformat(txn.get("timestamp", datetime.now().isoformat()))
    hour = ts.hour
    day_of_week = ts.weekday()
    is_night = 1 if hour <= NIGHT_HOUR_CUTOFF else 0
    is_weekend = 1 if day_of_week >= WEEKEND_DAY_CUTOFF else 0

    # Use same TXN_TYPE_MAP as training
    txn_type_encoded = TXN_TYPE_MAP.get(txn["transaction_type"], 0)

    sender = txn["sender_upi"]
    amount = txn["amount"]
    device = txn["sender_device_id"]
    receiver = txn["receiver_upi"]

    hist = _get_or_create_history(sender)

    # Filter to real 24h window
    recent_txns = _filter_last_24h(hist["transactions"], ts)

    sender_txn_count_24h = len(recent_txns)
    recent_amounts = [amt for _, amt, _, _ in recent_txns]

    if recent_amounts:
        sender_avg_amount = sum(recent_amounts) / len(recent_amounts)
        sender_std_amount = (
            (sum((a - sender_avg_amount) ** 2 for a in recent_amounts) / len(recent_amounts)) ** 0.5
            if len(recent_amounts) > 1
            else 0.0
        )
    else:
        sender_avg_amount = amount
        sender_std_amount = 0.0

    amount_deviation = (
        (amount - sender_avg_amount) / sender_std_amount
        if sender_std_amount > 0
        else 0.0
    )

    recent_receivers = {recv for _, _, _, recv in recent_txns}
    sender_unique_receivers_24h = len(recent_receivers)

    is_new_device = 0 if device in hist["devices"] else 1
    is_new_receiver = 0 if receiver in hist["receivers"] else 1

    # Update history
    hist["transactions"].append((ts, amount, device, receiver))
    hist["devices"].add(device)
    hist["receivers"].add(receiver)

    # Prune old transactions
    cutoff_7d = ts - timedelta(days=7)
    hist["transactions"] = [
        (t, a, d, r) for t, a, d, r in hist["transactions"] if t >= cutoff_7d
    ]

    # Build feature dict — keys MUST match FEATURE_COLUMNS exactly
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

    # Sanity check: every key in contract must be present
    missing = set(FEATURE_COLUMNS) - set(features.keys())
    if missing:
        raise ValueError(f"Feature contract violation! Missing features: {missing}")

    return features
