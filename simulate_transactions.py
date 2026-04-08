"""Run demo transactions through the full bank pipeline.

Run:
  python simulate_transactions.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from statistics import mean

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


MUMBAI = (19.0760, 72.8777)
DELHI = (28.6139, 77.2090)
BENGALURU = (12.9716, 77.5946)
CHENNAI = (13.0827, 80.2707)


def _txn(
  sender_upi: str,
  receiver_upi: str,
  amount: float,
  tx_type: str,
  ts: datetime,
  device_id: str,
  lat: float,
  lon: float,
) -> dict:
  return {
    "sender_upi": sender_upi,
    "receiver_upi": receiver_upi,
    "amount": amount,
    "transaction_type": tx_type,
    "timestamp": ts.isoformat(),
    "sender_device_id": device_id,
    "sender_location_lat": lat,
    "sender_location_lon": lon,
  }


def _run_pipeline(txn: dict, graph):
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
    graph=graph,
    behavior_fn=analyze_behavioral_risk,
    graph_score_fn=score_graph_risk,
    rules_score_fn=compute_rules_score,
    combine_risk_fn=combine_risk_scores,
    audit_fn=None,
    decision_mode="bank",
  )


def _prime_context(run_tag: str, graph, base: datetime) -> None:
  # Prime normal users so known-device/known-receiver behavior looks realistic.
  warmups = [
    _txn(f"n1.{run_tag}@upi", f"biller.{run_tag}@okaxis", 1450.0, "bill_payment", base - timedelta(hours=3), "N1_DEVICE", *MUMBAI),
    _txn(f"n2.{run_tag}@upi", f"grocery.{run_tag}@ybl", 520.0, "purchase", base - timedelta(hours=3), "N2_DEVICE", *BENGALURU),
    _txn(f"n3.{run_tag}@upi", f"rent.{run_tag}@oksbi", 11800.0, "transfer", base - timedelta(hours=3), "N3_DEVICE", *DELHI),
    _txn(f"n4.{run_tag}@upi", f"recharge.{run_tag}@paytm", 299.0, "recharge", base - timedelta(hours=3), "N4_DEVICE", *CHENNAI),
    _txn(f"n5.{run_tag}@upi", f"merchant.{run_tag}@okhdfc", 880.0, "purchase", base - timedelta(hours=3), "N5_DEVICE", *MUMBAI),
  ]
  for txn in warmups:
    _run_pipeline(txn, graph)

  # Prime fraud users with normal baselines so attack transactions show sharp deviation.
  fraud_baselines = [
    _txn(f"f1.{run_tag}@upi", f"known.payee.{run_tag}@upi", 780.0, "purchase", base - timedelta(hours=2, minutes=40), "F1_OLD_DEVICE", *DELHI),
    _txn(f"f4.{run_tag}@upi", f"known.payee.{run_tag}@upi", 640.0, "purchase", base - timedelta(hours=2, minutes=35), "F4_OLD_DEVICE", *MUMBAI),
    _txn(f"f5.{run_tag}@upi", f"known.payee.{run_tag}@upi", 520.0, "purchase", base - timedelta(hours=2, minutes=30), "F5_OLD_DEVICE", *CHENNAI),
  ]
  for txn in fraud_baselines:
    _run_pipeline(txn, graph)

  # Prime velocity fraud sender with many transactions in the last hour.
  velocity_sender = f"f2.{run_tag}@upi"
  for i in range(14):
    txn = _txn(
      velocity_sender,
      f"spray{i}.{run_tag}@upi",
      900.0 + i * 15.0,
      "transfer",
      base + timedelta(minutes=i * 2),
      "F2_DEVICE",
      *BENGALURU,
    )
    _run_pipeline(txn, graph)

  # Prime f4 with sequence signatures that increase behavior pattern-risk.
  # This creates round-amount burst + increment pattern + velocity ramp.
  f4_sender = f"f4.{run_tag}@upi"
  burst_amounts = [1000.0, 2000.0, 3000.0, 4000.0, 5000.0, 6000.0, 7000.0]
  burst_minutes = [14, 15, 15, 16, 16, 16, 16]
  for i, (amt, minute) in enumerate(zip(burst_amounts, burst_minutes)):
    txn = _txn(
      f4_sender,
      f"burst.{i}.{run_tag}@upi",
      amt,
      "transfer",
      base + timedelta(minutes=minute),
      "F4_OLD_DEVICE",
      *MUMBAI,
    )
    _run_pipeline(txn, graph)

  # Prime impossible-travel sender with a prior location.
  prior = _txn(
    f"f3.{run_tag}@upi",
    f"utility.{run_tag}@okaxis",
    620.0,
    "bill_payment",
    base + timedelta(minutes=8),
    "F3_DEVICE",
    *MUMBAI,
  )
  _run_pipeline(prior, graph)

  # Prime graph-risk receiver with many incoming edges (mule-like pattern).
  mule_receiver = f"mule.collector.{run_tag}@upi"
  for i in range(12):
    txn = _txn(
      f"seed{i}.{run_tag}@upi",
      mule_receiver,
      1500.0 + i * 120.0,
      "transfer",
      base + timedelta(minutes=5 + i),
      f"SEED_{i}",
      *DELHI,
    )
    _run_pipeline(txn, graph)


def main() -> None:
  init_db()
  graph = get_graph()

  run_tag = datetime.utcnow().strftime("%m%d%H%M%S")
  base = datetime(2026, 4, 8, 11, 0, 0)

  _prime_context(run_tag, graph, base)

  cases = [
    {
      "kind": "normal",
      "name": "Routine utility bill",
      "txn": _txn(f"n1.{run_tag}@upi", f"biller.{run_tag}@okaxis", 1620.0, "bill_payment", base + timedelta(minutes=2), "N1_DEVICE", *MUMBAI),
    },
    {
      "kind": "normal",
      "name": "Morning grocery payment",
      "txn": _txn(f"n2.{run_tag}@upi", f"grocery.{run_tag}@ybl", 690.0, "purchase", base + timedelta(minutes=4), "N2_DEVICE", *BENGALURU),
    },
    {
      "kind": "normal",
      "name": "Scheduled rent transfer",
      "txn": _txn(f"n3.{run_tag}@upi", f"rent.{run_tag}@oksbi", 12000.0, "transfer", base + timedelta(minutes=6), "N3_DEVICE", *DELHI),
    },
    {
      "kind": "normal",
      "name": "Mobile recharge",
      "txn": _txn(f"n4.{run_tag}@upi", f"recharge.{run_tag}@paytm", 349.0, "recharge", base + timedelta(minutes=8), "N4_DEVICE", *CHENNAI),
    },
    {
      "kind": "normal",
      "name": "Known merchant purchase",
      "txn": _txn(f"n5.{run_tag}@upi", f"merchant.{run_tag}@okhdfc", 930.0, "purchase", base + timedelta(minutes=10), "N5_DEVICE", *MUMBAI),
    },
    {
      "kind": "fraud",
      "name": "High amount + new device at night",
      "txn": _txn(f"f1.{run_tag}@upi", f"urgent.kyc.verify.{run_tag}@upi", 98000.0, "transfer", base.replace(hour=2, minute=11), "F1_NEW_DEVICE", *DELHI),
    },
    {
      "kind": "fraud",
      "name": "High velocity follow-up transfer",
      "txn": _txn(f"f2.{run_tag}@upi", f"collector.{run_tag}@upi", 76000.0, "transfer", base + timedelta(minutes=29), "F2_DEVICE", *BENGALURU),
    },
    {
      "kind": "fraud",
      "name": "Impossible travel payout",
      "txn": _txn(f"f3.{run_tag}@upi", f"cashout.{run_tag}@upi", 82000.0, "transfer", base + timedelta(minutes=17), "F3_DEVICE", *DELHI),
    },
    {
      "kind": "fraud",
      "name": "Mule network + impossible travel attack",
      "txn": _txn(f"f4.{run_tag}@upi", f"mule.collector.{run_tag}@upi", 91000.0, "transfer", base + timedelta(minutes=24), "F4_NEW_DEVICE", *DELHI),
    },
    {
      "kind": "fraud",
      "name": "Suspicious support-payment lure",
      "txn": _txn(f"f5.{run_tag}@upi", f"refund.support.helpdesk.{run_tag}@upi", 87000.0, "transfer", base.replace(hour=1, minute=47), "F5_NEW_DEVICE", *CHENNAI),
    },
    {
      "kind": "normal",
      "name": "Borderline normal: late-night travel transfer",
      "txn": _txn(f"n3.{run_tag}@upi", f"rent.{run_tag}@oksbi", 26500.0, "transfer", base.replace(hour=1, minute=26), "N3_TRAVEL_DEVICE", *DELHI),
    },
    {
      "kind": "fraud",
      "name": "Borderline fraud: moderate deviation rapid transfer",
      "txn": _txn(f"f2.{run_tag}@upi", f"collector.{run_tag}@upi", 42000.0, "transfer", base + timedelta(minutes=31), "F2_DEVICE", *BENGALURU),
    },
  ]

  results = []

  normal_total = sum(1 for c in cases if c["kind"] == "normal")
  fraud_total = sum(1 for c in cases if c["kind"] == "fraud")

  print(f"DEMO SIMULATION ({len(cases)} transactions | {normal_total} normal + {fraud_total} fraud)")
  print("=" * 120)

  for idx, case in enumerate(cases, start=1):
    ctx = _run_pipeline(case["txn"], graph)
    result = {
      "kind": case["kind"],
      "name": case["name"],
      "transaction_id": str(ctx.txn_id),
      "risk_score": round(float(ctx.bank_risk_score or ctx.risk_score or 0.0), 4),
      "decision": str(ctx.bank_decision or ctx.decision or "ALLOW").upper(),
      "component_scores": {
        "rules": round(float(ctx.rules_score or 0.0), 4),
        "ml": round(float(ctx.ml_score or 0.0), 4),
        "behavior": round(float(ctx.behavior_score or 0.0), 4),
        "graph": round(float(ctx.graph_score or 0.0), 4),
      },
      "reason": list((ctx.reasons or ctx.decision_reasons or ["No strong risk signal"])[:3]),
    }
    results.append(result)

    required_payload = {
      "transaction_id": result["transaction_id"],
      "risk_score": result["risk_score"],
      "decision": result["decision"],
      "component_scores": result["component_scores"],
      "reason": result["reason"],
    }

    print(
      f"{idx:02d} | kind={case['kind']:<6} | risk_score={result['risk_score']:.4f} "
      f"| decision={result['decision']:<7} | txn={result['transaction_id']} | {case['name']}"
    )
    print(f"      OUTPUT={json.dumps(required_payload, ensure_ascii=False)}")

  normal_scores = [r["risk_score"] for r in results if r["kind"] == "normal"]
  fraud_scores = [r["risk_score"] for r in results if r["kind"] == "fraud"]
  normal_ml_scores = [r["component_scores"]["ml"] for r in results if r["kind"] == "normal"]
  fraud_ml_scores = [r["component_scores"]["ml"] for r in results if r["kind"] == "fraud"]
  fraud_high_actions = [r for r in results if r["kind"] == "fraud" and r["decision"] in {"STEP-UP", "BLOCK"}]
  normal_stepups = [r for r in results if r["kind"] == "normal" and r["decision"] == "STEP-UP"]
  fraud_stepups = [r for r in results if r["kind"] == "fraud" and r["decision"] == "STEP-UP"]
  fraud_blocks = [r for r in results if r["kind"] == "fraud" and r["decision"] == "BLOCK"]

  print("-" * 120)
  print(
    "SUMMARY | "
    f"normal_avg={mean(normal_scores):.4f} | fraud_avg={mean(fraud_scores):.4f} | "
    f"normal_ml_avg={mean(normal_ml_scores):.4f} | fraud_ml_avg={mean(fraud_ml_scores):.4f} | "
    f"fraud_stepup_or_block={len(fraud_high_actions)}/{len(fraud_scores)} | "
    f"normal_stepup={len(normal_stepups)} | fraud_stepup={len(fraud_stepups)} | fraud_block={len(fraud_blocks)}"
  )

  if mean(fraud_scores) <= mean(normal_scores):
    raise SystemExit("Validation failed: fraud average risk_score is not higher than normal average")
  if mean(fraud_ml_scores) <= mean(normal_ml_scores):
    raise SystemExit("Validation failed: fraud average ML score is not higher than normal average")
  if len(normal_stepups) == 0:
    raise SystemExit("Validation failed: expected at least one normal STEP-UP borderline case")
  if len(fraud_stepups) == 0:
    raise SystemExit("Validation failed: expected at least one fraud STEP-UP case (not all fraud should be BLOCK)")

  print("Validation passed: fraud scenarios score higher risk than normal scenarios.")


if __name__ == "__main__":
  main()
