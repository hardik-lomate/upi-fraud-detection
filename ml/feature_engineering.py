"""
Feature Engineering — Training-time feature extraction.
Imports all definitions from feature_contract.py (single source of truth).
"""

from collections import defaultdict, deque
from datetime import timedelta
import pandas as pd
import numpy as np
import sys
import os

# Add project root to path so we can import feature_contract
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from feature_contract import FEATURE_COLUMNS, TXN_TYPE_MAP, NIGHT_HOUR_CUTOFF, WEEKEND_DAY_CUTOFF


WINDOW_1M = timedelta(minutes=1)
WINDOW_5M = timedelta(minutes=5)
WINDOW_1H = timedelta(hours=1)
WINDOW_24H = timedelta(hours=24)
WINDOW_7D = timedelta(days=7)
HIGH_RISK_HOURS = {0, 1, 2, 3, 4, 22, 23}

KNOWN_SAFE_SUFFIX_RISK = {
    "ybl": 0.10,
    "oksbi": 0.10,
    "paytm": 0.20,
    "okicici": 0.15,
    "okaxis": 0.15,
    "okhdfcbank": 0.15,
    "upi": 0.30,
}
SUSPICIOUS_VPA_TERMS = ("bank", "helpline", "support", "care", "refund", "reward", "prize")


def _safe_float(v, default=0.0):
    try:
        n = float(v)
        if np.isnan(n):
            return default
        return n
    except Exception:
        return default


def _suffix(upi_id: str) -> str:
    if not upi_id or "@" not in upi_id:
        return ""
    return upi_id.split("@", 1)[1].strip().lower()


def _local_part(upi_id: str) -> str:
    if not upi_id or "@" not in upi_id:
        return ""
    return upi_id.split("@", 1)[0].strip().lower()


def _vpa_suffix_risk_score(receiver_upi: str) -> float:
    local = _local_part(receiver_upi)
    suffix = _suffix(receiver_upi)

    score = KNOWN_SAFE_SUFFIX_RISK.get(suffix, 0.80)
    if any(term in local for term in SUSPICIOUS_VPA_TERMS):
        score = max(score, 1.0)
    if local.isdigit() and len(local) >= 6:
        score = max(score, 0.95)
    if len(local) > 30:
        score = max(score, 0.90)
    if local and local[-6:].isdigit():
        score = max(score, 0.85)

    return float(min(1.0, max(0.0, score)))


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = np.radians(lat1)
    p2 = np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlon / 2.0) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return float(r * c)


def _prune_window(dq: deque, cutoff_ts, ts_getter):
    while dq and ts_getter(dq[0]) < cutoff_ts:
        dq.popleft()


def engineer_features(df):
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Ensure optional columns exist for robust feature extraction across datasets.
    if "sender_device_id" not in df.columns:
        df["sender_device_id"] = "UNKNOWN_DEVICE"
    if "sender_location_lat" not in df.columns:
        df["sender_location_lat"] = np.nan
    if "sender_location_lon" not in df.columns:
        df["sender_location_lon"] = np.nan
    if "decision" not in df.columns:
        df["decision"] = ""

    # --- Time features (using contract constants) ---
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_night"] = df["hour"].apply(lambda h: 1 if h <= NIGHT_HOUR_CUTOFF else 0)
    df["is_weekend"] = df["day_of_week"].apply(lambda d: 1 if d >= WEEKEND_DAY_CUTOFF else 0)
    df["is_high_risk_hour"] = df["hour"].apply(lambda h: 1 if h in HIGH_RISK_HOURS else 0)

    # --- Encode transaction type (using contract map, NOT LabelEncoder) ---
    df["txn_type_encoded"] = df["transaction_type"].map(TXN_TYPE_MAP).fillna(0).astype(int)

    # --- Stateful feature extraction over rolling windows ---
    sender_24h = defaultdict(deque)   # (ts, amount, device, receiver)
    sender_1h = defaultdict(deque)    # (ts, amount)
    sender_1m = defaultdict(deque)    # ts
    sender_5m = defaultdict(deque)    # ts
    sender_7d = defaultdict(deque)    # (ts, amount, receiver)

    sender_seen_devices = defaultdict(set)
    sender_seen_receivers = defaultdict(set)
    sender_all_amounts = defaultdict(list)
    sender_recent_fraud = defaultdict(lambda: deque(maxlen=5))
    sender_last_location = {}

    receiver_seen_count = defaultdict(int)
    receiver_24h = defaultdict(deque)  # (ts, sender)
    receiver_first_seen = {}
    receiver_flagged_count = defaultdict(int)

    out_sender_txn_count_24h = []
    out_sender_txn_count_1h = []
    out_sender_txn_count_1min = []
    out_sender_avg_amount = []
    out_sender_std_amount = []
    out_sender_max_amount_7d = []
    out_amount_deviation = []
    out_amount_to_avg_ratio = []
    out_amount_percentile_sender = []
    out_sender_unique_receivers_24h = []
    out_sender_unique_receivers_7d = []
    out_is_new_device = []
    out_is_new_receiver = []
    out_receiver_seen_count = []
    out_receiver_new_sender_ratio_24h = []
    out_sender_velocity_1min = []
    out_sender_velocity_5min = []
    out_geo_distance_km = []
    out_is_impossible_travel = []
    out_vpa_suffix_risk_score = []
    out_upi_age_days = []
    out_cross_bank_flag = []
    out_txn_amount_rank_7d = []
    out_sender_fraud_score_history = []
    out_receiver_fraud_flag_count = []

    for _, row in df.iterrows():
        ts = row["timestamp"]
        sender = str(row.get("sender_upi") or "").strip().lower()
        receiver = str(row.get("receiver_upi") or "").strip().lower()
        amount = _safe_float(row.get("amount"), 0.0)
        device = str(row.get("sender_device_id") or "")
        lat = _safe_float(row.get("sender_location_lat"), np.nan)
        lon = _safe_float(row.get("sender_location_lon"), np.nan)

        # Prune sender windows
        _prune_window(sender_24h[sender], ts - WINDOW_24H, lambda x: x[0])
        _prune_window(sender_1h[sender], ts - WINDOW_1H, lambda x: x[0])
        _prune_window(sender_1m[sender], ts - WINDOW_1M, lambda x: x)
        _prune_window(sender_5m[sender], ts - WINDOW_5M, lambda x: x)
        _prune_window(sender_7d[sender], ts - WINDOW_7D, lambda x: x[0])

        # Prune receiver windows
        _prune_window(receiver_24h[receiver], ts - WINDOW_24H, lambda x: x[0])

        tx24 = sender_24h[sender]
        tx7d = sender_7d[sender]
        tx1h = sender_1h[sender]
        tx1m = sender_1m[sender]
        tx5m = sender_5m[sender]

        sender_txn_count_24h = len(tx24)
        sender_txn_count_1h = len(tx1h)
        sender_txn_count_1min = len(tx1m)
        sender_velocity_1min = sender_txn_count_1min
        sender_velocity_5min = len(tx5m)

        amounts_24h = [a for _, a, _, _ in tx24]
        if amounts_24h:
            sender_avg_amount = float(np.mean(amounts_24h))
            sender_std_amount = float(np.std(amounts_24h))
        else:
            sender_avg_amount = amount
            sender_std_amount = 0.0

        amounts_7d = [a for _, a, _ in tx7d]
        sender_max_amount_7d = max(amounts_7d) if amounts_7d else amount
        amount_deviation = (
            (amount - sender_avg_amount) / sender_std_amount
            if sender_std_amount > 0 else 0.0
        )
        amount_to_avg_ratio = amount / max(sender_avg_amount, 1.0)

        sender_amount_hist = sender_all_amounts[sender]
        if sender_amount_hist:
            amount_percentile_sender = (sum(1 for a in sender_amount_hist if a <= amount) + 1) / (len(sender_amount_hist) + 1)
        else:
            amount_percentile_sender = 1.0

        sender_unique_receivers_24h = len({r for _, _, _, r in tx24})
        sender_unique_receivers_7d = len({r for _, _, r in tx7d})

        is_new_device = 0 if device in sender_seen_devices[sender] else 1
        is_new_receiver = 0 if receiver in sender_seen_receivers[sender] else 1

        rx_seen_count = receiver_seen_count[receiver]
        rx_24h_senders = [s for _, s in receiver_24h[receiver]]
        if rx_24h_senders:
            receiver_new_sender_ratio_24h = len(set(rx_24h_senders)) / len(rx_24h_senders)
        else:
            receiver_new_sender_ratio_24h = 1.0

        # Geo-distance and impossible travel from previous known sender location.
        geo_distance_km = 0.0
        is_impossible_travel = 0
        if np.isfinite(lat) and np.isfinite(lon) and sender in sender_last_location:
            prev_lat, prev_lon, prev_ts = sender_last_location[sender]
            geo_distance_km = _haversine_km(prev_lat, prev_lon, lat, lon)
            minutes = max((ts - prev_ts).total_seconds() / 60.0, 0.0)
            if geo_distance_km > 500 and minutes < 30:
                is_impossible_travel = 1

        vpa_suffix_risk_score = _vpa_suffix_risk_score(receiver)

        first_seen = receiver_first_seen.get(receiver)
        if first_seen is None:
            upi_age_days = -1
        else:
            upi_age_days = int((ts - first_seen).total_seconds() // 86400)

        sender_suffix = _suffix(sender)
        receiver_suffix = _suffix(receiver)
        cross_bank_flag = 1 if sender_suffix and receiver_suffix and sender_suffix != receiver_suffix else 0

        if amounts_7d:
            txn_amount_rank_7d = sum(1 for a in amounts_7d if a < amount) / max(len(amounts_7d), 1)
        else:
            txn_amount_rank_7d = 1.0

        sender_fraud_hist = sender_recent_fraud[sender]
        sender_fraud_score_history = float(np.mean(sender_fraud_hist)) if sender_fraud_hist else 0.0
        receiver_fraud_flag_count = receiver_flagged_count[receiver]

        out_sender_txn_count_24h.append(sender_txn_count_24h)
        out_sender_txn_count_1h.append(sender_txn_count_1h)
        out_sender_txn_count_1min.append(sender_txn_count_1min)
        out_sender_avg_amount.append(sender_avg_amount)
        out_sender_std_amount.append(sender_std_amount)
        out_sender_max_amount_7d.append(sender_max_amount_7d)
        out_amount_deviation.append(amount_deviation)
        out_amount_to_avg_ratio.append(amount_to_avg_ratio)
        out_amount_percentile_sender.append(amount_percentile_sender)
        out_sender_unique_receivers_24h.append(sender_unique_receivers_24h)
        out_sender_unique_receivers_7d.append(sender_unique_receivers_7d)
        out_is_new_device.append(is_new_device)
        out_is_new_receiver.append(is_new_receiver)
        out_receiver_seen_count.append(rx_seen_count)
        out_receiver_new_sender_ratio_24h.append(receiver_new_sender_ratio_24h)
        out_sender_velocity_1min.append(sender_velocity_1min)
        out_sender_velocity_5min.append(sender_velocity_5min)
        out_geo_distance_km.append(geo_distance_km)
        out_is_impossible_travel.append(is_impossible_travel)
        out_vpa_suffix_risk_score.append(vpa_suffix_risk_score)
        out_upi_age_days.append(upi_age_days)
        out_cross_bank_flag.append(cross_bank_flag)
        out_txn_amount_rank_7d.append(txn_amount_rank_7d)
        out_sender_fraud_score_history.append(sender_fraud_score_history)
        out_receiver_fraud_flag_count.append(receiver_fraud_flag_count)

        # Update state after feature calculation.
        sender_24h[sender].append((ts, amount, device, receiver))
        sender_1h[sender].append((ts, amount))
        sender_1m[sender].append(ts)
        sender_5m[sender].append(ts)
        sender_7d[sender].append((ts, amount, receiver))

        sender_seen_devices[sender].add(device)
        sender_seen_receivers[sender].add(receiver)
        sender_all_amounts[sender].append(amount)

        if np.isfinite(lat) and np.isfinite(lon):
            sender_last_location[sender] = (lat, lon, ts)

        receiver_seen_count[receiver] += 1
        receiver_24h[receiver].append((ts, sender))
        if receiver not in receiver_first_seen:
            receiver_first_seen[receiver] = ts

        if "fraud_score" in df.columns and pd.notna(row.get("fraud_score")):
            current_fraud_score = _safe_float(row.get("fraud_score"), 0.0)
        elif "is_fraud" in df.columns:
            current_fraud_score = _safe_float(row.get("is_fraud"), 0.0)
        else:
            current_fraud_score = 0.0
        sender_recent_fraud[sender].append(current_fraud_score)

        decision = str(row.get("decision") or "").upper()
        is_flagged_outcome = decision in {"BLOCK", "VERIFY"} or current_fraud_score >= 0.5
        if is_flagged_outcome:
            receiver_flagged_count[receiver] += 1

    df["sender_txn_count_24h"] = out_sender_txn_count_24h
    df["sender_txn_count_1h"] = out_sender_txn_count_1h
    df["sender_txn_count_1min"] = out_sender_txn_count_1min
    df["sender_avg_amount"] = out_sender_avg_amount
    df["sender_std_amount"] = out_sender_std_amount
    df["sender_max_amount_7d"] = out_sender_max_amount_7d
    df["amount_deviation"] = out_amount_deviation
    df["amount_to_avg_ratio"] = out_amount_to_avg_ratio
    df["amount_percentile_sender"] = out_amount_percentile_sender
    df["sender_unique_receivers_24h"] = out_sender_unique_receivers_24h
    df["sender_unique_receivers_7d"] = out_sender_unique_receivers_7d
    df["is_new_device"] = out_is_new_device
    df["is_new_receiver"] = out_is_new_receiver
    df["receiver_seen_count"] = out_receiver_seen_count
    df["receiver_new_sender_ratio_24h"] = out_receiver_new_sender_ratio_24h
    df["sender_velocity_1min"] = out_sender_velocity_1min
    df["sender_velocity_5min"] = out_sender_velocity_5min
    df["geo_distance_km"] = out_geo_distance_km
    df["is_impossible_travel"] = out_is_impossible_travel
    df["vpa_suffix_risk_score"] = out_vpa_suffix_risk_score
    df["upi_age_days"] = out_upi_age_days
    df["cross_bank_flag"] = out_cross_bank_flag
    df["txn_amount_rank_7d"] = out_txn_amount_rank_7d
    df["sender_fraud_score_history"] = out_sender_fraud_score_history
    df["receiver_fraud_flag_count"] = out_receiver_fraud_flag_count

    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0

    return df


if __name__ == "__main__":
    df = pd.read_csv("ml/data/raw/transactions.csv")
    print(f"Loaded {len(df)} transactions")
    print("Engineering features...")

    df = engineer_features(df)

    # Use FEATURE_COLUMNS from contract — guarantees consistency
    output_cols = list(FEATURE_COLUMNS)
    if "is_fraud" in df.columns:
        output_cols.append("is_fraud")
    df_out = df[output_cols]
    df_out.to_csv("ml/data/processed/features.csv", index=False)
    print(f"Saved {len(df_out)} rows with {len(FEATURE_COLUMNS)} features")
    print(f"Feature order: {FEATURE_COLUMNS}")
    print(df_out.describe())
