"""Lock-check: deterministic /predict output for identical input."""

import json
import sys
import time

import requests

BASE = "http://127.0.0.1:8000"

RUN_ID = str(int(time.time()))

payload = {
    # Use a per-run unique sender/receiver so we don't hit an old cached DB record
    # for the deterministic txn_id (sender|receiver|amount|type).
    "sender_upi": f"lockcheck_{RUN_ID}@upi",
    "receiver_upi": f"merchant_{RUN_ID}@upi",
    "amount": 30000,
    "transaction_type": "transfer",
    "sender_device_id": "NEW_DEVICE_LOCKCHECK",
}


def post_predict() -> dict:
    r = requests.post(f"{BASE}/predict", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def main() -> int:
    r1 = post_predict()
    r2 = post_predict()

    s1 = json.dumps(r1, sort_keys=True, separators=(",", ":"))
    s2 = json.dumps(r2, sort_keys=True, separators=(",", ":"))

    same = s1 == s2
    print("same_json:", same)

    if not same:
        keys = sorted(set(r1) | set(r2))
        for k in keys:
            if r1.get(k) != r2.get(k):
                print("diff", k, "=>", r1.get(k), "vs", r2.get(k))
        return 1

    print(
        "decision:",
        r1.get("decision"),
        "fraud_score:",
        r1.get("fraud_score"),
        "risk_score:",
        r1.get("risk_score"),
        "status:",
        r1.get("status"),
    )
    print("transaction_id:", r1.get("transaction_id"))
    print("timestamp:", r1.get("timestamp"))
    print("reasons:", r1.get("reasons"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
