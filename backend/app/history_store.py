"""
Sender History Store — Redis with automatic DB fallback.

If Redis is available → uses Redis (fast, survives restarts, TTL-based expiry).
If Redis is unavailable → falls back to in-memory dict + DB hydration.

This is transparent to feature_extract.py — it just calls get_sender_history().
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Try Redis connection
_redis_client = None
_use_redis = False
REDIS_TTL_SECONDS = 7 * 24 * 3600  # 7 days

try:
    import redis
    _redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True,
                                socket_connect_timeout=2)
    _redis_client.ping()
    _use_redis = True
    logger.info("[OK] Redis connected -- using Redis for sender history")
except Exception:
    logger.info("[WARN] Redis unavailable -- using in-memory dict with DB fallback")

# In-memory fallback
_memory_store: dict = {}


def _redis_key(sender: str) -> str:
    return f"sender_history:{sender}"


def get_sender_history(sender: str) -> dict:
    """Get sender history from Redis or memory."""
    if _use_redis:
        try:
            raw = _redis_client.get(_redis_key(sender))
            if raw:
                data = json.loads(raw)
                # Convert stored timestamps back to datetime tuples
                txns = [(datetime.fromisoformat(t["ts"]), t["amt"], t["dev"], t["recv"])
                        for t in data.get("transactions", [])]
                return {
                    "transactions": txns,
                    "devices": set(data.get("devices", [])),
                    "receivers": set(data.get("receivers", [])),
                }
        except Exception as e:
            logger.warning(f"Redis read failed for {sender}: {e}")

    # Fallback to memory
    if sender not in _memory_store:
        _memory_store[sender] = {
            "transactions": [],
            "devices": set(),
            "receivers": set(),
        }
    return _memory_store[sender]


def save_sender_history(sender: str, hist: dict):
    """Persist sender history to Redis (with TTL) or keep in memory."""
    # Always update memory
    _memory_store[sender] = hist

    if _use_redis:
        try:
            # Serialize for Redis
            data = {
                "transactions": [
                    {"ts": t.isoformat(), "amt": a, "dev": d, "recv": r}
                    for t, a, d, r in hist["transactions"]
                ],
                "devices": list(hist.get("devices", set())),
                "receivers": list(hist.get("receivers", set())),
            }
            _redis_client.setex(_redis_key(sender), REDIS_TTL_SECONDS, json.dumps(data))
        except Exception as e:
            logger.warning(f"Redis write failed for {sender}: {e}")


def hydrate_from_db(records: list):
    """Load historical transactions into the store on startup."""
    count = 0
    for r in records:
        sender = r["sender_upi"]
        hist = get_sender_history(sender)
        try:
            ts = datetime.fromisoformat(r["timestamp"])
        except (ValueError, TypeError):
            ts = datetime.utcnow()
        hist["transactions"].append((ts, r["amount"], r["device_id"], r["receiver_upi"]))
        hist["devices"].add(r["device_id"])
        hist["receivers"].add(r["receiver_upi"])
        save_sender_history(sender, hist)
        count += 1
    logger.info(f"Hydrated {count} transactions for {len(_memory_store)} senders "
                f"({'Redis' if _use_redis else 'memory'})")
    return count


def is_redis_active() -> bool:
    return _use_redis


def get_store_stats() -> dict:
    return {
        "backend": "redis" if _use_redis else "memory",
        "senders_tracked": len(_memory_store),
    }
