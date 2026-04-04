import hashlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _hash_bucket(transaction_id: str) -> int:
    return int(hashlib.sha256(transaction_id.encode()).hexdigest(), 16) % 100


def _find_txn_id(prefix: str, predicate, max_tries: int = 5000) -> str:
    for i in range(max_tries):
        txn_id = f"{prefix}_{i}"
        if predicate(txn_id):
            return txn_id
    raise AssertionError("Unable to find a suitable transaction_id for deterministic biometric test")


@pytest.fixture
def app_client():
    from backend.app.main import app

    with patch("backend.app.main.load_all_models"):
        yield TestClient(app)


def test_biometric_verify_success_updates_transaction(app_client):
    from backend.app.database import SessionLocal, TransactionRecord

    # Fraud score triggers VERIFY, but still gives a high pass probability.
    fraud_score = 0.35

    # Medium-risk increments fraud_count by 1, which reduces pass_probability by 0.15.
    # Base for <0.5 is 0.95 => effective threshold ~80%.
    txn_id = _find_txn_id("TXN_BIO_PASS", lambda t: _hash_bucket(t) < 80)

    with patch("backend.app.main.predict_fraud") as mock_predict:
        mock_predict.return_value = {
            "ensemble_score": fraud_score,
            "individual_scores": {"xgboost": fraud_score},
            "models_used": ["xgboost"],
            "weights": {"xgboost": 1.0},
        }

        r = app_client.post(
            "/predict",
            json={
                "transaction_id": txn_id,
                "sender_upi": "bio_pass@upi",
                "receiver_upi": "merchant@upi",
                "amount": 1200,
                "transaction_type": "purchase",
                "sender_device_id": "DEV_TEST",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["decision"] == "VERIFY"
        assert data["status"] == "PENDING_VERIFICATION"

        vr = app_client.post("/verify-biometric", json={"transaction_id": txn_id, "method": "fingerprint"})
        assert vr.status_code == 200
        vdata = vr.json()
        assert vdata["verification_status"] == "VERIFIED"
        assert vdata["final_decision"] == "ALLOW"

    db = SessionLocal()
    try:
        rec = db.query(TransactionRecord).filter(TransactionRecord.transaction_id == txn_id).first()
        assert rec is not None
        assert rec.status == "VERIFIED"
        assert rec.decision == "ALLOW"
    finally:
        db.close()


def test_biometric_verify_failure_blocks_and_increments_history(app_client):
    from backend.app.database import SessionLocal, TransactionRecord, FraudHistory

    fraud_score = 0.35

    # Pick an id that will FAIL for the ~80% threshold.
    txn_id = _find_txn_id("TXN_BIO_FAIL", lambda t: _hash_bucket(t) >= 80)

    with patch("backend.app.main.predict_fraud") as mock_predict:
        mock_predict.return_value = {
            "ensemble_score": fraud_score,
            "individual_scores": {"xgboost": fraud_score},
            "models_used": ["xgboost"],
            "weights": {"xgboost": 1.0},
        }

        r = app_client.post(
            "/predict",
            json={
                "transaction_id": txn_id,
                "sender_upi": "bio_fail@upi",
                "receiver_upi": "merchant@upi",
                "amount": 1300,
                "transaction_type": "purchase",
                "sender_device_id": "DEV_TEST",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["decision"] == "VERIFY"
        assert data["status"] == "PENDING_VERIFICATION"

        vr = app_client.post("/verify-biometric", json={"transaction_id": txn_id, "method": "face"})
        assert vr.status_code == 200
        vdata = vr.json()
        assert vdata["verification_status"] == "FAILED"
        assert vdata["final_decision"] == "BLOCK"

    db = SessionLocal()
    try:
        rec = db.query(TransactionRecord).filter(TransactionRecord.transaction_id == txn_id).first()
        assert rec is not None
        assert rec.status == "BLOCKED"
        assert rec.decision == "BLOCK"

        hist = db.query(FraudHistory).filter(FraudHistory.upi_id == "bio_fail@upi").first()
        assert hist is not None
        assert (hist.fraud_count or 0) >= 2  # 1 for step-up + 1 for biometric failure
        assert (hist.block_count or 0) >= 1
    finally:
        db.close()


def test_high_risk_repeat_offender_is_blocked(app_client):
    from backend.app.database import increment_fraud_count

    sender = "repeat_offender@upi"
    increment_fraud_count(sender, was_blocked=False)

    fraud_score = 0.95

    with patch("backend.app.main.predict_fraud") as mock_predict:
        mock_predict.return_value = {
            "ensemble_score": fraud_score,
            "individual_scores": {"xgboost": fraud_score},
            "models_used": ["xgboost"],
            "weights": {"xgboost": 1.0},
        }

        r = app_client.post(
            "/predict",
            json={
                "transaction_id": "TXN_REPEAT_BLOCK",
                "sender_upi": sender,
                "receiver_upi": "merchant@upi",
                "amount": 5000,
                "transaction_type": "purchase",
                "sender_device_id": "DEV_TEST",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["decision"] == "BLOCK"
        assert data["status"] == "BLOCKED"
