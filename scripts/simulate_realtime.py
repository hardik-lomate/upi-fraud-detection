import requests
import random
import time
import uuid
from datetime import datetime

API_URL = "http://localhost:8000/predict"

senders = [f"user{i}@upi" for i in range(100)]
receivers = [f"merchant{i}@upi" for i in range(200)]
devices = [f"DEV_{uuid.uuid4().hex[:8].upper()}" for _ in range(100)]
txn_types = ["purchase", "transfer", "bill_payment", "recharge"]


def random_transaction(is_suspicious=False):
    if is_suspicious:
        return {
            "sender_upi": random.choice(senders),
            "receiver_upi": random.choice(receivers),
            "amount": round(random.uniform(10000, 50000), 2),
            "transaction_type": random.choice(txn_types),
            "sender_device_id": f"DEV_{uuid.uuid4().hex[:8].upper()}",
            "sender_ip": f"{random.randint(1,255)}.{random.randint(0,255)}.0.1",
            "timestamp": datetime.now()
            .replace(hour=random.choice([1, 2, 3, 4]))
            .isoformat(),
        }
    return {
        "sender_upi": random.choice(senders),
        "receiver_upi": random.choice(receivers),
        "amount": round(random.uniform(50, 3000), 2),
        "transaction_type": random.choice(txn_types),
        "sender_device_id": random.choice(devices),
        "sender_ip": f"192.168.1.{random.randint(1,254)}",
        "timestamp": datetime.now().isoformat(),
    }


def main():
    print("🚀 Starting real-time transaction simulation...")
    print(f"   Target: {API_URL}")
    print("   Press Ctrl+C to stop\n")

    count = 0
    blocked = 0
    flagged = 0

    try:
        while True:
            # 5% chance of suspicious transaction
            is_suspicious = random.random() < 0.05
            txn = random_transaction(is_suspicious)

            try:
                resp = requests.post(API_URL, json=txn, timeout=5)
                data = resp.json()
                count += 1

                decision = data["decision"]
                score = data["fraud_score"]

                if decision == "BLOCK":
                    blocked += 1
                    icon = "🚫"
                elif decision == "FLAG":
                    flagged += 1
                    icon = "⚠️"
                else:
                    icon = "✅"

                print(
                    f"  {icon} #{count:04d} | ₹{txn['amount']:>10,.2f} | "
                    f"Score: {score:.3f} | {decision:5s} | "
                    f"{txn['sender_upi']} → {txn['receiver_upi']}"
                )

            except requests.exceptions.RequestException as e:
                print(f"  ❌ Request failed: {e}")

            time.sleep(random.uniform(0.5, 2.0))

    except KeyboardInterrupt:
        print(f"\n\n📊 Simulation Summary:")
        print(f"   Total transactions: {count}")
        print(f"   Blocked:            {blocked}")
        print(f"   Flagged:            {flagged}")
        print(f"   Allowed:            {count - blocked - flagged}")


if __name__ == "__main__":
    main()
