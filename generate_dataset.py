"""Generate a realistic fraud dataset for model training proof.

Run:
  python generate_dataset.py

Output:
  data/fraud_dataset.csv
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 42
DEFAULT_ROWS = 6000
DEFAULT_FRAUD_RATIO = 0.15
OUTPUT_PATH = Path("data/fraud_dataset.csv")

CITIES = [
    ("Mumbai", 19.0760, 72.8777),
    ("Delhi", 28.6139, 77.2090),
    ("Bengaluru", 12.9716, 77.5946),
    ("Chennai", 13.0827, 80.2707),
    ("Hyderabad", 17.3850, 78.4867),
    ("Pune", 18.5204, 73.8567),
    ("Kolkata", 22.5726, 88.3639),
    ("Ahmedabad", 23.0225, 72.5714),
]

FRAUD_PATTERNS = [
    "high_amount_new_device",
    "high_velocity",
    "unusual_time",
    "large_amount_deviation",
    "high_failed_attempts",
    "suspicious_graph_connections",
    "behavioral_anomaly_low_behavior_score",
]

TXN_TYPES = ["purchase", "transfer", "bill_payment", "recharge"]


def _clip01(v: float) -> float:
    return float(max(0.0, min(1.0, v)))


def _city_distance_score(city_a: str, city_b: str) -> float:
    if city_a == city_b:
        return 0.05
    return 0.85


def generate_dataset(
    rows: int = DEFAULT_ROWS,
    fraud_ratio: float = DEFAULT_FRAUD_RATIO,
    output_path: Path = OUTPUT_PATH,
    seed: int = SEED,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    rows = max(5000, int(rows))
    fraud_ratio = min(max(float(fraud_ratio), 0.10), 0.20)

    num_users = 1400
    num_merchants = 1800

    user_ids = [f"user_{i:05d}" for i in range(num_users)]
    merchant_ids = [f"merchant_{i:05d}@upi" for i in range(num_merchants)]

    merchant_risk_map = {
        merchant_ids[i]: float(rng.beta(2.0, 7.0))
        for i in range(num_merchants)
    }

    user_profiles = {}
    for user_id in user_ids:
        city_idx = int(rng.integers(0, len(CITIES)))
        city_name, lat, lon = CITIES[city_idx]
        avg_amount = float(rng.lognormal(mean=np.log(1400.0), sigma=0.55))
        std_amount = max(80.0, avg_amount * float(rng.uniform(0.22, 0.55)))
        account_age_days = int(rng.integers(45, 3650))
        base_velocity = float(rng.uniform(0.6, 3.2))
        primary_device = f"DEV_{user_id[-5:]}_A"

        user_profiles[user_id] = {
            "home_city": city_name,
            "home_lat": float(lat),
            "home_lon": float(lon),
            "avg_amount": avg_amount,
            "std_amount": std_amount,
            "account_age_days": account_age_days,
            "base_velocity": base_velocity,
            "primary_device": primary_device,
            "secondary_device": f"DEV_{user_id[-5:]}_B",
        }

    fraud_count = int(round(rows * fraud_ratio))
    labels = np.array([1] * fraud_count + [0] * (rows - fraud_count), dtype=int)
    rng.shuffle(labels)

    start = datetime(2026, 1, 1, 0, 0, 0)
    horizon_minutes = 120 * 24 * 60

    generated = []

    for idx in range(rows):
        label = int(labels[idx])
        user_id = user_ids[int(rng.integers(0, num_users))]
        profile = user_profiles[user_id]

        ts = start + timedelta(minutes=int(rng.integers(0, horizon_minutes)))
        merchant = merchant_ids[int(rng.integers(0, num_merchants))]
        sender_upi = f"{user_id}@okbank"
        receiver_upi = merchant

        avg_amount = float(profile["avg_amount"] * rng.uniform(0.90, 1.10))
        base_std = float(profile["std_amount"])

        pattern = "normal"
        if label == 1:
            pattern = str(rng.choice(FRAUD_PATTERNS))

        transaction_velocity = int(max(1, rng.poisson(profile["base_velocity"])))
        failed_attempts = int(max(0, rng.poisson(0.4)))
        is_new_device = int(rng.random() < 0.03)
        device_id = profile["secondary_device"] if is_new_device else profile["primary_device"]
        city_name = profile["home_city"]
        txn_type = str(rng.choice(TXN_TYPES, p=[0.45, 0.28, 0.17, 0.10]))

        amount = float(max(20.0, rng.normal(loc=avg_amount, scale=max(60.0, base_std * 0.75))))
        merchant_risk = float(merchant_risk_map[merchant])
        graph_risk = float(rng.beta(2.2, 7.2))

        if label == 1:
            if pattern == "high_amount_new_device":
                amount = float(avg_amount * rng.uniform(4.0, 10.0))
                is_new_device = 1
                device_id = f"DEV_ATTACK_{idx:06d}"
                failed_attempts += int(rng.integers(2, 6))
                merchant_risk = max(merchant_risk, float(rng.uniform(0.65, 0.95)))
                graph_risk = max(graph_risk, float(rng.uniform(0.55, 0.90)))
                txn_type = "transfer"
                receiver_upi = f"urgent.kyc.verify.{idx % 250}@upi"

            elif pattern == "high_velocity":
                transaction_velocity = int(rng.integers(14, 46))
                amount = float(avg_amount * rng.uniform(1.8, 4.8))
                failed_attempts += int(rng.integers(2, 7))
                merchant_risk = max(merchant_risk, float(rng.uniform(0.55, 0.85)))
                graph_risk = max(graph_risk, float(rng.uniform(0.55, 0.85)))
                txn_type = "transfer"

            elif pattern == "unusual_time":
                suspicious_hour = int(rng.choice([0, 1, 2, 3, 4, 23]))
                ts = ts.replace(hour=suspicious_hour, minute=int(rng.integers(0, 60)))
                amount = float(avg_amount * rng.uniform(2.3, 5.5))
                is_new_device = int(rng.random() < 0.7)
                if is_new_device:
                    device_id = f"DEV_NIGHT_{idx:06d}"
                merchant_risk = max(merchant_risk, float(rng.uniform(0.62, 0.92)))
                graph_risk = max(graph_risk, float(rng.uniform(0.50, 0.82)))
                txn_type = "transfer"
                receiver_upi = f"refund.support.helpdesk.{idx % 250}@upi"

            elif pattern == "large_amount_deviation":
                amount = float(avg_amount * rng.uniform(6.0, 14.0))
                failed_attempts += int(rng.integers(1, 4))
                merchant_risk = max(merchant_risk, float(rng.uniform(0.58, 0.88)))
                graph_risk = max(graph_risk, float(rng.uniform(0.45, 0.78)))
                txn_type = "transfer"

            elif pattern == "high_failed_attempts":
                failed_attempts += int(rng.integers(8, 20))
                amount = float(avg_amount * rng.uniform(1.8, 4.5))
                transaction_velocity = max(transaction_velocity, int(rng.integers(8, 26)))
                is_new_device = int(rng.random() < 0.55)
                if is_new_device:
                    device_id = f"DEV_FAIL_{idx:06d}"
                merchant_risk = max(merchant_risk, float(rng.uniform(0.55, 0.86)))
                graph_risk = max(graph_risk, float(rng.uniform(0.48, 0.80)))
                txn_type = "transfer"

            elif pattern == "suspicious_graph_connections":
                amount = float(avg_amount * rng.uniform(2.0, 6.8))
                graph_risk = max(graph_risk, float(rng.uniform(0.82, 0.99)))
                merchant_risk = max(merchant_risk, float(rng.uniform(0.66, 0.95)))
                transaction_velocity = max(transaction_velocity, int(rng.integers(6, 20)))
                txn_type = "transfer"
                receiver_upi = f"mule.collector.{idx % 40}@upi"

            elif pattern == "behavioral_anomaly_low_behavior_score":
                amount = float(avg_amount * rng.uniform(6.0, 14.0))
                transaction_velocity = max(transaction_velocity, int(rng.integers(12, 36)))
                failed_attempts += int(rng.integers(8, 20))
                is_new_device = 1
                device_id = f"DEV_BEHAV_{idx:06d}"
                merchant_risk = max(merchant_risk, float(rng.uniform(0.78, 0.96)))
                graph_risk = max(graph_risk, float(rng.uniform(0.72, 0.95)))
                suspicious_hour = int(rng.choice([0, 1, 2, 3, 4, 23]))
                ts = ts.replace(hour=suspicious_hour, minute=int(rng.integers(0, 60)))
                txn_type = "transfer"
                receiver_upi = f"behavior.anomaly.support.{idx % 180}@upi"

        if label == 0 and rng.random() < 0.92:
            hour = int(rng.integers(7, 22))
            ts = ts.replace(hour=hour, minute=int(rng.integers(0, 60)))

        city_name_now = city_name
        if label == 1 and (pattern in {"unusual_time", "suspicious_graph_connections"} or is_new_device == 1):
            city_name_now = CITIES[int(rng.integers(0, len(CITIES)))][0]

        hour_of_day = int(ts.hour)
        is_night = 1 if hour_of_day <= 5 else 0

        amount_deviation = float((amount - avg_amount) / max(base_std, 75.0))
        location_shift = _city_distance_score(profile["home_city"], city_name_now)

        behavior_score = _clip01(
            (0.30 * min(abs(amount_deviation) / 4.0, 1.0))
            + (0.25 * min(transaction_velocity / 20.0, 1.0))
            + (0.20 * is_new_device)
            + (0.15 * min(failed_attempts / 12.0, 1.0))
            + (0.10 * location_shift)
        )

        if label == 1 and pattern == "behavioral_anomaly_low_behavior_score":
            # For this pattern, behavior_score is a stability signal where lower means anomaly.
            behavior_score = float(rng.uniform(0.02, 0.15))

        generated.append(
            {
                "transaction_id": f"TXN_{ts.strftime('%Y%m%d')}_{idx:07d}",
                "user_id": user_id,
                "sender_upi": sender_upi,
                "receiver_upi": receiver_upi,
                "amount": round(amount, 2),
                "timestamp": ts.isoformat(),
                "device_id": device_id,
                "location": city_name_now,
                "is_new_device": int(is_new_device),
                "transaction_velocity": int(transaction_velocity),
                "avg_transaction_amount": round(avg_amount, 2),
                "amount_deviation": round(amount_deviation, 4),
                "hour_of_day": hour_of_day,
                "is_night": int(is_night),
                "failed_attempts_last_24h": int(failed_attempts),
                "account_age_days": int(profile["account_age_days"]),
                "merchant_risk_score": round(_clip01(merchant_risk), 4),
                "graph_risk_score": round(_clip01(graph_risk), 4),
                "behavior_score": round(_clip01(behavior_score), 4),
                "label": int(label),
                "transaction_type": txn_type,
                "fraud_pattern": pattern,
            }
        )

    df = pd.DataFrame(generated).sort_values("timestamp").reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    summary = {
        "rows": int(len(df)),
        "fraud_count": int(df["label"].sum()),
        "fraud_ratio": float(df["label"].mean()),
        "output": str(output_path),
        "pattern_distribution": df[df["label"] == 1]["fraud_pattern"].value_counts().to_dict(),
    }
    print(json.dumps(summary, indent=2))
    return df


def main() -> None:
    generate_dataset()


if __name__ == "__main__":
    main()
