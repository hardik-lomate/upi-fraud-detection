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
        features=dict(getattr(ctx, "features", {}) or {}),
        timestamp=str(getattr(ctx, "timestamp", "") or ""),
    )
