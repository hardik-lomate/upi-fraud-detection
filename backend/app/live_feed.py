"""
WebSocket Live Transaction Feed — sends simulated transactions every 2 seconds.
"""

import asyncio
import random
import uuid
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect


# Simulated UPI IDs and device patterns
SENDERS = [f"user_{i:03d}@upi" for i in range(50)]
RECEIVERS = [f"merchant_{i:03d}@upi" for i in range(30)] + [f"user_{i:03d}@upi" for i in range(20)]
DEVICES = [f"DEV_{uuid.uuid4().hex[:8].upper()}" for _ in range(40)]
TXN_TYPES = ["purchase", "transfer", "bill_payment", "recharge"]
TXN_TYPE_WEIGHTS = [0.45, 0.30, 0.15, 0.10]


def _generate_random_txn() -> dict:
    """Generate a random realistic-looking transaction."""
    hour = datetime.now().hour
    # Slightly fraudulent patterns at night
    is_suspicious = random.random() < 0.12
    if is_suspicious:
        amount = random.choice([random.uniform(20000, 100000), random.uniform(45000, 200000)])
        txn_type = "transfer"
    else:
        amount = random.choice([
            random.uniform(10, 500),      # small purchase
            random.uniform(100, 3000),     # medium
            random.uniform(500, 15000),    # large
        ])
        txn_type = random.choices(TXN_TYPES, weights=TXN_TYPE_WEIGHTS, k=1)[0]

    sender = random.choice(SENDERS)
    receiver = random.choice(RECEIVERS)
    # Small chance of self-transfer (fraud pattern)
    if random.random() < 0.03:
        receiver = sender

    return {
        "sender_upi": sender,
        "receiver_upi": receiver,
        "amount": round(amount, 2),
        "transaction_type": txn_type,
        "sender_device_id": random.choice(DEVICES),
        "timestamp": datetime.now().isoformat(),
    }


async def live_feed_handler(websocket: WebSocket, pipeline_fn):
    """
    WebSocket handler — sends a simulated transaction + prediction every 2 seconds.
    pipeline_fn should accept a txn dict and return a prediction result dict.
    """
    await websocket.accept()
    seq = 0
    try:
        while True:
            txn = _generate_random_txn()
            try:
                result = pipeline_fn(txn)
                msg = {
                    "seq": seq,
                    "transaction": txn,
                    "prediction": result,
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                msg = {"seq": seq, "transaction": txn, "error": str(e),
                       "timestamp": datetime.now().isoformat()}

            await websocket.send_json(msg)
            seq += 1
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
