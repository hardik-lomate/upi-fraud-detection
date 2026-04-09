"""Demo scenarios runner with 20 scripted transactions.

Run:
  python scripts/demo_scenarios.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
import os
import time

import requests

API_URL = str(os.getenv("UPI_API_BASE_URL", "")).strip().rstrip("/")
if not API_URL:
    raise RuntimeError("Set UPI_API_BASE_URL, for example: https://your-backend.up.railway.app")
PRECHECK_ENDPOINT = f"{API_URL}/api/v1/pre-check"

DEMO_TRANSACTIONS = [
    {"id": "DEMO_01", "label": "Normal grocery payment", "sender_upi": "rahul.sharma@okicici", "receiver_upi": "bigbasket@ybl", "amount": 1240, "transaction_type": "purchase", "sender_device_id": "SAMSUNG_S23_RAHUL", "timestamp_offset_minutes": -120, "expected_decision": "ALLOW", "expected_risk_tier": "LOW", "expected_score_range": [0.0, 0.3]},
    {"id": "DEMO_02", "label": "Normal bill payment", "sender_upi": "priya.mehta@paytm", "receiver_upi": "bescom@okaxis", "amount": 2800, "transaction_type": "bill_payment", "sender_device_id": "IPHONE14_PRIYA", "timestamp_offset_minutes": -100, "expected_decision": "ALLOW", "expected_risk_tier": "LOW", "expected_score_range": [0.0, 0.3]},
    {"id": "DEMO_03", "label": "Normal friend transfer", "sender_upi": "amit.kumar@oksbi", "receiver_upi": "deepak.verma@ybl", "amount": 5000, "transaction_type": "transfer", "sender_device_id": "ONEPLUS_AMIT", "timestamp_offset_minutes": -90, "expected_decision": "ALLOW", "expected_risk_tier": "LOW", "expected_score_range": [0.0, 0.35]},
    {"id": "DEMO_04", "label": "Slightly high amount — warn zone", "sender_upi": "sunita.joshi@paytm", "receiver_upi": "amazon.in@apl", "amount": 18000, "transaction_type": "purchase", "sender_device_id": "REDMI_SUNITA", "timestamp_offset_minutes": -80, "expected_decision": "VERIFY", "expected_risk_tier": "MEDIUM", "expected_score_range": [0.4, 0.6]},
    {"id": "DEMO_05", "label": "New receiver + high amount", "sender_upi": "rahul.sharma@okicici", "receiver_upi": "lottery9999@ibl", "amount": 45000, "transaction_type": "transfer", "sender_device_id": "SAMSUNG_S23_RAHUL", "timestamp_offset_minutes": -70, "expected_decision": "VERIFY", "expected_risk_tier": "MEDIUM", "expected_score_range": [0.45, 0.72]},
    {"id": "DEMO_06", "label": "Late night high-value transfer", "sender_upi": "priya.mehta@paytm", "receiver_upi": "cashfast@upi", "amount": 35000, "transaction_type": "transfer", "sender_device_id": "IPHONE14_PRIYA", "timestamp_override_hour": 2, "expected_decision": "VERIFY", "expected_risk_tier": "MEDIUM", "expected_score_range": [0.5, 0.75]},
    {"id": "DEMO_07", "label": "Burst of 5 transactions in 1 minute", "sender_upi": "bot.attacker@ybl", "receiver_upi": "mule.account1@paytm", "amount": 9999, "transaction_type": "transfer", "sender_device_id": "VIRTUAL_DEV_01", "expected_decision": "BLOCK", "expected_risk_tier": "HIGH", "expected_score_range": [0.75, 1.0]},
    {"id": "DEMO_08", "label": "Impossible travel — Pune to Delhi in 10 minutes", "sender_upi": "amit.kumar@oksbi", "receiver_upi": "vendor@hdfcbank", "amount": 12000, "transaction_type": "transfer", "sender_device_id": "STOLEN_DEVICE", "sender_location_lat": 28.6139, "sender_location_lon": 77.2090, "expected_decision": "BLOCK", "expected_risk_tier": "HIGH", "expected_score_range": [0.8, 1.0]},
    {"id": "DEMO_09", "label": "New device — possible SIM swap", "sender_upi": "sunita.joshi@paytm", "receiver_upi": "transfer@okicici", "amount": 25000, "transaction_type": "transfer", "sender_device_id": "NEW_UNKNOWN_DEVICE", "expected_decision": "VERIFY", "expected_risk_tier": "MEDIUM", "expected_score_range": [0.5, 0.75]},
    {"id": "DEMO_10", "label": "Flagged receiver UPI", "sender_upi": "victim.user@okicici", "receiver_upi": "scamaccount@upi", "amount": 8000, "transaction_type": "transfer", "sender_device_id": "VICTIM_PHONE", "expected_decision": "BLOCK", "expected_risk_tier": "HIGH", "expected_score_range": [0.75, 1.0]},
    {"id": "DEMO_11", "label": "Recharge scam — OTP correlation", "sender_upi": "elderly.user@paytm", "receiver_upi": "otp.scam.vpa@upi", "amount": 999, "transaction_type": "recharge", "sender_device_id": "ELDERLY_PHONE", "expected_decision": "VERIFY", "expected_risk_tier": "MEDIUM", "expected_score_range": [0.5, 0.7]},
    {"id": "DEMO_12", "label": "Normal ATM withdrawal simulation", "sender_upi": "deepak.verma@ybl", "receiver_upi": "atm.sbi@sbi", "amount": 3000, "transaction_type": "transfer", "sender_device_id": "VIVO_DEEPAK", "expected_decision": "ALLOW", "expected_risk_tier": "LOW", "expected_score_range": [0.0, 0.3]},
    {"id": "DEMO_13", "label": "Mule account — many incoming senders", "sender_upi": "innocent.user@oksbi", "receiver_upi": "mule.collector@paytm", "amount": 7500, "transaction_type": "transfer", "sender_device_id": "INNOCENT_PHONE", "expected_decision": "BLOCK", "expected_risk_tier": "HIGH", "expected_score_range": [0.75, 1.0]},
    {"id": "DEMO_14", "label": "Large legitimate business payment", "sender_upi": "retailshop.owner@okaxis", "receiver_upi": "wholesale.supplier@hdfcbank", "amount": 95000, "transaction_type": "transfer", "sender_device_id": "BUSINESS_LAPTOP_01", "expected_decision": "ALLOW", "expected_risk_tier": "LOW", "expected_score_range": [0.0, 0.4]},
    {"id": "DEMO_15", "label": "Weekend high-value transfer to new receiver", "sender_upi": "rahul.sharma@okicici", "receiver_upi": "property.deal99@ybl", "amount": 200000, "transaction_type": "transfer", "sender_device_id": "SAMSUNG_S23_RAHUL", "timestamp_override_hour": 23, "expected_decision": "BLOCK", "expected_risk_tier": "HIGH", "expected_score_range": [0.8, 1.0]},
    {"id": "DEMO_16", "label": "Normal UPI autopay subscription", "sender_upi": "priya.mehta@paytm", "receiver_upi": "netflix@ybl", "amount": 649, "transaction_type": "bill_payment", "sender_device_id": "IPHONE14_PRIYA", "expected_decision": "ALLOW", "expected_risk_tier": "LOW", "expected_score_range": [0.0, 0.2]},
    {"id": "DEMO_17", "label": "Cross-bank transfer to brand-new UPI", "sender_upi": "sunita.joshi@paytm", "receiver_upi": "newid.just.created@ibl", "amount": 50000, "transaction_type": "transfer", "sender_device_id": "REDMI_SUNITA", "expected_decision": "BLOCK", "expected_risk_tier": "HIGH", "expected_score_range": [0.78, 1.0]},
    {"id": "DEMO_18", "label": "Phishing UPI — suspicious pattern", "sender_upi": "victim2@okicici", "receiver_upi": "sbi-customer-care-helpline@upi", "amount": 1, "transaction_type": "transfer", "sender_device_id": "VICTIM2_PHONE", "expected_decision": "BLOCK", "expected_risk_tier": "HIGH", "expected_score_range": [0.75, 1.0]},
    {"id": "DEMO_19", "label": "Normal student sending rent", "sender_upi": "student.user@oksbi", "receiver_upi": "landlord.ram@okicici", "amount": 8500, "transaction_type": "transfer", "sender_device_id": "REDMI_STUDENT", "expected_decision": "ALLOW", "expected_risk_tier": "LOW", "expected_score_range": [0.0, 0.35]},
    {"id": "DEMO_20", "label": "Extreme fraud — all signals fire", "sender_upi": "victim.full@paytm", "receiver_upi": "fraud.ring.account@upi", "amount": 99999, "transaction_type": "transfer", "sender_device_id": "HACKED_DEVICE", "timestamp_override_hour": 3, "sender_location_lat": 28.6139, "sender_location_lon": 77.2090, "expected_decision": "BLOCK", "expected_risk_tier": "HIGH", "expected_score_range": [0.9, 1.0]},
]


def _build_payload(spec: dict, now: datetime) -> dict:
    ts = now + timedelta(minutes=int(spec.get("timestamp_offset_minutes", 0)))
    if "timestamp_override_hour" in spec:
        ts = ts.replace(hour=int(spec["timestamp_override_hour"]), minute=17, second=0, microsecond=0)

    payload = {
        "sender_upi": spec["sender_upi"],
        "receiver_upi": spec["receiver_upi"],
        "amount": spec["amount"],
        "transaction_type": spec.get("transaction_type", "transfer"),
        "sender_device_id": spec.get("sender_device_id", "DEMO_DEVICE"),
        "timestamp": ts.isoformat(),
    }
    if "sender_location_lat" in spec and "sender_location_lon" in spec:
        payload["sender_location_lat"] = spec["sender_location_lat"]
        payload["sender_location_lon"] = spec["sender_location_lon"]
    return payload


def _score_ok(score: float, expected_range: list[float]) -> bool:
    return float(expected_range[0]) <= score <= float(expected_range[1])


def run_demo():
    print("=" * 120)
    print("UPI Fraud Detection Demo Runner (20 scripted transactions)")
    print("=" * 120)

    total = len(DEMO_TRANSACTIONS)
    allowed = warned = blocked = 0
    correctly_classified = 0

    now = datetime.utcnow()
    for spec in DEMO_TRANSACTIONS:
        payload = _build_payload(spec, now)
        try:
            response = requests.post(PRECHECK_ENDPOINT, json=payload, timeout=12)
        except requests.ConnectionError:
            print("Cannot connect to backend. Start API first.")
            return

        if response.status_code != 200:
            print(f"{spec['id']} | {spec['label']} | ERROR {response.status_code} {response.text[:180]}")
            continue

        data = response.json()
        decision = str(data.get("decision", "")).upper()
        risk_score = float(data.get("risk_score", 0.0) or 0.0)
        risk_tier = str(data.get("risk_tier") or data.get("user_warning", {}).get("risk_tier") or "LOW").upper()
        reasons = list(data.get("reasons", []))[:3]

        if decision == "ALLOW":
            allowed += 1
        elif decision == "BLOCK":
            blocked += 1
        else:
            warned += 1

        expected_decision = str(spec.get("expected_decision", "ALLOW")).upper()
        expected_tier = str(spec.get("expected_risk_tier", "LOW")).upper()
        expected_range = spec.get("expected_score_range", [0.0, 1.0])

        is_pass = decision == expected_decision and risk_tier == expected_tier and _score_ok(risk_score, expected_range)
        if is_pass:
            correctly_classified += 1

        print(
            f"{spec['id']} | {spec['label']} | amount={spec['amount']} | receiver={spec['receiver_upi']} | "
            f"risk_score={risk_score:.4f} | risk_tier={risk_tier} | decision={decision} | "
            f"top_reasons={reasons} | pass_fail={'PASS' if is_pass else 'FAIL'}"
        )
        time.sleep(0.12)

    accuracy = correctly_classified / max(total, 1)
    print("-" * 120)
    print(
        "SUMMARY | "
        f"total={total} | allowed={allowed} | warned={warned} | blocked={blocked} | "
        f"correctly_classified={correctly_classified} | accuracy={accuracy:.2%}"
    )
    print("=" * 120)


if __name__ == "__main__":
    run_demo()
