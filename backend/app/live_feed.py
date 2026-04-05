"""WebSocket live feed with bounded realistic traffic cadence (1-5 TPS)."""

import asyncio
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect


SENDERS = [f"user_{i:04d}@upi" for i in range(1200)]
MERCHANTS = [f"merchant_{i:04d}@upi" for i in range(300)]
PEERS = [f"friend_{i:04d}@upi" for i in range(220)]
DEVICES = [f"DEV_{i:04d}" for i in range(1200)]
TXN_TYPES = ["purchase", "transfer", "bill_payment", "recharge"]

PROFILE_SETTINGS = {
    "normal": {
        "base_delay": 0.7,
        "jitter": [0.9, 1.05, 1.0, 0.82, 1.12],
    },
    "peak": {
        "base_delay": 0.42,
        "jitter": [0.88, 1.0, 1.1, 0.8, 1.18],
    },
    "stress": {
        "base_delay": 0.3,
        "jitter": [0.85, 1.0, 1.14, 0.78, 1.05],
    },
    "attack": {
        "base_delay": 0.24,
        "jitter": [0.82, 0.98, 1.1, 0.8, 1.02],
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
    # Enforce realistic bounded traffic: 1-5 transactions/sec.
    min_delay = 1.0 / _clamp(tps, 1.0, 5.0)
    return _clamp(delay, min_delay, 1.0)


def _txn_amount(seq: int, profile: str, hour: int) -> float:
    pattern = (seq * 7 + hour * 3) % 100
    if pattern < 56:
        low, high = 50, 2600
    elif pattern < 84:
        low, high = 2600, 12000
    elif pattern < 97:
        low, high = 12000, 55000
    else:
        low, high = 55000, 180000

    # Keep normal traffic mostly below hard-block thresholds.
    if profile == "normal":
        high = min(high, 60000)
    elif profile == "peak":
        high = min(high, 95000)

    if profile == "peak" and pattern >= 84:
        high = min(110000, int(high * 1.1))
    if profile == "stress" and pattern >= 84:
        high = min(300000, int(high * 1.45))
    if profile == "attack":
        high = min(350000, int(high * 1.6))

    span = max(1, high - low)
    amount = low + ((seq * 137 + hour * 29) % span)
    return round(float(amount), 2)


def _generate_txn(seq: int, profile: str, namespace: str = "") -> dict:
    now = datetime.now()
    hour = now.hour

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

    # Deterministic anomaly injection to keep the stream operationally useful.
    if seq % 41 == 0:
        receiver = sender
    if profile in ("peak", "stress") and seq % 17 == 0:
        device = f"DEV_NEW_{seq % 1000:03d}"
    if profile == "stress" and seq % 13 == 0:
        amount = round(min(400000.0, amount * 1.7), 2)

    return {
        "sender_upi": sender,
        "receiver_upi": receiver,
        "amount": amount,
        "transaction_type": txn_type,
        "sender_device_id": device,
        "timestamp": now.isoformat(),
    }


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
