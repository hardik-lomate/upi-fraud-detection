import pandas as pd
import numpy as np
import random
import uuid
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

NUM_TRANSACTIONS = 100_000
FRAUD_RATIO = 0.03  # 3% fraud rate (realistic)

NUM_SENDERS = 5000
NUM_RECEIVERS = 8000

senders = [f"user{i}@upi" for i in range(NUM_SENDERS)]
receivers = [f"merchant{i}@upi" for i in range(NUM_RECEIVERS)]
devices = [f"DEV_{uuid.uuid4().hex[:8].upper()}" for _ in range(NUM_SENDERS)]
txn_types = ["purchase", "transfer", "bill_payment", "recharge"]


def generate_transaction(idx, is_fraud=False):
    sender_idx = random.randint(0, NUM_SENDERS - 1)
    timestamp = datetime(2024, 1, 1) + timedelta(
        seconds=random.randint(0, 90 * 24 * 3600)
    )

    if is_fraud:
        amount = round(
            random.choice(
                [
                    random.uniform(8000, 50000),  # unusually high
                    random.uniform(1, 10),  # micro-test transaction
                ]
            ),
            2,
        )
        hour = random.choice([0, 1, 2, 3, 4, 23])  # odd hours
        receiver_idx = random.randint(0, NUM_RECEIVERS - 1)
        # Fraudsters often use new devices
        device = f"DEV_{uuid.uuid4().hex[:8].upper()}"
    else:
        amount = round(random.uniform(10, 5000), 2)
        hour = random.randint(6, 22)
        receiver_idx = random.randint(0, NUM_RECEIVERS - 1)
        device = devices[sender_idx]

    timestamp = timestamp.replace(hour=hour)

    return {
        "transaction_id": f"TXN_{timestamp.strftime('%Y%m%d')}_{idx:06d}",
        "sender_upi": senders[sender_idx],
        "receiver_upi": receivers[receiver_idx],
        "amount": amount,
        "timestamp": timestamp.isoformat(),
        "sender_device_id": device,
        "sender_ip": f"{random.randint(1,255)}.{random.randint(0,255)}."
        f"{random.randint(0,255)}.{random.randint(1,254)}",
        "transaction_type": random.choice(txn_types),
        "sender_location_lat": round(random.uniform(8.0, 37.0), 4),
        "sender_location_lon": round(random.uniform(68.0, 97.0), 4),
        "is_fraud": 1 if is_fraud else 0,
    }


if __name__ == "__main__":
    import os

    os.makedirs("ml/data/raw", exist_ok=True)
    os.makedirs("ml/data/processed", exist_ok=True)
    os.makedirs("ml/models", exist_ok=True)

    num_fraud = int(NUM_TRANSACTIONS * FRAUD_RATIO)
    num_legit = NUM_TRANSACTIONS - num_fraud

    transactions = []
    for i in range(num_legit):
        transactions.append(generate_transaction(i, is_fraud=False))
    for i in range(num_fraud):
        transactions.append(generate_transaction(num_legit + i, is_fraud=True))

    df = pd.DataFrame(transactions)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    df.to_csv("ml/data/raw/transactions.csv", index=False)
    print(f"Generated {len(df)} transactions ({num_fraud} fraud, {num_legit} legit)")
    print(f"Fraud ratio: {num_fraud / len(df) * 100:.1f}%")
    print(df.head())
