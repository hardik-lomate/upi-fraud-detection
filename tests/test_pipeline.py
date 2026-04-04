"""Tests for pipeline steps — each step tested in isolation."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "app"))

from feature_contract import FEATURE_COLUMNS
from backend.app.pipeline import (
    PipelineContext, step_validate, step_extract_features,
    step_rules_engine, step_ml_predict, step_decide,
)
from backend.app.rules_engine import evaluate_rules, get_rule_decision


@pytest.fixture
def base_txn():
    return {
        "sender_upi": "user123@upi",
        "receiver_upi": "merchant456@upi",
        "amount": 500.0,
        "transaction_type": "purchase",
        "sender_device_id": "DEV_001",
        "timestamp": "2026-04-03T14:30:00",
    }


@pytest.fixture
def base_features():
    return {
        "amount": 500.0, "hour": 14, "day_of_week": 4,
        "is_night": 0, "is_weekend": 0, "txn_type_encoded": 1,
        "sender_txn_count_24h": 3, "sender_avg_amount": 450.0,
        "sender_std_amount": 100.0, "amount_deviation": 0.5,
        "sender_unique_receivers_24h": 2, "is_new_device": 0,
        "is_new_receiver": 0, "_sender_txn_count_1h": 1,
    }


# === Step: Validate ===

def test_step_validate_generates_txn_id(base_txn):
    ctx = PipelineContext()
    ctx = step_validate(ctx, base_txn)
    assert ctx.txn_id.startswith("TXN_")
    assert ctx.timestamp == "2026-04-03T14:30:00"
    assert "validate" in ctx.processing_steps


def test_step_validate_preserves_txn_id(base_txn):
    base_txn["transaction_id"] = "TXN_001"
    ctx = PipelineContext()
    ctx = step_validate(ctx, base_txn)
    assert ctx.txn_id == "TXN_001"


# === Step: Features ===

def test_step_features_contract_check(base_features):
    ctx = PipelineContext()
    ctx.raw_txn = {"sender_upi": "a@upi", "receiver_upi": "b@upi", "amount": 100,
                   "transaction_type": "purchase", "sender_device_id": "DEV", "timestamp": "2026-01-01T12:00:00"}

    def mock_extract(txn):
        return base_features

    ctx = step_extract_features(ctx, mock_extract)
    assert "features" in ctx.processing_steps
    for col in FEATURE_COLUMNS:
        assert col in ctx.features


def test_step_features_missing_column_reports_error():
    ctx = PipelineContext()
    ctx.raw_txn = {}

    def bad_extract(txn):
        return {"amount": 100}  # Missing most columns

    ctx = step_extract_features(ctx, bad_extract)
    assert len(ctx.errors) > 0
    assert "Feature contract violation" in ctx.errors[0]


# === Step: Rules ===

def test_step_rules_self_transfer(base_features):
    ctx = PipelineContext()
    ctx.raw_txn = {"sender_upi": "same@upi", "receiver_upi": "same@upi", "amount": 100,
                   "timestamp": "2026-01-01T12:00:00"}
    ctx.features = base_features
    ctx = step_rules_engine(ctx, evaluate_rules, get_rule_decision)
    assert ctx.rule_decision == "BLOCK"
    rule_names = [r.rule_name for r in ctx.rules_triggered]
    assert "SELF_TRANSFER" in rule_names


def test_step_rules_rapid_fire(base_features):
    ctx = PipelineContext()
    ctx.raw_txn = {"sender_upi": "a@upi", "receiver_upi": "b@upi", "amount": 100,
                   "timestamp": "2026-01-01T12:00:00"}
    ctx.features = {**base_features, "_sender_txn_count_1h": 15}
    ctx = step_rules_engine(ctx, evaluate_rules, get_rule_decision)
    rule_names = [r.rule_name for r in ctx.rules_triggered]
    assert "RAPID_FIRE_TRANSACTIONS" in rule_names


# === Step: Decide ===

def test_step_decide_rules_override_ml():
    ctx = PipelineContext()
    ctx.rule_decision = "BLOCK"
    ctx.fraud_score = 0.1  # Low ML score
    ctx.rules_triggered = [type("R", (), {"rule_name": "SELF_TRANSFER", "action": "BLOCK", "reason": "test"})()]
    ctx = step_decide(ctx)
    assert ctx.decision == "BLOCK"


def test_step_decide_ml_block():
    ctx = PipelineContext()
    ctx.rule_decision = None
    ctx.fraud_score = 0.85
    ctx = step_decide(ctx)
    assert ctx.decision == "REQUIRE_BIOMETRIC"
    assert ctx.risk_level == "HIGH"


def test_step_decide_ml_allow():
    ctx = PipelineContext()
    ctx.rule_decision = None
    ctx.fraud_score = 0.05
    ctx = step_decide(ctx)
    assert ctx.decision == "ALLOW"
    assert ctx.risk_level == "LOW"


# === Step: ML Predict ===

def test_step_ml_predict_mock(base_features):
    ctx = PipelineContext()
    ctx.features = base_features

    def mock_predict(features):
        return {"ensemble_score": 0.42, "individual_scores": {"xgboost": 0.4},
                "models_used": ["xgboost"], "weights": {"xgboost": 1.0}}

    ctx = step_ml_predict(ctx, mock_predict)
    assert ctx.fraud_score == 0.42
    assert "xgboost" in ctx.models_used
