"""Integration tests for API endpoints using FastAPI TestClient."""

import pytest
import sys
import os

# Set dev mode env vars before importing the app
os.environ["AUTH_REQUIRED"] = "false"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-ci-only-32chars"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client():
    """Create test client with mocked model loading."""
    with patch("backend.app.main.load_all_models"):
        with patch("backend.app.main.predict_fraud") as mock_predict:
            mock_predict.return_value = {
                "ensemble_score": 0.15,
                "individual_scores": {"xgboost": 0.15},
                "models_used": ["xgboost"],
                "weights": {"xgboost": 1.0},
            }
            from backend.app.main import app
            yield TestClient(app)


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "model_version" in data
    assert "timestamp" in data


def test_predict_legitimate(client):
    r = client.post("/predict", json={
        "sender_upi": "alice@upi",
        "receiver_upi": "bob@upi",
        "amount": 500,
        "transaction_type": "purchase",
        "sender_device_id": "DEV_001",
    })
    assert r.status_code == 200
    data = r.json()
    assert "fraud_score" in data
    assert "decision" in data
    assert data["model_version"] == "2.0.0"


def test_predict_self_transfer_blocked(client):
    r = client.post("/predict", json={
        "sender_upi": "same@upi",
        "receiver_upi": "same@upi",
        "amount": 1000,
        "transaction_type": "transfer",
        "sender_device_id": "DEV_001",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["decision"] == "BLOCK"
    rule_names = [rt["rule_name"] for rt in data["rules_triggered"]]
    assert "SELF_TRANSFER" in rule_names


def test_predict_validation_error(client):
    r = client.post("/predict", json={
        "sender_upi": "a@upi",
        "receiver_upi": "b@upi",
        "amount": -100,
        "transaction_type": "purchase",
        "sender_device_id": "DEV",
    })
    assert r.status_code == 422


def test_predict_missing_fields(client):
    r = client.post("/predict", json={"sender_upi": "a@upi"})
    assert r.status_code == 422


def test_transactions_endpoint(client):
    r = client.get("/transactions?limit=5")
    assert r.status_code == 200


def test_monitoring_stats(client):
    r = client.get("/monitoring/stats")
    assert r.status_code == 200


def test_monitoring_latency(client):
    r = client.get("/monitoring/latency")
    assert r.status_code == 200
    data = r.json()
    assert "avg_latency_ms" in data
    assert "max_latency_ms" in data


def test_monitoring_graph(client):
    r = client.get("/monitoring/graph")
    assert r.status_code == 200
    data = r.json()
    assert "total_nodes" in data
