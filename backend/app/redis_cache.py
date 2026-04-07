"""Redis-backed cache for per-user feature snapshots."""

from __future__ import annotations

import json
import logging
import os

from .history_store import get_sender_history

logger = logging.getLogger(__name__)

try:
    import redis
except Exception:
    redis = None

_REDIS = None


def _get_client():
    global _REDIS
    if _REDIS is not None:
        return _REDIS
    if redis is None:
        return None

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        _REDIS = redis.from_url(redis_url, decode_responses=True)
        _REDIS.ping()
        return _REDIS
    except Exception as exc:
        logger.warning("Redis cache unavailable: %s", exc)
        _REDIS = None
        return None


def _key(sender_upi: str) -> str:
    return f"user_features:{sender_upi}"


async def get_user_features(sender_upi: str) -> dict | None:
    client = _get_client()
    if client is None:
        hist = get_sender_history(sender_upi)
        return hist if hist else None

    try:
        raw = client.get(_key(sender_upi))
        if not raw:
            hist = get_sender_history(sender_upi)
            return hist if hist else None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Redis get failed for %s: %s", sender_upi, exc)
        hist = get_sender_history(sender_upi)
        return hist if hist else None


async def set_user_features(sender_upi: str, features: dict, ttl_seconds: int = 3600) -> None:
    client = _get_client()
    if client is None:
        return

    try:
        client.setex(_key(sender_upi), int(ttl_seconds), json.dumps(features, default=str))
    except Exception as exc:
        logger.warning("Redis set failed for %s: %s", sender_upi, exc)


async def invalidate_user_features(sender_upi: str) -> None:
    client = _get_client()
    if client is None:
        return

    try:
        client.delete(_key(sender_upi))
    except Exception as exc:
        logger.warning("Redis delete failed for %s: %s", sender_upi, exc)
