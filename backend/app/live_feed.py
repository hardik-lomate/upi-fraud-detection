"""WebSocket live feed v3.0 — Realistic fraud injection at 15-20% rate.

Injects named bad actors, velocity attacks, impossible travel,
SIM swap patterns, and mule consolidation into the transaction stream.
"""

import asyncio
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect


SENDERS = [f"user_{i:04d}@upi" for i in range(1200)]
MERCHANTS = [f"merchant_{i:04d}@upi" for i in range(300)]
PEERS = [f"friend_{i:04d}@upi" for i in range(220)]
DEVICES = [f"DEV_{i:04d}" for i in range(1200)]
TXN_TYPES = ["purchase", "transfer", "bill_payment", "recharge"]

# Named bad actors that repeatedly show up so the system builds history
FRAUD_SENDERS = [
    "attacker_001@ybl", "mule_driver@paytm", "sim_swap_victim@upi",
    "velocity_bot@oksbi", "geo_spoof@okicici", "new_acct_fraud@ybl",
    "smurfing_user@okhdfcbank", "account_takeover@upi", "synthetic_id@okaxis",
    "card_fraud_linked@paytm",
]
FRAUD_RECEIVERS = [
    "mule_a@ybl", "mule_b@paytm", "mule_c@oksbi",
    "cash_out_001@upi", "offshore_xk9f2@ybl", "drop_account@okicici",
    "temp_collect@upi", "fake_merchant@okhdfcbank",
]

# Indian cities for impossible travel simulation
CITIES = [
    {"name": "Mumbai", "lat": 19.076, "lon": 72.877},
    {"name": "Delhi", "lat": 28.614, "lon": 77.209},
    {"name": "Bangalore", "lat": 12.972, "lon": 77.595},
    {"name": "Chennai", "lat": 13.083, "lon": 80.271},
    {"name": "Kolkata", "lat": 22.572, "lon": 88.364},
    {"name": "Hyderabad", "lat": 17.385, "lon": 78.487},
    {"name": "Jamtara", "lat": 23.963, "lon": 86.814},  # Known fraud hotspot
    {"name": "Mewat", "lat": 27.928, "lon": 77.001},     # Known fraud hotspot
]

PROFILE_SETTINGS = {
    "normal": {
        "base_delay": 0.7,
        "jitter": [0.9, 1.05, 1.0, 0.82, 1.12],
        "fraud_inject_rate": 8,   # every Nth transaction uses fraud actor
    },
    "peak": {
        "base_delay": 0.42,
        "jitter": [0.88, 1.0, 1.1, 0.8, 1.18],
        "fraud_inject_rate": 6,
    },
    "stress": {
        "base_delay": 0.3,
        "jitter": [0.85, 1.0, 1.14, 0.78, 1.05],
        "fraud_inject_rate": 4,
    },
    "attack": {
        "base_delay": 0.24,
        "jitter": [0.82, 0.98, 1.1, 0.8, 1.02],
        "fraud_inject_rate": 3,
    },
}

_FEED_CONNECTION_SEQ = 0


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _next_connection_namespace() -> str:
    global _FEED_CONNECTION_SEQ
    _FEED_CONNECTION_SEQ += 1
    return f"lf{_FEED_CONNECTION_SEQ:04d}"


def _ns_upi(base_upi: str, namespace: str) -> str:
    local, _, domain = base_upi.partition("@")
    if not domain:
        return f"{base_upi}_{namespace}@upi"
    return f"{local}_{namespace}@{domain}"


def _market_phase(hour: int) -> str:
    if 8 <= hour <= 11:
        return "salary-window"
    if 12 <= hour <= 15:
        return "merchant-peak"
    if 18 <= hour <= 22:
        return "evening-peak"
    if 0 <= hour <= 5:
        return "night-risk"
    return "steady"


def _hourly_demand_multiplier(hour: int) -> float:
    if 8 <= hour <= 11 or 18 <= hour <= 22:
        return 1.35
    if 12 <= hour <= 15:
        return 1.15
    if 0 <= hour <= 5:
        return 0.58
    return 0.9


def _get_profile(websocket: WebSocket) -> tuple[str, float, float]:
    requested = (websocket.query_params.get("profile") or "normal").strip().lower()
    profile = requested if requested in PROFILE_SETTINGS else "normal"
    try:
        speed = float(websocket.query_params.get("speed") or "1.0")
    except ValueError:
        speed = 1.0
    speed = _clamp(speed, 0.25, 4.0)
    try:
        tps = float(websocket.query_params.get("tps") or "2.0")
    except ValueError:
        tps = 2.0
    tps = _clamp(tps, 1.0, 5.0)
    return profile, speed, tps


def _next_delay_seconds(seq: int, profile: str, speed: float, tps: float) -> float:
    now = datetime.now()
    cfg = PROFILE_SETTINGS[profile]
    jitter = cfg["jitter"][seq % len(cfg["jitter"])]
    demand = _hourly_demand_multiplier(now.hour)
    delay = cfg["base_delay"] * jitter / max(0.2, demand * speed)
    min_delay = 1.0 / _clamp(tps, 1.0, 5.0)
    return _clamp(delay, min_delay, 1.0)


def _txn_amount(seq: int, profile: str, hour: int) -> float:
    """Amount distribution recalibrated: fewer micro-payments, more mid-range."""
    pattern = (seq * 7 + hour * 3) % 100

    # Recalibrated: Rs.500-5000 (45%), Rs.5000-25000 (35%), Rs.25000-100000 (15%), Rs.100000+ (5%)
    if pattern < 45:
        low, high = 500, 5000
    elif pattern < 80:
        low, high = 5000, 25000
    elif pattern < 95:
        low, high = 25000, 100000
    else:
        low, high = 100000, 300000

    if profile == "normal":
        high = min(high, 80000)
    elif profile == "peak":
        high = min(high, 120000)

    if profile == "stress" and pattern >= 80:
        high = min(300000, int(high * 1.45))
    if profile == "attack":
        high = min(400000, int(high * 1.6))

    span = max(1, high - low)
    amount = low + ((seq * 137 + hour * 29) % span)
    return round(float(amount), 2)


def _generate_txn(seq: int, profile: str, namespace: str = "") -> dict:
    """Generate transaction with fraud pattern injection."""
    now = datetime.now()
    hour = now.hour
    cfg = PROFILE_SETTINGS[profile]
    fraud_rate = cfg.get("fraud_inject_rate", 8)

    sender = _ns_upi(SENDERS[seq % len(SENDERS)], namespace) if namespace else SENDERS[seq % len(SENDERS)]
    txn_type = TXN_TYPES[(seq + hour) % len(TXN_TYPES)]
    base_device = DEVICES[(seq * 5 + hour) % len(DEVICES)]
    device = f"{base_device}_{namespace}" if namespace else base_device

    if txn_type in ("purchase", "bill_payment", "recharge"):
        base_receiver = MERCHANTS[(seq * 11 + hour) % len(MERCHANTS)]
    else:
        base_receiver = PEERS[(seq * 7 + hour * 2) % len(PEERS)]
    receiver = _ns_upi(base_receiver, namespace) if namespace else base_receiver

    amount = _txn_amount(seq, profile, hour)
    extra = {}

    # ─── Fraud Pattern Injection ─────────────────────────────────

    # Every Nth transaction: use a bad actor sender/receiver
    if seq % fraud_rate == 0:
        sender = FRAUD_SENDERS[seq % len(FRAUD_SENDERS)]
        receiver = FRAUD_RECEIVERS[seq % len(FRAUD_RECEIVERS)]
        txn_type = "transfer"
        amount = max(amount, 20000 + (seq * 137 % 80000))
        device = f"DEV_NEW_{seq % 1000:03d}"
        extra["_fraud_injected"] = True

    # seq % 7: New device for same sender (SIM swap signal)
    if seq % 7 == 0:
        device = f"DEV_NEW_{seq % 999:03d}"

    # seq % 11: Night timestamp override (2:30 AM)
    if seq % 11 == 0:
        hour_override = 2
        ts = now.replace(hour=hour_override, minute=30)
        extra["timestamp"] = ts.isoformat()
        if amount < 8000:
            amount = 8000 + (seq * 43 % 42000)

    # seq % 13: High amount + new device (strong SIM swap)
    if seq % 13 == 0:
        amount = max(amount, 50000 + (seq * 71 % 100000))
        device = f"DEV_NEW_{seq % 800:03d}"

    # seq % 17: Same sender 3 consecutive times (velocity attack simulation)
    if seq % 17 == 0:
        sender = FRAUD_SENDERS[(seq // 17) % len(FRAUD_SENDERS)]
        txn_type = "transfer"

    # seq % 19: Receiver with high-entropy VPA (mule pattern)
    if seq % 19 == 0:
        entropy_id = f"xk{seq % 9999:04d}temp{(seq * 31) % 99:02d}"
        receiver = f"{entropy_id}@ybl"

    # seq % 23: Impossible travel — inject coordinates from distant cities
    if seq % 23 == 0:
        city1 = CITIES[seq % len(CITIES)]
        city2 = CITIES[(seq + 3) % len(CITIES)]
        extra["sender_location_lat"] = city2["lat"]
        extra["sender_location_lon"] = city2["lon"]
        extra["_previous_city"] = city1["name"]

    # seq % 29: Self-transfer attempt
    if seq % 29 == 0:
        receiver = sender

    # seq % 31: 5-transaction burst from fraud sender
    if seq % 31 == 0:
        sender = FRAUD_SENDERS[(seq // 31) % len(FRAUD_SENDERS)]
        receiver = FRAUD_RECEIVERS[(seq // 31 + 1) % len(FRAUD_RECEIVERS)]
        amount = max(amount, 4500 + (seq * 37 % 500))  # Just under Rs.5000 (smurfing)
        txn_type = "transfer"

    txn = {
        "sender_upi": sender,
        "receiver_upi": receiver,
        "amount": round(amount, 2),
        "transaction_type": txn_type,
        "sender_device_id": device,
        "timestamp": extra.get("timestamp", now.isoformat()),
    }

    # Pass through any extra location data
    if "sender_location_lat" in extra:
        txn["sender_location_lat"] = extra["sender_location_lat"]
        txn["sender_location_lon"] = extra["sender_location_lon"]

    return txn


async def live_feed_handler(websocket: WebSocket, pipeline_fn):
    """Send simulated transaction+prediction events using bounded inter-arrival timing."""
    await websocket.accept()
    seq = 0
    profile, speed, tps = _get_profile(websocket)
    namespace = _next_connection_namespace()

    await websocket.send_json(
        {
            "event": "feed_started",
            "profile": profile,
            "speed": speed,
            "tps": tps,
            "namespace": namespace,
            "timestamp": datetime.now().isoformat(),
        }
    )

    try:
        while True:
            txn = _generate_txn(seq, profile, namespace=namespace)
            try:
                result = pipeline_fn(txn)
                msg = {
                    "seq": seq,
                    "profile": profile,
                    "market_phase": _market_phase(datetime.now().hour),
                    "transaction": txn,
                    "prediction": result,
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                msg = {
                    "seq": seq,
                    "profile": profile,
                    "transaction": txn,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

            await websocket.send_json(msg)
            seq += 1
            await asyncio.sleep(_next_delay_seconds(seq, profile, speed, tps))
    except WebSocketDisconnect:
        pass
