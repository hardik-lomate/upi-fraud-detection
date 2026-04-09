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
    "high_velocity_no_new_device",
    "unusual_time_medium_deviation",
    "large_amount_deviation",
    "high_failed_attempts",
    "suspicious_graph_connections",
    "blended_low_signal_fraud",
]

FRAUD_PATTERN_WEIGHTS = [0.17, 0.16, 0.15, 0.16, 0.13, 0.14, 0.09]

NORMAL_EDGE_PATTERNS = [
    "normal_high_amount_known_device",
    "normal_night_low_amount",
    "normal_new_device_low_value",
    "normal_velocity_burst_known_context",
    "normal_travel_spike_small_amount",
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
        profile_type = "standard"
        severity = "baseline"
        if label == 1:
            pattern = str(rng.choice(FRAUD_PATTERNS, p=FRAUD_PATTERN_WEIGHTS))
            severity = "moderate" if rng.random() < 0.36 else "severe"

        transaction_velocity = int(max(1, rng.poisson(profile["base_velocity"] + 0.2)))
        failed_attempts = int(max(0, rng.poisson(0.6)))
        is_new_device = int(rng.random() < 0.05)
        device_id = profile["secondary_device"] if is_new_device else profile["primary_device"]
        city_name = profile["home_city"]
        txn_type = str(rng.choice(TXN_TYPES, p=[0.45, 0.28, 0.17, 0.10]))

        amount = float(max(20.0, rng.normal(loc=avg_amount, scale=max(65.0, base_std * 0.85))))
        merchant_risk = float(merchant_risk_map[merchant])
        graph_risk = float(rng.beta(2.4, 6.4))

        if label == 1:
            if pattern == "high_amount_new_device":
                profile_type = f"fraud_{severity}"
                if severity == "moderate":
                    amount = float(avg_amount * rng.uniform(2.4, 4.8))
                    transaction_velocity = max(transaction_velocity, int(rng.integers(5, 15)))
                    failed_attempts += int(rng.integers(2, 7))
                    is_new_device = int(rng.random() < 0.75)
                    merchant_risk = max(merchant_risk, float(rng.uniform(0.50, 0.85)))
                    graph_risk = max(graph_risk, float(rng.uniform(0.45, 0.78)))
                else:
                    amount = float(avg_amount * rng.uniform(4.8, 9.5))
                    transaction_velocity = max(transaction_velocity, int(rng.integers(10, 30)))
                    failed_attempts += int(rng.integers(4, 10))
                    is_new_device = int(rng.random() < 0.95)
                    merchant_risk = max(merchant_risk, float(rng.uniform(0.68, 0.95)))
                    graph_risk = max(graph_risk, float(rng.uniform(0.60, 0.92)))
                if is_new_device:
                    device_id = f"DEV_ATTACK_{idx:06d}"
                txn_type = "transfer"
                receiver_upi = f"urgent.kyc.verify.{idx % 250}@upi"
                if rng.random() < (0.55 if severity == "moderate" else 0.80):
                    suspicious_hour = int(rng.choice([0, 1, 2, 3, 4]))
                    ts = ts.replace(hour=suspicious_hour, minute=int(rng.integers(0, 60)))

            elif pattern == "high_velocity_no_new_device":
                profile_type = f"fraud_{severity}"
                if severity == "moderate":
                    transaction_velocity = int(rng.integers(12, 32))
                    amount = float(avg_amount * rng.uniform(1.6, 3.8))
                    failed_attempts += int(rng.integers(2, 8))
                    is_new_device = int(rng.random() < 0.20)
                    merchant_risk = max(merchant_risk, float(rng.uniform(0.46, 0.78)))
                    graph_risk = max(graph_risk, float(rng.uniform(0.45, 0.75)))
                else:
                    transaction_velocity = int(rng.integers(24, 58))
                    amount = float(avg_amount * rng.uniform(2.2, 5.5))
                    failed_attempts += int(rng.integers(6, 15))
                    is_new_device = int(rng.random() < 0.35)
                    merchant_risk = max(merchant_risk, float(rng.uniform(0.60, 0.90)))
                    graph_risk = max(graph_risk, float(rng.uniform(0.60, 0.88)))
                if is_new_device:
                    device_id = f"DEV_VEL_{idx:06d}"
                else:
                    device_id = profile["primary_device"]
                txn_type = "transfer"

            elif pattern == "unusual_time_medium_deviation":
                profile_type = f"fraud_{severity}"
                if rng.random() < (0.65 if severity == "moderate" else 0.85):
                    suspicious_hour = int(rng.choice([0, 1, 2, 3, 4, 23]))
                    ts = ts.replace(hour=suspicious_hour, minute=int(rng.integers(0, 60)))
                amount = float(avg_amount * rng.uniform(2.0, 3.8 if severity == "moderate" else 6.2))
                is_new_device = int(rng.random() < (0.45 if severity == "moderate" else 0.72))
                if is_new_device:
                    device_id = f"DEV_NIGHT_{idx:06d}"
                transaction_velocity = max(transaction_velocity, int(rng.integers(4, 16 if severity == "moderate" else 28)))
                failed_attempts += int(rng.integers(1, 6 if severity == "moderate" else 11))
                merchant_risk = max(merchant_risk, float(rng.uniform(0.48, 0.86 if severity == "moderate" else 0.93)))
                graph_risk = max(graph_risk, float(rng.uniform(0.38, 0.74 if severity == "moderate" else 0.88)))
                txn_type = "transfer"
                receiver_upi = f"refund.support.helpdesk.{idx % 250}@upi"

            elif pattern == "large_amount_deviation":
                profile_type = f"fraud_{severity}"
                amount = float(avg_amount * rng.uniform(2.8, 6.0 if severity == "moderate" else 11.5))
                failed_attempts += int(rng.integers(1, 5 if severity == "moderate" else 10))
                transaction_velocity = max(transaction_velocity, int(rng.integers(3, 14 if severity == "moderate" else 26)))
                is_new_device = max(is_new_device, int(rng.random() < (0.35 if severity == "moderate" else 0.65)))
                if is_new_device:
                    device_id = f"DEV_DEV_{idx:06d}"
                merchant_risk = max(merchant_risk, float(rng.uniform(0.46, 0.82 if severity == "moderate" else 0.92)))
                graph_risk = max(graph_risk, float(rng.uniform(0.36, 0.70 if severity == "moderate" else 0.84)))
                txn_type = "transfer"

            elif pattern == "high_failed_attempts":
                profile_type = f"fraud_{severity}"
                failed_attempts += int(rng.integers(5, 14 if severity == "moderate" else 24))
                amount = float(avg_amount * rng.uniform(1.5, 3.6 if severity == "moderate" else 5.0))
                transaction_velocity = max(transaction_velocity, int(rng.integers(6, 18 if severity == "moderate" else 34)))
                is_new_device = int(rng.random() < (0.38 if severity == "moderate" else 0.60))
                if is_new_device:
                    device_id = f"DEV_FAIL_{idx:06d}"
                merchant_risk = max(merchant_risk, float(rng.uniform(0.44, 0.80 if severity == "moderate" else 0.90)))
                graph_risk = max(graph_risk, float(rng.uniform(0.40, 0.72 if severity == "moderate" else 0.86)))
                txn_type = "transfer"

            elif pattern == "suspicious_graph_connections":
                profile_type = f"fraud_{severity}"
                amount = float(avg_amount * rng.uniform(1.8, 4.2 if severity == "moderate" else 7.0))
                graph_risk = max(graph_risk, float(rng.uniform(0.64, 0.90 if severity == "moderate" else 0.99)))
                merchant_risk = max(merchant_risk, float(rng.uniform(0.52, 0.84 if severity == "moderate" else 0.97)))
                transaction_velocity = max(transaction_velocity, int(rng.integers(4, 14 if severity == "moderate" else 28)))
                is_new_device = max(is_new_device, int(rng.random() < (0.22 if severity == "moderate" else 0.55)))
                if is_new_device:
                    device_id = f"DEV_GRAPH_{idx:06d}"
                txn_type = "transfer"
                receiver_upi = f"mule.collector.{idx % 40}@upi"

            elif pattern == "blended_low_signal_fraud":
                # Intentional low-to-moderate fraud profile to create realistic overlap.
                profile_type = "fraud_borderline"
                amount = float(avg_amount * rng.uniform(1.6, 2.9))
                transaction_velocity = max(transaction_velocity, int(rng.integers(3, 10)))
                failed_attempts += int(rng.integers(1, 7))
                is_new_device = int(rng.random() < 0.30)
                if is_new_device:
                    device_id = f"DEV_BLEND_{idx:06d}"
                if rng.random() < 0.28:
                    suspicious_hour = int(rng.choice([1, 2, 3, 4, 23]))
                    ts = ts.replace(hour=suspicious_hour, minute=int(rng.integers(0, 60)))
                merchant_risk = max(merchant_risk, float(rng.uniform(0.36, 0.68)))
                graph_risk = max(graph_risk, float(rng.uniform(0.40, 0.70)))
                txn_type = str(rng.choice(["purchase", "transfer"], p=[0.40, 0.60]))

        if label == 0 and rng.random() < 0.10:
            edge_pattern = str(rng.choice(NORMAL_EDGE_PATTERNS))
            profile_type = f"normal_edge_{edge_pattern}"

            if edge_pattern == "normal_high_amount_known_device":
                amount = float(avg_amount * rng.uniform(1.9, 3.6))
                is_new_device = 0
                device_id = profile["primary_device"]
                transaction_velocity = max(transaction_velocity, int(rng.integers(2, 8)))
                failed_attempts = max(0, failed_attempts - int(rng.integers(0, 2)))
                txn_type = "transfer"

            elif edge_pattern == "normal_night_low_amount":
                ts = ts.replace(hour=int(rng.choice([1, 2, 3, 4])), minute=int(rng.integers(0, 60)))
                amount = float(avg_amount * rng.uniform(0.35, 1.10))
                is_new_device = int(rng.random() < 0.05)
                device_id = profile["secondary_device"] if is_new_device else profile["primary_device"]
                transaction_velocity = max(1, int(rng.integers(1, 4)))
                failed_attempts = max(0, failed_attempts - int(rng.integers(0, 2)))
                txn_type = str(rng.choice(["bill_payment", "recharge"], p=[0.55, 0.45]))

            elif edge_pattern == "normal_new_device_low_value":
                is_new_device = 1
                device_id = f"DEV_TRAVEL_{idx:06d}"
                amount = float(avg_amount * rng.uniform(0.35, 1.35))
                transaction_velocity = max(1, int(rng.integers(1, 6)))
                failed_attempts = max(0, failed_attempts + int(rng.integers(0, 2)))
                city_name = CITIES[int(rng.integers(0, len(CITIES)))][0]
                merchant_risk = float(min(merchant_risk, rng.uniform(0.10, 0.45)))
                graph_risk = float(min(graph_risk, rng.uniform(0.08, 0.35)))
                txn_type = str(rng.choice(["purchase", "bill_payment", "recharge"], p=[0.30, 0.45, 0.25]))

            elif edge_pattern == "normal_velocity_burst_known_context":
                amount = float(avg_amount * rng.uniform(0.85, 1.85))
                transaction_velocity = max(transaction_velocity, int(rng.integers(6, 13)))
                failed_attempts = max(0, failed_attempts + int(rng.integers(0, 2)))
                is_new_device = 0
                device_id = profile["primary_device"]
                txn_type = str(rng.choice(["bill_payment", "transfer"], p=[0.65, 0.35]))

            elif edge_pattern == "normal_travel_spike_small_amount":
                is_new_device = int(rng.random() < 0.45)
                device_id = f"DEV_TRAVEL_{idx:06d}" if is_new_device else profile["secondary_device"]
                city_name = CITIES[int(rng.integers(0, len(CITIES)))][0]
                amount = float(avg_amount * rng.uniform(0.60, 1.45))
                transaction_velocity = max(transaction_velocity, int(rng.integers(3, 9)))
                failed_attempts = max(0, failed_attempts + int(rng.integers(0, 3)))
                merchant_risk = max(merchant_risk, float(rng.uniform(0.22, 0.54)))
                graph_risk = max(graph_risk, float(rng.uniform(0.20, 0.52)))
                txn_type = str(rng.choice(["purchase", "transfer", "bill_payment"], p=[0.45, 0.20, 0.35]))

        # Introduce overlap by softening a fraction of fraud and elevating a fraction of normal cases.
        if label == 1 and rng.random() < 0.18:
            amount *= float(rng.uniform(0.72, 0.92))
            transaction_velocity = max(1, int(round(transaction_velocity * rng.uniform(0.68, 0.90))))
            failed_attempts = max(0, failed_attempts - int(rng.integers(0, 3)))
            merchant_risk = max(0.24, merchant_risk * float(rng.uniform(0.70, 0.90)))
            graph_risk = max(0.26, graph_risk * float(rng.uniform(0.72, 0.90)))
            profile_type = "fraud_borderline_overlap"

        if label == 0 and rng.random() < 0.14:
            amount *= float(rng.uniform(1.05, 1.45))
            transaction_velocity = max(transaction_velocity, int(rng.integers(4, 11)))
            failed_attempts = max(0, failed_attempts + int(rng.integers(1, 4)))
            merchant_risk = max(merchant_risk, float(rng.uniform(0.24, 0.58)))
            graph_risk = max(graph_risk, float(rng.uniform(0.22, 0.56)))
            if rng.random() < 0.20:
                is_new_device = 1
                device_id = f"DEV_EDGE_{idx:06d}"
            if profile_type == "standard":
                profile_type = "normal_soft_anomaly"

        # Inject slight noise for realistic overlap between classes.
        amount *= float(rng.normal(1.0, 0.05 if label == 1 else 0.04))
        transaction_velocity = int(max(1, round(transaction_velocity + rng.normal(0.0, 1.1))))
        failed_attempts = int(max(0, round(failed_attempts + rng.normal(0.0, 0.85))))
        merchant_risk = _clip01(float(merchant_risk + rng.normal(0.0, 0.032)))
        graph_risk = _clip01(float(graph_risk + rng.normal(0.0, 0.036)))

        if label == 0 and rng.random() < 0.90:
            hour = int(rng.integers(7, 22))
            ts = ts.replace(hour=hour, minute=int(rng.integers(0, 60)))

        city_name_now = city_name
        if label == 1 and (pattern in {"unusual_time_medium_deviation", "suspicious_graph_connections"} or is_new_device == 1):
            city_name_now = CITIES[int(rng.integers(0, len(CITIES)))][0]

        hour_of_day = int(ts.hour)
        is_night = 1 if hour_of_day <= 5 else 0

        amount_deviation = float((amount - avg_amount) / max(base_std, 75.0))
        location_shift = _city_distance_score(profile["home_city"], city_name_now)

        behavior_base = _clip01(
            (0.30 * min(abs(amount_deviation) / 4.0, 1.0))
            + (0.25 * min(transaction_velocity / 20.0, 1.0))
            + (0.20 * is_new_device)
            + (0.15 * min(failed_attempts / 12.0, 1.0))
            + (0.10 * location_shift)
        )

        if label == 1:
            behavior_score = _clip01(behavior_base + float(rng.normal(0.09, 0.10)))
            if pattern == "blended_low_signal_fraud":
                behavior_score = _clip01(behavior_score - float(rng.uniform(0.08, 0.18)))
        else:
            behavior_score = _clip01(behavior_base + float(rng.normal(-0.01, 0.08)))
            if profile_type.startswith("normal_edge"):
                behavior_score = _clip01(behavior_score + float(rng.uniform(0.04, 0.16)))

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
                "scenario_profile": profile_type,
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
