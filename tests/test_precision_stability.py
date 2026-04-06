"""Precision and stability acceptance tests for the risk engine."""

import os
import sys
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_REQUIRED"] = "false"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-ci-only-32chars"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

RUN_SUFFIX = str(int(time.time() * 1000))


def _mock_predict(features: dict) -> dict:
    amount = float(features.get("amount") or 0)

    if amount >= 90000:
        score = 0.88
    elif amount >= 25000:
        score = 0.42
    elif amount >= 10000:
        score = 0.28
    else:
        score = 0.10

    return {
        "ensemble_score": score,
        "individual_scores": {
            "xgboost": round(min(1.0, score + 0.03), 4),
            "lightgbm": round(max(0.0, score - 0.02), 4),
            "isolation_forest": round(min(1.0, score + 0.01), 4),
        },
        "models_used": ["xgboost", "lightgbm", "isolation_forest"],
        "weights": {"xgboost": 0.45, "lightgbm": 0.35, "isolation_forest": 0.20},
    }


@pytest.fixture
def client():
    with patch("backend.app.main.load_all_models"):
        with patch("backend.app.main.predict_fraud", side_effect=_mock_predict):
            from backend.app.main import app
            yield TestClient(app)


def _post(client: TestClient, payload: dict) -> dict:
    r = client.post("/predict", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_normal_transaction_allow(client):
    _post(
        client,
        {
            "transaction_id": f"normal-seed-{RUN_SUFFIX}",
            "sender_upi": "normal_user_case@upi",
            "receiver_upi": "known_shop_case@upi",
            "amount": 500,
            "transaction_type": "purchase",
            "sender_device_id": "NORMAL_DEVICE_001",
            "timestamp": "2026-04-01T11:59:00",
        },
    )

    data = _post(
        client,
        {
            "transaction_id": f"normal-{RUN_SUFFIX}",
            "sender_upi": "normal_user_case@upi",
            "receiver_upi": "known_shop_case@upi",
            "amount": 900,
            "transaction_type": "purchase",
            "sender_device_id": "NORMAL_DEVICE_001",
            "timestamp": "2026-04-01T12:00:00",
        },
    )
    assert data["decision"] == "ALLOW"


def test_new_device_high_amount_verify(client):
    seed = {
        "transaction_id": f"verify-seed-1-{RUN_SUFFIX}",
        "sender_upi": "verify_case_1@upi",
        "receiver_upi": "trusted_receiver_1@upi",
        "amount": 600,
        "transaction_type": "purchase",
        "sender_device_id": "KNOWN_DEVICE_VERIFY_1",
        "timestamp": "2026-04-01T12:10:00",
    }
    _post(client, seed)

    data = _post(
        client,
        {
            "transaction_id": f"verify-high-1-{RUN_SUFFIX}",
            "sender_upi": "verify_case_1@upi",
            "receiver_upi": "trusted_receiver_1@upi",
            "amount": 35000,
            "transaction_type": "purchase",
            "sender_device_id": "NEW_DEVICE_VERIFY_1",
            "timestamp": "2026-04-01T12:11:00",
        },
    )
    assert data["decision"] == "VERIFY"


def test_trusted_receiver_high_amount_verify(client):
    seed = {
        "transaction_id": f"verify-seed-2-{RUN_SUFFIX}",
        "sender_upi": "verify_case_2@upi",
        "receiver_upi": "trusted_receiver_2@upi",
        "amount": 750,
        "transaction_type": "purchase",
        "sender_device_id": "KNOWN_DEVICE_VERIFY_2",
        "timestamp": "2026-04-01T12:20:00",
    }
    _post(client, seed)

    data = _post(
        client,
        {
            "transaction_id": f"verify-high-2-{RUN_SUFFIX}",
            "sender_upi": "verify_case_2@upi",
            "receiver_upi": "trusted_receiver_2@upi",
            "amount": 32000,
            "transaction_type": "purchase",
            "sender_device_id": "KNOWN_DEVICE_VERIFY_2",
            "timestamp": "2026-04-01T12:21:00",
        },
    )
    assert data["decision"] == "VERIFY"


def test_velocity_attack_block(client):
    final = None
    for i in range(10):
        final = _post(
            client,
            {
                "transaction_id": f"velocity-{RUN_SUFFIX}-{i}",
                "sender_upi": "velocity_attack_case@upi",
                "receiver_upi": f"velocity_target_{i}@upi",
                "amount": 1500,
                "transaction_type": "transfer",
                "sender_device_id": "VELO_DEVICE_001",
                "timestamp": "2026-04-01T13:00:00",
            },
        )

    assert final is not None
    assert final["decision"] == "BLOCK"


def test_repeated_suspicious_block(client):
    final = None
    for i in range(3):
        final = _post(
            client,
            {
                "transaction_id": f"repeat-{RUN_SUFFIX}-{i}",
                "sender_upi": "repeated_suspicious_case@upi",
                "receiver_upi": f"suspicious_receiver_{i}@upi",
                "amount": 95000,
                "transaction_type": "transfer",
                "sender_device_id": "SUSPICIOUS_DEVICE_001",
                "timestamp": "2026-04-01T02:30:00",
            },
        )

    assert final is not None
    assert final["decision"] == "BLOCK"


def test_same_input_twice_same_output(client):
    payload = {
        "transaction_id": f"determinism-{RUN_SUFFIX}",
        "sender_upi": "determinism_test_case@upi",
        "receiver_upi": "determinism_receiver_case@upi",
        "amount": 30000,
        "transaction_type": "transfer",
        "sender_device_id": "DETERMINISM_DEVICE_001",
        "timestamp": "2026-04-01T11:15:00",
    }

    first = _post(client, payload)
    second = _post(client, payload)
    assert first == second
