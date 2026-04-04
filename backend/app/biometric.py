"""
Biometric Verification Simulation — Step-up authentication for medium-risk transactions.

Simulates fingerprint/face verification with realistic success/failure logic.
Not random — uses rule-based decisions for demo predictability.
"""

import time
import hashlib
from datetime import datetime
from .database import (
    update_transaction_status, get_user_fraud_history,
    increment_fraud_count, SessionLocal, TransactionRecord,
)
from .history_store import get_sender_history, save_sender_history
import logging

logger = logging.getLogger(__name__)

# Simulated verification delay (seconds)
VERIFICATION_DELAY = 1.5


def _get_transaction(txn_id: str) -> dict:
    """Fetch transaction from DB."""
    db = SessionLocal()
    try:
        record = db.query(TransactionRecord).filter(
            TransactionRecord.transaction_id == txn_id
        ).first()
        if record:
            return {
                "transaction_id": record.transaction_id,
                "sender_upi": record.sender_upi,
                "amount": record.amount,
                "fraud_score": record.fraud_score,
                "status": record.status,
            }
        return None
    finally:
        db.close()


def verify_biometric(transaction_id: str, method: str = "fingerprint") -> dict:
    """
    Simulate biometric verification for a pending transaction.

    Logic (deterministic for demo):
    - Fraud score < 0.5: always passes (legitimate user, minor flag)
    - Fraud score 0.5-0.7: 80% pass rate
    - Fraud score > 0.7: 40% pass rate (high risk, likely fail)
    - User with fraud history: reduce pass rate by 20%

    Uses transaction_id hash for reproducible results in demos.
    """
    # Simulate processing time
    time.sleep(VERIFICATION_DELAY)

    txn = _get_transaction(transaction_id)
    if not txn:
        return {
            "transaction_id": transaction_id,
            "verification_status": "ERROR",
            "message": "Transaction not found",
            "method": method,
        }

    if txn["status"] != "PENDING_VERIFICATION":
        return {
            "transaction_id": transaction_id,
            "verification_status": "ERROR",
            "message": f"Transaction is not pending verification (status: {txn['status']})",
            "method": method,
        }

    fraud_score = txn["fraud_score"]
    sender = txn["sender_upi"]
    fraud_hist = get_user_fraud_history(sender)

    # Calculate pass probability
    if fraud_score < 0.5:
        pass_probability = 0.95
    elif fraud_score < 0.7:
        pass_probability = 0.80
    else:
        pass_probability = 0.40

    # Reduce probability for users with fraud history
    if fraud_hist["fraud_count"] >= 3:
        pass_probability -= 0.30
    elif fraud_hist["fraud_count"] >= 1:
        pass_probability -= 0.15

    pass_probability = max(0.1, min(1.0, pass_probability))

    # Deterministic result based on txn_id hash (reproducible for demos)
    hash_val = int(hashlib.sha256(transaction_id.encode()).hexdigest(), 16) % 100
    passed = hash_val < (pass_probability * 100)

    if passed:
        # Biometric verified — approve transaction
        update_transaction_status(transaction_id, "VERIFIED", "ALLOW")
        try:
            hist = get_sender_history(sender)
            hist["last_verified_at"] = txn.get("timestamp") or datetime.utcnow().isoformat()
            save_sender_history(sender, hist)
        except Exception:
            pass
        logger.info(f"Biometric PASSED for {transaction_id} (score={fraud_score:.2f}, method={method})")
        return {
            "transaction_id": transaction_id,
            "verification_status": "VERIFIED",
            "final_decision": "ALLOW",
            "message": f"{method.title()} verification successful. Transaction approved.",
            "method": method,
            "fraud_score": fraud_score,
            "confidence": round(pass_probability * 100, 1),
        }
    else:
        # Biometric failed — block transaction
        update_transaction_status(transaction_id, "BLOCKED", "BLOCK")
        increment_fraud_count(sender, was_blocked=True)
        logger.info(f"Biometric FAILED for {transaction_id} (score={fraud_score:.2f}, method={method})")
        return {
            "transaction_id": transaction_id,
            "verification_status": "FAILED",
            "final_decision": "BLOCK",
            "message": f"{method.title()} verification failed. Transaction blocked for security.",
            "method": method,
            "fraud_score": fraud_score,
            "confidence": round((1 - pass_probability) * 100, 1),
        }
