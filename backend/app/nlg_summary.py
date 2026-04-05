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


def generate_summary(txn: dict, audit: dict = None) -> str:
    """Generate a 2-sentence investigation summary."""
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

    reasons = []
    if audit and isinstance(audit.get("reasons"), list):
        reasons = audit["reasons"]

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

    # Sentence 2: Why (from reasons or heuristics)
    if reasons:
        top_reasons = reasons[:3]
        reason_text = ", ".join(top_reasons)
        sentence2 = f"Key risk indicators: {reason_text}."
    elif fraud_score > 0.7:
        indicators = []
        if amount > 50000:
            indicators.append(f"unusually high amount ({amount_str})")
        if "NEW" in (device_id or "").upper():
            indicators.append("transaction from a new/unknown device")
        if not indicators:
            indicators.append("multiple ML models flagged anomalous patterns")
        sentence2 = f"The system detected {', '.join(indicators)}."
    elif fraud_score > 0.3:
        sentence2 = "The transaction shows moderate anomaly signals requiring human review."
    else:
        sentence2 = "No significant risk indicators were detected by the ensemble models."

    return f"{sentence1} {sentence2}"


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
