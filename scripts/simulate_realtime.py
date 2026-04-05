"""Real-time load simulator with traffic profiles.

Usage examples:
  python scripts/simulate_realtime.py --profile normal
  python scripts/simulate_realtime.py --profile peak --speed 1.5
  python scripts/simulate_realtime.py --profile stress --max-events 300
"""

import argparse
import time
from datetime import datetime
import random

import requests


API_URL = "http://127.0.0.1:8000/predict"

SENDERS = [f"user{i:04d}@upi" for i in range(600)]
MERCHANTS = [f"merchant{i:04d}@upi" for i in range(450)]
PEERS = [f"friend{i:04d}@upi" for i in range(200)]
DEVICES = [f"DEV_{i:04d}" for i in range(650)]
TXN_TYPES = ["purchase", "transfer", "bill_payment", "recharge"]

PROFILES = {
    "normal": {
        "base_delay": 1.0,
        "suspicious_rate": 0.06,
        "burst_every": 30,
        "burst_size": 2,
    },
    "peak": {
        "base_delay": 0.6,
        "suspicious_rate": 0.08,
        "burst_every": 14,
        "burst_size": 3,
    },
    "stress": {
        "base_delay": 0.35,
        "suspicious_rate": 0.12,
        "burst_every": 9,
        "burst_size": 4,
    },
    "attack": {
        "base_delay": 0.28,
        "suspicious_rate": 0.2,
        "burst_every": 8,
        "burst_size": 4,
    },
}


def _profile_multiplier(hour: int) -> float:
    if 8 <= hour <= 11 or 18 <= hour <= 22:
        return 1.4
    if 12 <= hour <= 15:
        return 1.15
    if 0 <= hour <= 5:
        return 0.55
    return 0.9


def _next_delay(profile: str, speed: float, target_tps: float) -> float:
    cfg = PROFILES[profile]
    hour = datetime.now().hour
    demand = _profile_multiplier(hour)
    jitter = random.uniform(0.75, 1.35)
    base_delay = cfg["base_delay"] * jitter / max(0.2, demand * speed)

    # Rate control: keep simulator in realistic 1-5 TPS window.
    bounded_tps = max(1.0, min(5.0, float(target_tps)))
    target_delay = 1.0 / bounded_tps
    delay = (base_delay * 0.6) + (target_delay * 0.4)
    return max(0.2, min(delay, 1.0))


def _amount(is_suspicious: bool) -> float:
    if is_suspicious:
        # Mix of moderate to high-risk payments.
        r = random.random()
        if r < 0.6:
            return round(random.uniform(9000, 65000), 2)
        return round(random.uniform(65000, 240000), 2)

    r = random.random()
    if r < 0.7:
        return round(random.uniform(50, 2500), 2)
    if r < 0.93:
        return round(random.uniform(2500, 12000), 2)
    return round(random.uniform(12000, 35000), 2)


def make_transaction(event_id: int, profile: str) -> dict:
    cfg = PROFILES[profile]
    is_suspicious = random.random() < cfg["suspicious_rate"]

    sender = random.choice(SENDERS)
    txn_type = random.choice(TXN_TYPES)

    if txn_type == "transfer":
        receiver = random.choice(PEERS)
    else:
        receiver = random.choice(MERCHANTS)

    amount = _amount(is_suspicious)

    if is_suspicious and random.random() < 0.25:
        # Deliberate suspicious marker: unknown device on higher amounts.
        device = f"DEV_NEW_{event_id:06d}"
    else:
        device = random.choice(DEVICES)

    ts = datetime.now()
    if is_suspicious and random.random() < 0.3:
        ts = ts.replace(hour=random.choice([1, 2, 3, 4]), minute=random.randint(0, 59))

    return {
        "sender_upi": sender,
        "receiver_upi": receiver,
        "amount": amount,
        "transaction_type": txn_type,
        "sender_device_id": device,
        "timestamp": ts.isoformat(),
    }


def _burst_size(seq: int, profile: str) -> int:
    cfg = PROFILES[profile]
    if seq > 0 and seq % cfg["burst_every"] == 0:
        return cfg["burst_size"]
    return 1


def run(profile: str, speed: float, max_events: int, target_tps: float):
    print("Starting real-time transaction simulation")
    print(f"Target      : {API_URL}")
    print(f"Profile     : {profile}")
    print(f"Speed x     : {speed}")
    print(f"Target TPS  : {target_tps}")
    if max_events > 0:
        print(f"Max events  : {max_events}")
    print("Press Ctrl+C to stop")
    print()

    total = 0
    blocked = 0
    verify = 0
    allowed = 0

    try:
        while True:
            batch = _burst_size(total, profile)
            for _ in range(batch):
                if max_events > 0 and total >= max_events:
                    raise KeyboardInterrupt

                txn = make_transaction(total, profile)
                try:
                    resp = requests.post(API_URL, json=txn, timeout=8)
                    resp.raise_for_status()
                    data = resp.json()

                    total += 1
                    decision = str(data.get("decision", "")).upper()
                    score = float(data.get("fraud_score", 0.0))

                    if decision == "BLOCK":
                        blocked += 1
                        icon = "[BLOCK]"
                    elif decision == "VERIFY":
                        verify += 1
                        icon = "[CHECK]"
                    else:
                        allowed += 1
                        icon = "[ALLOW]"

                    print(
                        f"{icon} #{total:05d} | INR {txn['amount']:>10,.2f} | "
                        f"score={score:0.3f} | {decision:6s} | {txn['sender_upi']} -> {txn['receiver_upi']}"
                    )
                except requests.exceptions.RequestException as exc:
                    print(f"[ERROR] request failed: {exc}")

            time.sleep(_next_delay(profile, speed, target_tps))

    except KeyboardInterrupt:
        print("\nSimulation summary")
        print(f"Total  : {total}")
        print(f"Allow  : {allowed}")
        print(f"Verify : {verify}")
        print(f"Block  : {blocked}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UPI fraud realtime simulator")
    parser.add_argument("--profile", choices=["normal", "peak", "stress", "attack"], default="normal")
    parser.add_argument("--speed", type=float, default=1.0, help="Traffic speed multiplier")
    parser.add_argument("--tps", type=float, default=2.0, help="Target transactions per second (1-5)")
    parser.add_argument("--max-events", type=int, default=0, help="Stop after N events (0 = infinite)")
    return parser.parse_args()


if __name__ == "__main__":
    random.seed(42)
    args = parse_args()
    run(
        args.profile,
        max(0.25, min(args.speed, 4.0)),
        max(0, args.max_events),
        max(1.0, min(args.tps, 5.0)),
    )
