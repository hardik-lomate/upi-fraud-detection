"""
Audit Trail — Immutable prediction logging with model versioning.
Every prediction decision is logged with full context for compliance.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import MODEL_VERSION

AUDIT_DIR = Path(__file__).resolve().parent.parent.parent / "audit_logs"
AUDIT_DIR.mkdir(exist_ok=True)


def _get_log_file() -> Path:
    """One log file per day for easy rotation."""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    return AUDIT_DIR / f"audit_{date_str}.jsonl"


def log_prediction(
    transaction_id: str,
    sender_upi: str,
    receiver_upi: str,
    amount: float,
    fraud_score: float,
    decision: str,
    risk_level: str,
    reasons: list[str],
    rules_triggered: list[str],
    model_version: str = MODEL_VERSION,
    features: dict = None,
    timestamp: str = None,
):
    """
    Append an immutable audit record. JSONL format — one JSON object per line.
    These logs should NEVER be modified or deleted (compliance requirement).
    """
    record = {
        "event_type": "PREDICTION",
        "event_time": datetime.utcnow().isoformat() + "Z",
        "model_version": model_version,
        "transaction_id": transaction_id,
        "sender_upi": sender_upi,
        "receiver_upi": receiver_upi,
        "amount": amount,
        "transaction_timestamp": timestamp,
        "fraud_score": fraud_score,
        "decision": decision,
        "risk_level": risk_level,
        "reasons": reasons,
        "rules_triggered": rules_triggered,
        "features": features or {},
    }

    log_file = _get_log_file()
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_auth_event(event: str, api_key_id: str, ip: str, details: str = ""):
    """Log authentication events (login, failed auth, rate limit hit)."""
    record = {
        "event_type": "AUTH",
        "event_time": datetime.utcnow().isoformat() + "Z",
        "event": event,
        "api_key_id": api_key_id,
        "ip_address": ip,
        "details": details,
    }
    log_file = _get_log_file()
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_audit_logs(date: str = None, limit: int = 100) -> list[dict]:
    """Read audit logs for a specific date (default: today)."""
    if date is None:
        date = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = AUDIT_DIR / f"audit_{date}.jsonl"
    if not log_file.exists():
        return []

    records = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
                if len(records) >= limit:
                    break
    return records
