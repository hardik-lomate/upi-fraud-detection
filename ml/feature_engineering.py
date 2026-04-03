"""
Feature Engineering — Training-time feature extraction.
Imports all definitions from feature_contract.py (single source of truth).
"""

import pandas as pd
import numpy as np
import sys
import os

# Add project root to path so we can import feature_contract
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from feature_contract import FEATURE_COLUMNS, TXN_TYPE_MAP, NIGHT_HOUR_CUTOFF, WEEKEND_DAY_CUTOFF


def engineer_features(df):
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # --- Time features (using contract constants) ---
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_night"] = df["hour"].apply(lambda h: 1 if h <= NIGHT_HOUR_CUTOFF else 0)
    df["is_weekend"] = df["day_of_week"].apply(lambda d: 1 if d >= WEEKEND_DAY_CUTOFF else 0)

    # --- Encode transaction type (using contract map, NOT LabelEncoder) ---
    df["txn_type_encoded"] = df["transaction_type"].map(TXN_TYPE_MAP).fillna(0).astype(int)

    # --- Behavioral features ---
    # Sender transaction counts (cumulative, approximates 24h in batch context)
    sender_counts = df.groupby("sender_upi").cumcount()
    df["sender_txn_count_24h"] = sender_counts

    # Sender average and std amount (expanding window)
    sender_stats = df.groupby("sender_upi")["amount"].expanding()
    df["sender_avg_amount"] = sender_stats.mean().reset_index(level=0, drop=True)
    df["sender_std_amount"] = sender_stats.std().reset_index(level=0, drop=True)
    df["sender_std_amount"] = df["sender_std_amount"].fillna(0)

    # Amount deviation
    df["amount_deviation"] = np.where(
        df["sender_std_amount"] > 0,
        (df["amount"] - df["sender_avg_amount"]) / df["sender_std_amount"],
        0,
    )

    # Unique receivers per sender
    sender_unique_recv = {}
    unique_recv_counts = []
    for _, row in df.iterrows():
        sender = row["sender_upi"]
        receiver = row["receiver_upi"]
        if sender not in sender_unique_recv:
            sender_unique_recv[sender] = set()
        sender_unique_recv[sender].add(receiver)
        unique_recv_counts.append(len(sender_unique_recv[sender]))
    df["sender_unique_receivers_24h"] = unique_recv_counts

    # New device detection
    sender_devices = {}
    is_new_device = []
    for _, row in df.iterrows():
        sender = row["sender_upi"]
        device = row["sender_device_id"]
        if sender not in sender_devices:
            sender_devices[sender] = set()
            is_new_device.append(1)
        elif device not in sender_devices[sender]:
            is_new_device.append(1)
        else:
            is_new_device.append(0)
        sender_devices[sender].add(device)
    df["is_new_device"] = is_new_device

    # New receiver detection
    sender_receivers = {}
    is_new_receiver = []
    for _, row in df.iterrows():
        sender = row["sender_upi"]
        receiver = row["receiver_upi"]
        if sender not in sender_receivers:
            sender_receivers[sender] = set()
            is_new_receiver.append(1)
        elif receiver not in sender_receivers[sender]:
            is_new_receiver.append(1)
        else:
            is_new_receiver.append(0)
        sender_receivers[sender].add(receiver)
    df["is_new_receiver"] = is_new_receiver

    return df


if __name__ == "__main__":
    df = pd.read_csv("ml/data/raw/transactions.csv")
    print(f"Loaded {len(df)} transactions")
    print("Engineering features...")

    df = engineer_features(df)

    # Use FEATURE_COLUMNS from contract — guarantees consistency
    df_out = df[FEATURE_COLUMNS + ["is_fraud"]]
    df_out.to_csv("ml/data/processed/features.csv", index=False)
    print(f"Saved {len(df_out)} rows with {len(FEATURE_COLUMNS)} features")
    print(f"Feature order: {FEATURE_COLUMNS}")
    print(df_out.describe())
