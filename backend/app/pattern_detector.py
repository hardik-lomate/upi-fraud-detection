"""Pattern detector for scripted/bot-like fraud behavior."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta


def _parse_ts(value):
    if isinstance(value, datetime):
        return value
    text = str(value or "")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def detect_round_amount_burst(transactions: list[dict]) -> dict:
    # 5+ transactions with amount multiple of 1000 within 10 minutes.
    rows = sorted(transactions, key=lambda t: _parse_ts(t.get("timestamp")))
    for i in range(len(rows)):
        start = _parse_ts(rows[i].get("timestamp"))
        end = start + timedelta(minutes=10)
        subset = [r for r in rows if start <= _parse_ts(r.get("timestamp")) <= end]
        count = sum(1 for r in subset if int(float(r.get("amount", 0) or 0)) % 1000 == 0)
        if count >= 5:
            return {"name": "ROUND_AMOUNT_BURST", "matched": True, "count": count}
    return {"name": "ROUND_AMOUNT_BURST", "matched": False, "count": 0}


def detect_same_receiver_multi_sender(transactions: list[dict]) -> dict:
    # Same receiver receives from 3+ different senders in 5 minutes.
    rows = sorted(transactions, key=lambda t: _parse_ts(t.get("timestamp")))
    for i in range(len(rows)):
        start = _parse_ts(rows[i].get("timestamp"))
        end = start + timedelta(minutes=5)
        receiver_map = defaultdict(set)
        for r in rows:
            ts = _parse_ts(r.get("timestamp"))
            if start <= ts <= end:
                receiver = str(r.get("receiver_upi") or "").lower()
                sender = str(r.get("sender_upi") or "").lower()
                if receiver and sender:
                    receiver_map[receiver].add(sender)
        for receiver, senders in receiver_map.items():
            if len(senders) >= 3:
                return {
                    "name": "SAME_RECEIVER_MULTI_SENDER",
                    "matched": True,
                    "receiver_upi": receiver,
                    "unique_senders": len(senders),
                }
    return {"name": "SAME_RECEIVER_MULTI_SENDER", "matched": False}


def detect_amount_increment_pattern(transactions: list[dict]) -> dict:
    # Increasing by fixed step e.g. 1000, 2000, 3000...
    amts = [float(t.get("amount", 0) or 0) for t in sorted(transactions, key=lambda t: _parse_ts(t.get("timestamp")))]
    if len(amts) < 4:
        return {"name": "AMOUNT_INCREMENT_PATTERN", "matched": False}
    diffs = [round(amts[i] - amts[i - 1], 2) for i in range(1, len(amts))]
    if len(set(diffs[-3:])) == 1 and diffs[-1] > 0:
        return {"name": "AMOUNT_INCREMENT_PATTERN", "matched": True, "step": diffs[-1]}
    return {"name": "AMOUNT_INCREMENT_PATTERN", "matched": False}


def detect_velocity_ramp(transactions: list[dict]) -> dict:
    # Transactions-per-minute doubling pattern.
    minute_bins = defaultdict(int)
    for txn in transactions:
        ts = _parse_ts(txn.get("timestamp"))
        minute_bins[ts.replace(second=0, microsecond=0)] += 1

    if len(minute_bins) < 3:
        return {"name": "VELOCITY_RAMP", "matched": False}

    counts = [minute_bins[k] for k in sorted(minute_bins.keys())]
    for i in range(2, len(counts)):
        if counts[i] >= 2 * max(1, counts[i - 1]) and counts[i - 1] >= 2 * max(1, counts[i - 2]):
            return {"name": "VELOCITY_RAMP", "matched": True, "window": counts[i - 2 : i + 1]}
    return {"name": "VELOCITY_RAMP", "matched": False}


def detect_fraud_patterns(transactions: list[dict]) -> list[dict]:
    detectors = [
        detect_round_amount_burst,
        detect_same_receiver_multi_sender,
        detect_amount_increment_pattern,
        detect_velocity_ramp,
    ]
    results = [detector(transactions) for detector in detectors]
    return [r for r in results if r.get("matched")]
