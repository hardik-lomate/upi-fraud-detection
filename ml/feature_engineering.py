import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder


def engineer_features(df):
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # --- Time features ---
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_night"] = df["hour"].apply(lambda h: 1 if h <= 5 else 0)
    df["is_weekend"] = df["day_of_week"].apply(lambda d: 1 if d >= 5 else 0)

    # --- Encode transaction type ---
    le = LabelEncoder()
    df["txn_type_encoded"] = le.fit_transform(df["transaction_type"])

    # --- Behavioral features (rolling window approximations) ---
    # Sender transaction counts (cumulative)
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

    # Unique receivers per sender (computed via loop for compatibility)
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


FEATURE_COLS = [
    "amount",
    "hour",
    "day_of_week",
    "is_night",
    "is_weekend",
    "txn_type_encoded",
    "sender_txn_count_24h",
    "sender_avg_amount",
    "sender_std_amount",
    "amount_deviation",
    "sender_unique_receivers_24h",
    "is_new_device",
    "is_new_receiver",
]


if __name__ == "__main__":
    df = pd.read_csv("ml/data/raw/transactions.csv")
    print(f"Loaded {len(df)} transactions")
    print("Engineering features... (this may take a few minutes)")

    df = engineer_features(df)

    df_out = df[FEATURE_COLS + ["is_fraud"]]
    df_out.to_csv("ml/data/processed/features.csv", index=False)
    print(f"Saved {len(df_out)} rows with {len(FEATURE_COLS)} features")
    print(df_out.describe())
