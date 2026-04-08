"""
Feature Extraction — Serving-time (single transaction).
Uses feature_contract.py for definitions and history_store.py for persistence.
"""

from datetime import datetime, timedelta
import sys, os
import logging
import math

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import TXN_TYPE_MAP, NIGHT_HOUR_CUTOFF, WEEKEND_DAY_CUTOFF, FEATURE_COLUMNS
from .history_store import get_sender_history, save_sender_history
from .database import (
    count_recent_sender_transactions,
    count_receiver_transactions,
    get_receiver_sender_stats_24h,
    get_receiver_upi_age_days,
    get_sender_last_n_fraud_score_avg,
    count_receiver_flagged_transactions,
)
from .geo_risk import calculate_travel_impossibility
from .upi_pattern import detect_scam_vpa_pattern, analyze_upi_id
from .feature_columns import validate_feature_dict

logger = logging.getLogger(__name__)

WINDOW_1H = timedelta(hours=1)
WINDOW_24H = timedelta(hours=24)
WINDOW_7D = timedelta(days=7)
WINDOW_COOLDOWN = timedelta(minutes=30)
HIGH_RISK_HOURS = {0, 1, 2, 3, 4, 22, 23}


def _safe_suffix(upi_id: str) -> str:
    if not upi_id or "@" not in upi_id:
        return ""
    return upi_id.split("@", 1)[1].strip().lower()


def _is_valid_geo(lat, lon) -> bool:
    return (
        lat is not None and lon is not None and
        isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and
        math.isfinite(lat) and math.isfinite(lon)
    )


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

    sender = str(txn.get("sender_upi") or "").strip().lower()
    receiver = str(txn.get("receiver_upi") or "").strip().lower()
    amount = float(txn.get("amount") or 0)
    device = txn.get("sender_device_id") or ""
    sender_lat = txn.get("sender_location_lat")
    sender_lon = txn.get("sender_location_lon")

    if not sender or not receiver:
        raise ValueError("sender_upi and receiver_upi are required")
    if amount <= 0:
        raise ValueError("amount must be > 0")

    hist = get_sender_history(sender)

    # Real-time velocity from DB arrival times for robust anti-bot windows.
    try:
        sender_txn_count_1min = int(count_recent_sender_transactions(sender, seconds=60) or 0) + 1
        sender_txn_count_5min = int(count_recent_sender_transactions(sender, seconds=300) or 0) + 1
    except Exception:
        sender_txn_count_1min = 1
        sender_txn_count_5min = 1

    # Cooldown: after a successful verification, temporarily reduce strictness.
    cooldown_active = 0
    last_verified = hist.get("last_verified_at")
    if last_verified:
        try:
            last_verified_dt = datetime.fromisoformat(str(last_verified).replace("Z", "+00:00"))
            if ts - last_verified_dt <= WINDOW_COOLDOWN:
                cooldown_active = 1
        except Exception:
            cooldown_active = 0

    # Real time-windowed counts
    txns_24h = _filter_window(hist["transactions"], ts, WINDOW_24H)
    txns_1h = _filter_window(hist["transactions"], ts, WINDOW_1H)
    txns_7d = _filter_window(hist["transactions"], ts, WINDOW_7D)

    sender_txn_count_24h = len(txns_24h)
    sender_txn_count_1h = len(txns_1h)
    amounts_24h = [amt for _, amt, _, _ in txns_24h]
    amounts_7d = [amt for _, amt, _, _ in txns_7d]
    sender_total_amount_24h = float(sum(amounts_24h)) if amounts_24h else 0.0

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
    amount_to_avg_ratio = amount / max(sender_avg_amount, 1.0)
    sender_max_amount_7d = max(amounts_7d) if amounts_7d else amount

    receivers_24h = {recv for _, _, _, recv in txns_24h}
    sender_unique_receivers_24h = len(receivers_24h)
    receivers_7d = {recv for _, _, _, recv in txns_7d}
    sender_unique_receivers_7d = len(receivers_7d)

    is_new_device = 0 if device in hist["devices"] else 1
    is_new_receiver = 0 if receiver in hist["receivers"] else 1

    all_sender_amounts = [amt for _, amt, _, _ in hist["transactions"]]
    if all_sender_amounts:
        amount_percentile_sender = (
            (sum(1 for x in all_sender_amounts if x <= amount) + 1)
            / (len(all_sender_amounts) + 1)
        )
    else:
        amount_percentile_sender = 1.0

    if amounts_7d:
        txn_amount_rank_7d = sum(1 for x in amounts_7d if x < amount) / max(len(amounts_7d), 1)
    else:
        txn_amount_rank_7d = 1.0

    # Receiver-level features from DB-backed history.
    try:
        receiver_seen_count = int(count_receiver_transactions(receiver) or 0)
    except Exception:
        receiver_seen_count = 0

    try:
        receiver_stats_24h = get_receiver_sender_stats_24h(receiver)
        receiver_new_sender_ratio_24h = float(receiver_stats_24h.get("new_sender_ratio", 0.0))
    except Exception:
        receiver_new_sender_ratio_24h = 0.0

    try:
        upi_age_days = int(get_receiver_upi_age_days(receiver))
    except Exception:
        upi_age_days = -1

    try:
        sender_fraud_score_history = float(get_sender_last_n_fraud_score_avg(sender, n=5))
    except Exception:
        sender_fraud_score_history = 0.0

    try:
        receiver_fraud_flag_count = int(count_receiver_flagged_transactions(receiver) or 0)
    except Exception:
        receiver_fraud_flag_count = 0

    sender_suffix = _safe_suffix(sender)
    receiver_suffix = _safe_suffix(receiver)
    cross_bank_flag = 1 if sender_suffix and receiver_suffix and sender_suffix != receiver_suffix else 0
    is_high_risk_hour = 1 if hour in HIGH_RISK_HOURS else 0

    # Geo features + impossible travel.
    geo_distance_km = 0.0
    is_impossible_travel = 0
    time_since_last_txn_minutes = -1.0
    last_loc = hist.get("last_location")
    last_ts = hist.get("last_timestamp")
    if _is_valid_geo(sender_lat, sender_lon) and isinstance(last_loc, dict) and last_ts:
        try:
            geo_result = calculate_travel_impossibility(
                float(last_loc.get("lat")),
                float(last_loc.get("lon")),
                str(last_ts),
                float(sender_lat),
                float(sender_lon),
                ts.isoformat(),
            )
            geo_distance_km = float(geo_result.get("distance_km", 0.0))
            is_impossible_travel = 1 if geo_result.get("is_impossible") else 0
            time_since_last_txn_minutes = float(geo_result.get("time_diff_minutes", -1.0))
        except Exception:
            pass

    # VPA risk score.
    try:
        vpa_scan = detect_scam_vpa_pattern(receiver)
        vpa_suffix_risk_score = float(vpa_scan.get("risk_score", 0.0))
    except Exception:
        vpa_suffix_risk_score = float(analyze_upi_id(receiver).get("risk_score", 0.0))

    sender_velocity_1min = sender_txn_count_1min
    sender_velocity_5min = sender_txn_count_5min

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
        "sender_txn_count_1h": sender_txn_count_1h,
        "sender_txn_count_1min": sender_txn_count_1min,
        "sender_avg_amount": sender_avg_amount,
        "sender_std_amount": sender_std_amount,
        "sender_max_amount_7d": sender_max_amount_7d,
        "amount_deviation": amount_deviation,
        "amount_to_avg_ratio": amount_to_avg_ratio,
        "amount_percentile_sender": amount_percentile_sender,
        "sender_unique_receivers_24h": sender_unique_receivers_24h,
        "sender_unique_receivers_7d": sender_unique_receivers_7d,
        "is_new_device": is_new_device,
        "is_new_receiver": is_new_receiver,
        "receiver_seen_count": receiver_seen_count,
        "receiver_new_sender_ratio_24h": receiver_new_sender_ratio_24h,
        "sender_velocity_1min": sender_velocity_1min,
        "sender_velocity_5min": sender_velocity_5min,
        "geo_distance_km": geo_distance_km,
        "is_impossible_travel": is_impossible_travel,
        "vpa_suffix_risk_score": vpa_suffix_risk_score,
        "upi_age_days": upi_age_days,
        "cross_bank_flag": cross_bank_flag,
        "is_high_risk_hour": is_high_risk_hour,
        "txn_amount_rank_7d": txn_amount_rank_7d,
        "sender_fraud_score_history": sender_fraud_score_history,
        "receiver_fraud_flag_count": receiver_fraud_flag_count,
    }

    for col in FEATURE_COLUMNS:
        features.setdefault(col, 0.0)

    missing = validate_feature_dict(features)
    if missing:
        raise ValueError(f"Feature contract violation! Missing: {missing}")

    # Expose helper fields for rules and UI.
    features["_sender_txn_count_1h"] = sender_txn_count_1h
    features["_sender_txn_count_60s"] = sender_txn_count_1min
    features["_sender_txn_count_1min"] = sender_txn_count_1min
    features["_sender_txn_count_5min"] = sender_txn_count_5min
    features["_sender_total_amount_24h"] = sender_total_amount_24h
    features["_cooldown_active"] = cooldown_active
    features["_transaction_type"] = txn.get("transaction_type") or "purchase"
    features["_time_since_last_txn_minutes"] = time_since_last_txn_minutes

    return features
