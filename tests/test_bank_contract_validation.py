"""Bank-side contract validation tests.

These tests lock down the demo contract:
- deterministic threshold decisions
- normalized weighted risk composition
- strict linear pipeline order with all core modules contributing
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from feature_contract import FEATURE_COLUMNS
from backend.app.decision_engine import make_bank_decision
from backend.app.pipeline import run_pipeline
from backend.app.risk_engine import combine_risk_scores


class _GraphStub:
    def add_transaction(self, sender, receiver, amount, timestamp, transaction_id=None):
        return None

    def get_node_features(self, node):
        return {
            "in_degree": 2,
            "cycle_count": 1,
            "is_mule_suspect": False,
        }


def _feature_payload() -> dict:
    payload = {c: 0.0 for c in FEATURE_COLUMNS}
    payload.update(
        {
            "amount": 25000.0,
            "hour": 2,
            "is_high_risk_hour": 1,
            "is_new_device": 1,
            "is_new_receiver": 1,
            "sender_txn_count_1min": 3,
            "is_impossible_travel": 1,
            "receiver_fraud_flag_count": 2,
        }
    )
    return payload


def test_bank_decision_threshold_contract():
    assert make_bank_decision(0.81)[0] == "BLOCK"
    assert make_bank_decision(0.80)[0] == "STEP-UP"
    assert make_bank_decision(0.61)[0] == "STEP-UP"
    assert make_bank_decision(0.60)[0] == "ALLOW"
    assert make_bank_decision(0.20)[0] == "ALLOW"


def test_risk_composition_normalized_and_explainable():
    payload = combine_risk_scores(
        rules_score=1.4,
        ml_score=-0.2,
        behavior_score=0.5,
        graph_score=2.0,
        weights={"rules": 3, "ml": 4, "behavior": 2, "graph": 1},
    )

    assert 0.0 <= payload["risk_score"] <= 1.0
    assert payload["components"]["rules_score"] == 1.0
    assert payload["components"]["ml_score"] == 0.0
    assert payload["components"]["behavior_score"] == 0.5
    assert payload["components"]["graph_score"] == 1.0

    weights_sum = sum(payload["weights"].values())
    assert weights_sum == pytest.approx(1.0, abs=1e-6)

    contrib_sum = sum(payload["contributions"].values())
    assert contrib_sum == pytest.approx(payload["risk_score"], abs=1e-3)
    assert "weight_justification" in payload
    assert "input_normalization" in payload


def test_bank_pipeline_linear_order_and_component_usage():
    txn = {
        "sender_upi": "victim@upi",
        "receiver_upi": "merchant@upi",
        "amount": 25000.0,
        "transaction_type": "transfer",
        "timestamp": "2026-04-08T02:15:00",
        "sender_device_id": "DEV_X",
    }

    def extract_fn(_txn):
        return _feature_payload()

    def evaluate_rules_fn(_enriched):
        return []

    def get_rule_decision_fn(_rules):
        return None

    def predict_fn(_features):
        return {
            "ensemble_score": 0.9,
            "individual_scores": {"xgboost": 0.9},
            "models_used": ["xgboost"],
        }

    def explain_fn(_features, _feature_columns, top_n=8):
        return ["Amount", "Is High Risk Hour"]

    def format_reasons_fn(explanations):
        return [str(x) for x in explanations]

    def check_device_fn(_txn, _features):
        return []

    def update_device_fn(_txn):
        return None

    def behavior_fn(sender_upi, features, current_txn):
        return {
            "behavior_score": 0.2,
            "reasons": ["Behavior drift detected"],
            "drift_score": 0.2,
            "pattern_score": 0.2,
            "context_score": 0.2,
        }

    def graph_score_fn(graph_info):
        return {
            "graph_score": 0.3,
            "reasons": ["Network signal risk"],
            "components": {"in_degree": float(graph_info.get("in_degree", 0))},
        }

    def rules_score_fn(rule_decision, rules_triggered):
        return 0.1

    ctx = run_pipeline(
        txn_dict=txn,
        extract_fn=extract_fn,
        evaluate_rules_fn=evaluate_rules_fn,
        get_rule_decision_fn=get_rule_decision_fn,
        predict_fn=predict_fn,
        explain_fn=explain_fn,
        format_reasons_fn=format_reasons_fn,
        check_device_fn=check_device_fn,
        update_device_fn=update_device_fn,
        sender_history=None,
        graph=_GraphStub(),
        behavior_fn=behavior_fn,
        graph_score_fn=graph_score_fn,
        rules_score_fn=rules_score_fn,
        combine_risk_fn=combine_risk_scores,
        audit_fn=lambda _ctx: None,
        decision_mode="bank",
    )

    assert ctx.errors == []
    assert ctx.bank_risk_score == pytest.approx(0.4432, abs=1e-6)
    assert ctx.bank_decision == "ALLOW"

    expected_steps = [
        "validate",
        "feature_validation",
        "features",
        "rules",
        "ml_predict",
        "device_check",
        "behavior_analysis",
        "advanced_signals",
        "graph_analysis",
        "risk_scoring",
        "decide",
        "shap_explain",
        "user_warning",
        "audit_logging",
    ]
    assert ctx.processing_steps == expected_steps

    assert ctx.risk_components.get("contributions") is not None
    assert ctx.risk_components.get("weights") is not None
    assert {"rules_score", "ml_score", "behavior_score", "graph_score"}.issubset(set(ctx.risk_components.keys()))
    assert set(ctx.risk_components.get("weights", {}).keys()) == {
        "rules",
        "ml",
        "behavior",
        "graph",
    }
