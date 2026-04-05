"""Deterministic load and latency benchmark for /predict.

Runs 50-100+ requests, reports:
- success rate
- average/max/p95 latency
- decision distribution
- deterministic same-input consistency check

Usage:
  python scripts/benchmark_load.py --count 100
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta

import requests

BASE_URL = "http://127.0.0.1:8000"
PREDICT_URL = f"{BASE_URL}/predict"


def build_payload(i: int) -> dict:
    ts = (datetime(2026, 4, 1, 10, 0, 0) + timedelta(seconds=i)).isoformat()

    # Deterministic traffic split: mostly normal, periodic suspicious attack-like events.
    if i % 12 in (10, 11):
        return {
            "sender_upi": f"attack_sender_{i % 5}@upi",
            "receiver_upi": f"new_receiver_{i}@upi",
            "amount": float(35000 + (i % 7) * 5500),
            "transaction_type": "transfer",
            "sender_device_id": f"ATTACK_DEV_{i:03d}",
            "timestamp": ts,
        }

    return {
        "sender_upi": f"normal_sender_{i % 20}@upi",
        "receiver_upi": f"trusted_merchant_{i % 8}@upi",
        "amount": float(120 + (i % 15) * 180),
        "transaction_type": "purchase",
        "sender_device_id": f"KNOWN_DEV_{i % 20:03d}",
        "timestamp": ts,
    }


def post_once(payload: dict, timeout: int = 10) -> tuple[bool, float, dict | None, str | None]:
    start = time.perf_counter()
    try:
        r = requests.post(PREDICT_URL, json=payload, timeout=timeout)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if r.status_code != 200:
            return (False, elapsed_ms, None, f"HTTP {r.status_code}: {r.text[:120]}")
        return (True, elapsed_ms, r.json(), None)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return (False, elapsed_ms, None, str(exc))


def run(count: int, rate: float) -> int:
    latencies = []
    success = 0
    failures = 0
    decision_counts = {"ALLOW": 0, "VERIFY": 0, "BLOCK": 0}
    errors = []

    interval = 1.0 / max(0.1, float(rate))

    for i in range(count):
        req_start = time.perf_counter()
        payload = build_payload(i)
        ok, elapsed_ms, data, err = post_once(payload)
        latencies.append(elapsed_ms)

        if ok and data:
            success += 1
            decision = str(data.get("decision", "")).upper()
            if decision in decision_counts:
                decision_counts[decision] += 1
        else:
            failures += 1
            if err:
                errors.append(err)

        spent = time.perf_counter() - req_start
        if spent < interval:
            time.sleep(interval - spent)

    # Determinism check: same payload twice -> exactly same JSON
    consistency_payload = {
        "sender_upi": "determinism_case@upi",
        "receiver_upi": "determinism_merchant@upi",
        "amount": 30000.0,
        "transaction_type": "transfer",
        "sender_device_id": "DET_DEVICE_001",
        "timestamp": "2026-04-01T11:30:00",
    }
    ok1, _, out1, err1 = post_once(consistency_payload)
    ok2, _, out2, err2 = post_once(consistency_payload)
    deterministic = bool(ok1 and ok2 and out1 == out2)

    lat_sorted = sorted(latencies)
    avg_ms = sum(latencies) / max(1, len(latencies))
    max_ms = max(latencies) if latencies else 0.0
    p95_ms = lat_sorted[int(0.95 * (len(lat_sorted) - 1))] if lat_sorted else 0.0

    report = {
        "count": count,
        "success": success,
        "failures": failures,
        "success_rate_pct": round((success / max(1, count)) * 100, 2),
        "latency_ms": {
            "avg": round(avg_ms, 2),
            "max": round(max_ms, 2),
            "p95": round(p95_ms, 2),
            "target_lt_200ms": avg_ms < 200.0,
        },
        "decision_distribution": decision_counts,
        "deterministic_same_input": deterministic,
        "determinism_errors": [e for e in [err1, err2] if e],
        "sample_errors": errors[:5],
    }

    print(json.dumps(report, indent=2))

    if failures > 0:
        return 1
    if not deterministic:
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic load benchmark for /predict")
    parser.add_argument("--count", type=int, default=80, help="Number of transactions to send (recommended 50-100)")
    parser.add_argument("--rate", type=float, default=1.2, help="Request rate (transactions per second)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    c = max(50, min(1000, args.count))
    raise SystemExit(run(c, max(0.2, min(args.rate, 5.0))))
