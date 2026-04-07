"""Bank-side simulation and validation.

Runs 10 deterministic transactions (5 normal, 5 fraud-like) through the
single bank pipeline and prints risk_score + decision for each.

Run:
  python scripts/simulate_bank_validation.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.behavioral_engine import analyze_behavioral_risk
from backend.app.database import init_db
from backend.app.device_fingerprint import check_device_anomalies, update_device_history
from backend.app.explainability_engine import explain_prediction, format_reasons
from backend.app.feature_extract import extract_features
from backend.app.graph_engine import score_graph_risk
from backend.app.graph_features import get_graph
from backend.app.ml_model import predict_ml_probability
from backend.app.pipeline import run_pipeline
from backend.app.risk_engine import combine_risk_scores, compute_rules_score
from backend.app.rules_engine import evaluate_rules, get_rule_decision


def _txn(
    sender_upi: str,
    receiver_upi: str,
    amount: float,
    tx_type: str,
    ts: datetime,
    sender_device_id: str,
    lat: float,
    lon: float,
) -> dict:
    return {
        "sender_upi": sender_upi,
        "receiver_upi": receiver_upi,
        "amount": amount,
        "transaction_type": tx_type,
        "timestamp": ts.isoformat(),
        "sender_device_id": sender_device_id,
        "sender_location_lat": lat,
        "sender_location_lon": lon,
    }


def _cases() -> list[dict]:
    base = datetime(2026, 4, 8, 11, 0, 0)
    return [
        {
            "kind": "normal",
            "name": "Monthly bill payment",
            "txn": _txn(
                "n1.user@okicici", "electricity.board@okaxis", 1820.0, "bill_payment",
                base + timedelta(minutes=1), "PIXEL7_N1", 19.0760, 72.8777,
            ),
        },
        {
            "kind": "normal",
            "name": "Grocery payment",
            "txn": _txn(
                "n2.user@ybl", "freshmart@ybl", 640.0, "purchase",
                base + timedelta(minutes=3), "ONEPLUS_N2", 12.9716, 77.5946,
            ),
        },
        {
            "kind": "normal",
            "name": "Rent transfer",
            "txn": _txn(
                "n3.user@oksbi", "owner.rent@oksbi", 12000.0, "transfer",
                base + timedelta(minutes=5), "IPHONE_N3", 28.6139, 77.2090,
            ),
        },
        {
            "kind": "normal",
            "name": "Recharge",
            "txn": _txn(
                "n4.user@paytm", "airtel.recharge@paytm", 399.0, "recharge",
                base + timedelta(minutes=7), "SAMSUNG_N4", 22.5726, 88.3639,
            ),
        },
        {
            "kind": "normal",
            "name": "Known merchant transfer",
            "txn": _txn(
                "n1.user@okicici", "electricity.board@okaxis", 1780.0, "bill_payment",
                base + timedelta(minutes=9), "PIXEL7_N1", 19.0760, 72.8777,
            ),
        },
        {
            "kind": "fraud",
            "name": "Night high-value new receiver",
            "txn": _txn(
                "f1.victim@ybl", "urgent.kyc.verify@upi", 48000.0, "transfer",
                base.replace(hour=2, minute=12), "UNKNOWN_F1", 28.6139, 77.2090,
            ),
        },
        {
            "kind": "fraud",
            "name": "Rapid repeat transfer 1",
            "txn": _txn(
                "f2.victim@okaxis", "mule.collector@paytm", 9500.0, "transfer",
                base + timedelta(minutes=11), "UNKNOWN_F2", 13.0827, 80.2707,
            ),
        },
        {
            "kind": "fraud",
            "name": "Rapid repeat transfer 2",
            "txn": _txn(
                "f2.victim@okaxis", "mule.collector@paytm", 9600.0, "transfer",
                base + timedelta(minutes=11, seconds=20), "UNKNOWN_F2", 13.0827, 80.2707,
            ),
        },
        {
            "kind": "fraud",
            "name": "Impossible travel attempt",
            "txn": _txn(
                "f3.victim@oksbi", "suspicious.payout@upi", 22000.0, "transfer",
                base + timedelta(minutes=13), "NEW_F3", 19.0760, 72.8777,
            ),
        },
        {
            "kind": "fraud",
            "name": "Cross-bank risky transfer",
            "txn": _txn(
                "f3.victim@oksbi", "suspicious.payout@upi", 23500.0, "transfer",
                base + timedelta(minutes=18), "NEW_F3", 28.6139, 77.2090,
            ),
        },
    ]


def _run_bank_pipeline(txn: dict):
    return run_pipeline(
        txn_dict=txn,
        extract_fn=extract_features,
        evaluate_rules_fn=evaluate_rules,
        get_rule_decision_fn=get_rule_decision,
        predict_fn=predict_ml_probability,
        explain_fn=explain_prediction,
        format_reasons_fn=format_reasons,
        check_device_fn=check_device_anomalies,
        update_device_fn=update_device_history,
        sender_history=None,
        graph=get_graph(),
        behavior_fn=analyze_behavioral_risk,
        graph_score_fn=score_graph_risk,
        rules_score_fn=compute_rules_score,
        combine_risk_fn=combine_risk_scores,
        audit_fn=None,
        decision_mode="bank",
    )


def main() -> None:
    init_db()

    results = []
    print("BANK-SIDE SIMULATION (5 normal + 5 fraud-like)")
    print("=" * 120)

    for idx, case in enumerate(_cases(), start=1):
        ctx = _run_bank_pipeline(case["txn"])
        risk_score = float(ctx.bank_risk_score or ctx.risk_score or 0.0)
        decision = str(ctx.bank_decision or ctx.decision or "ALLOW").upper()

        result = {
            "kind": case["kind"],
            "name": case["name"],
            "transaction_id": ctx.txn_id,
            "risk_score": round(risk_score, 4),
            "decision": decision,
            "component_scores": {
                "rules": round(float(ctx.rules_score or 0.0), 4),
                "ml": round(float(ctx.ml_score or 0.0), 4),
                "behavior": round(float(ctx.behavior_score or 0.0), 4),
                "graph": round(float(ctx.graph_score or 0.0), 4),
            },
            "reason": list((ctx.reasons or ctx.decision_reasons or [])[:3]),
        }
        results.append(result)

        print(
            f"{idx:02d} | kind={result['kind']:<6} | risk_score={result['risk_score']:.4f} "
            f"| decision={result['decision']:<7} | txn={result['transaction_id']} | {result['name']}"
        )

    normal_scores = [r["risk_score"] for r in results if r["kind"] == "normal"]
    fraud_scores = [r["risk_score"] for r in results if r["kind"] == "fraud"]
    fraud_high_actions = [r for r in results if r["kind"] == "fraud" and r["decision"] in {"STEP-UP", "BLOCK"}]

    print("-" * 120)
    print(
        "SUMMARY | "
        f"normal_avg={mean(normal_scores):.4f} | fraud_avg={mean(fraud_scores):.4f} | "
        f"fraud_stepup_or_block={len(fraud_high_actions)}/{len(fraud_scores)}"
    )

    if mean(fraud_scores) <= mean(normal_scores):
        raise SystemExit("Validation failed: fraud average risk_score is not higher than normal average")

    print("Validation passed: fraud scenarios score higher risk than normal scenarios.")


if __name__ == "__main__":
    main()
