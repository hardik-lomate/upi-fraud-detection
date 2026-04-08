"""Pipeline audit logger adapter."""

from __future__ import annotations

from .audit import log_prediction


def log_pipeline_decision(ctx) -> None:
    """Log final pipeline decision using immutable audit trail."""
    if not getattr(ctx, "txn_id", ""):
        return

    rules_names = [
        str(getattr(rule, "rule_name", ""))
        for rule in (getattr(ctx, "rules_triggered", []) or [])
        if getattr(rule, "rule_name", "")
    ]

    decision_for_log = str(getattr(ctx, "bank_decision", "") or getattr(ctx, "decision", "ALLOW")).upper()
    risk_level = str(getattr(ctx, "risk_level", "LOW") or "LOW")

    component_scores = {
        "rules": float(getattr(ctx, "rules_score", 0.0) or 0.0),
        "ml": float(getattr(ctx, "ml_score", 0.0) or 0.0),
        "behavior": float(getattr(ctx, "behavior_score", 0.0) or 0.0),
        "graph": float(getattr(ctx, "graph_score", 0.0) or 0.0),
        "anomaly": float(getattr(ctx, "anomaly_score", 0.0) or 0.0),
    }
    risk_components = dict(getattr(ctx, "risk_components", {}) or {})
    audit_features = dict(getattr(ctx, "features", {}) or {})
    audit_features["_component_scores"] = component_scores
    if risk_components:
        audit_features["_risk_components"] = risk_components
    audit_features["_decision_mode"] = str(getattr(ctx, "decision_mode", "") or "legacy")

    log_prediction(
        transaction_id=str(ctx.txn_id),
        sender_upi=str((ctx.raw_txn or {}).get("sender_upi") or ""),
        receiver_upi=str((ctx.raw_txn or {}).get("receiver_upi") or ""),
        amount=float((ctx.raw_txn or {}).get("amount") or 0.0),
        fraud_score=float(getattr(ctx, "risk_score", 0.0) or 0.0),
        decision=decision_for_log,
        risk_level=risk_level,
        reasons=[str(x) for x in (getattr(ctx, "reasons", []) or [])[:5]],
        rules_triggered=rules_names,
        features=audit_features,
        timestamp=str(getattr(ctx, "timestamp", "") or ""),
    )
