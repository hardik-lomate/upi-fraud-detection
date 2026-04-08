"""
Natural Language Alert Summaries — Template-based NLG.

Generates 2-sentence human-readable investigation summaries from raw pipeline
context. No external LLM dependency — uses rule-based templates for hackathon
reliability and zero-latency generation.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from .database import get_transaction_by_id
from .audit import get_prediction_audit_record

router = APIRouter(prefix="/explain", tags=["Explainability"])


class SummaryRequest(BaseModel):
    transaction_id: str = Field(..., description="Transaction ID to summarize")


class SummaryResponse(BaseModel):
    transaction_id: str
    nl_summary: str
    risk_factors: list[str]
    generated_at: str


def _format_amount(amount: float) -> str:
    if amount >= 100000:
        return f"Rs.{amount / 100000:.1f}L"
    elif amount >= 1000:
        return f"Rs.{amount / 1000:.1f}K"
    return f"Rs.{amount:,.0f}"


def _time_context(timestamp_str: str) -> str:
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        hour = ts.hour
        if 0 <= hour <= 5:
            return f"at {hour}:{ts.minute:02d}am (unusual late-night activity)"
        elif 6 <= hour <= 8:
            return f"at {hour}:{ts.minute:02d}am (early morning)"
        elif 22 <= hour <= 23:
            return f"at {hour - 12}:{ts.minute:02d}pm (late evening)"
        return f"at {ts.strftime('%I:%M%p').lower()}"
    except Exception:
        return ""


def _dedupe_text(values: list[str] | None, limit: int = 3) -> list[str]:
    unique: list[str] = []
    for raw in values or []:
        text = str(raw or "").strip().rstrip(".")
        if text and text not in unique:
            unique.append(text)
        if len(unique) >= limit:
            break
    return unique


def build_pipeline_reasoning(
    decision: str,
    risk_score: float,
    shap_reasons: list[str] | None = None,
    behavior_reasons: list[str] | None = None,
    graph_reasons: list[str] | None = None,
    rule_reasons: list[str] | None = None,
) -> list[str]:
    """Build a concise 2-3 sentence explanation from all major risk signals."""
    score = max(0.0, min(1.0, float(risk_score or 0.0)))
    score_pct = int(round(score * 100))
    decision_norm = str(decision or "ALLOW").strip().upper()

    if decision_norm == "BLOCK":
        sentence1 = f"The payment was blocked because the combined fraud risk reached {score_pct}%."
    elif decision_norm in {"VERIFY", "STEP-UP"}:
        sentence1 = f"The payment was flagged for additional verification with a fraud risk of {score_pct}%."
    else:
        sentence1 = f"The payment was allowed after evaluating a fraud risk score of {score_pct}%."

    model_signals = _dedupe_text(shap_reasons, limit=2)
    behavior_signals = _dedupe_text(behavior_reasons, limit=1)
    graph_signals = _dedupe_text(graph_reasons, limit=1)

    signal_parts: list[str] = []
    if model_signals:
        signal_parts.append(f"model features such as {', '.join(model_signals)}")
    if behavior_signals:
        signal_parts.append(f"behavioral signals such as {', '.join(behavior_signals)}")
    if graph_signals:
        signal_parts.append(f"graph-network signals such as {', '.join(graph_signals)}")

    if signal_parts:
        sentence2 = "Key contributing indicators include " + "; ".join(signal_parts) + "."
    else:
        sentence2 = "No dominant model, behavioral, or graph anomalies were observed."

    sentences = [sentence1, sentence2]

    rule_signals = _dedupe_text(rule_reasons, limit=2)
    if rule_signals:
        sentences.append("Rule safeguards also triggered: " + ", ".join(rule_signals) + ".")

    return sentences[:3]


def generate_summary(txn: dict, audit: dict = None) -> str:
    """Generate a concise 2-3 sentence investigation summary."""
    sender = txn.get("sender_upi", "Unknown sender")
    receiver = txn.get("receiver_upi", "Unknown receiver")
    amount = float(txn.get("amount", 0))
    decision = txn.get("decision", "ALLOW")
    fraud_score = float(txn.get("fraud_score", 0))
    timestamp = txn.get("timestamp", "")
    device_id = txn.get("device_id", "")

    amount_str = _format_amount(amount)
    time_str = _time_context(timestamp)
    score_pct = f"{fraud_score * 100:.0f}%"

    reasons = list(audit.get("reasons", []) or []) if audit and isinstance(audit.get("reasons"), list) else []

    # Sentence 1: What happened
    if decision == "BLOCK":
        sentence1 = (
            f"This transaction was blocked because {sender} attempted to send "
            f"{amount_str} to {receiver} {time_str} with a risk score of {score_pct}."
        )
    elif decision == "VERIFY":
        sentence1 = (
            f"This transaction requires verification: {sender} is sending "
            f"{amount_str} to {receiver} {time_str}, triggering a {score_pct} risk score."
        )
    else:
        sentence1 = (
            f"This transaction was approved: {sender} sent {amount_str} to "
            f"{receiver} {time_str} with a low risk score of {score_pct}."
        )

    behavior_reasons = [
        r for r in reasons
        if any(k in str(r).lower() for k in ("behavior", "drift", "velocity", "burst", "receiver pattern"))
    ]
    graph_reasons = [
        r for r in reasons
        if any(k in str(r).lower() for k in ("graph", "network", "mule", "cycle", "connectivity", "hub"))
    ]
    model_reasons = [r for r in reasons if r not in behavior_reasons and r not in graph_reasons]

    narrative = build_pipeline_reasoning(
        decision=decision,
        risk_score=fraud_score,
        shap_reasons=model_reasons,
        behavior_reasons=behavior_reasons,
        graph_reasons=graph_reasons,
        rule_reasons=[],
    )

    # Keep transaction-specific first sentence and add 1-2 reasoning sentences.
    tail = narrative[1:] if len(narrative) > 1 else ["No dominant risk indicators were identified."]
    return " ".join([sentence1, *tail[:2]])


@router.post("/summary", summary="Generate natural language investigation summary",
             response_model=SummaryResponse)
def explain_summary(req: SummaryRequest):
    txn = get_transaction_by_id(req.transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail=f"Transaction {req.transaction_id} not found")

    audit = get_prediction_audit_record(req.transaction_id)
    summary = generate_summary(txn, audit)

    reasons = []
    if audit and isinstance(audit.get("reasons"), list):
        reasons = audit["reasons"]

    return SummaryResponse(
        transaction_id=req.transaction_id,
        nl_summary=summary,
        risk_factors=reasons[:5],
        generated_at=datetime.utcnow().isoformat(),
    )
