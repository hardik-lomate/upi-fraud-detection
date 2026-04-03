"""
Demo Scenarios — 6 pre-built transactions demonstrating specific system behaviors.
Run: python scripts/demo_scenarios.py
"""

import requests
import json
import time

API_URL = "http://localhost:8000"

SCENARIOS = [
    {
        "name": "1. LEGITIMATE PURCHASE",
        "description": "Normal daytime purchase, known device, regular amount → ALLOW",
        "payload": {
            "sender_upi": "alice_regular@upi",
            "receiver_upi": "amazon_merchant@upi",
            "amount": 499,
            "transaction_type": "purchase",
            "sender_device_id": "ALICE_IPHONE_14",
            "timestamp": "2026-04-03T14:30:00",
        },
    },
    {
        "name": "2. SELF-TRANSFER (Rule: BLOCK)",
        "description": "Sender == Receiver → instant BLOCK by rules engine, ML never runs",
        "payload": {
            "sender_upi": "fraud_bob@upi",
            "receiver_upi": "fraud_bob@upi",
            "amount": 5000,
            "transaction_type": "transfer",
            "sender_device_id": "BOB_PHONE",
            "timestamp": "2026-04-03T15:00:00",
        },
    },
    {
        "name": "3. MIDNIGHT WHALE (Rule: FLAG)",
        "description": "₹85,000 transfer at 3AM → MIDNIGHT_HIGH_VALUE rule fires",
        "payload": {
            "sender_upi": "night_owl@upi",
            "receiver_upi": "shady_account@upi",
            "amount": 85000,
            "transaction_type": "transfer",
            "sender_device_id": "NIGHT_DEVICE",
            "timestamp": "2026-04-03T03:15:00",
        },
    },
    {
        "name": "4. NEW DEVICE HIGH AMOUNT (Rule: FLAG)",
        "description": "₹45,000 from an unrecognized device → NEW_DEVICE_HIGH_AMOUNT",
        "payload": {
            "sender_upi": "carol_victim@upi",
            "receiver_upi": "electronics_store@upi",
            "amount": 45000,
            "transaction_type": "purchase",
            "sender_device_id": "STOLEN_DEVICE_999",
            "timestamp": "2026-04-03T11:00:00",
        },
    },
    {
        "name": "5. HIGH AMOUNT + NEW ACCOUNT (Rule: BLOCK)",
        "description": "₹150,000 from account with <5 txns → HIGH_AMOUNT_NEW_ACCOUNT",
        "payload": {
            "sender_upi": "new_user_dave@upi",
            "receiver_upi": "luxury_store@upi",
            "amount": 150000,
            "transaction_type": "purchase",
            "sender_device_id": "DAVE_PHONE",
            "timestamp": "2026-04-03T16:00:00",
        },
    },
    {
        "name": "6. ML FRAUD DETECTION (No rule, pure ML)",
        "description": "All ML features fraud-positive: night, weekend, new device, high deviation",
        "payload": {
            "sender_upi": "ml_test_sender@upi",
            "receiver_upi": "ml_test_receiver@upi",
            "amount": 49000,
            "transaction_type": "transfer",
            "sender_device_id": "SUSPICIOUS_DEV_X",
            "timestamp": "2026-04-05T02:45:00",  # Saturday 2:45 AM
        },
    },
]


def run_demo():
    print("=" * 70)
    print("  UPI FRAUD DETECTION — DEMO SCENARIOS")
    print("=" * 70)

    for scenario in SCENARIOS:
        print(f"\n{'─' * 60}")
        print(f"  {scenario['name']}")
        print(f"  {scenario['description']}")
        print(f"{'─' * 60}")

        try:
            r = requests.post(f"{API_URL}/predict", json=scenario["payload"], timeout=10)
            if r.status_code == 200:
                data = r.json()
                color = {"ALLOW": "🟢", "FLAG": "🟡", "BLOCK": "🔴"}.get(data["decision"], "⚪")
                print(f"  {color} Decision: {data['decision']}  Score: {data['fraud_score']:.1%}  Risk: {data['risk_level']}")

                if data.get("rules_triggered"):
                    print(f"  📋 Rules: {', '.join(r['rule_name'] for r in data['rules_triggered'])}")

                if data.get("reasons"):
                    for reason in data["reasons"][:3]:
                        print(f"     💡 {reason}")

                if data.get("models_used"):
                    scores = data.get("individual_scores", {})
                    parts = [f"{m}={scores.get(m, 0):.1%}" for m in data["models_used"]]
                    print(f"  🤖 Models: {' | '.join(parts)}")
            else:
                print(f"  ❌ Error {r.status_code}: {r.text[:200]}")
        except requests.ConnectionError:
            print("  ❌ Cannot connect to API. Start the backend first: uvicorn app.main:app")
            return

        time.sleep(0.3)

    print(f"\n{'=' * 70}")
    print("  Demo complete! Check /monitoring/stats for aggregated results.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
