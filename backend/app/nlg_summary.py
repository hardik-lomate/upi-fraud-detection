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
import re

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
    seen: set[str] = set()
    for raw in values or []:
        text = _simplify_reason_text(str(raw or ""))
        key = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()
        if text and key and key not in seen:
            unique.append(text)
            seen.add(key)
        if len(unique) >= limit:
            break
    return unique


def _simplify_reason_text(text: str) -> str:
    raw = str(text or "").strip().rstrip(".")
    lowered = raw.lower()

    phrase_rules = [
        ("new device", "payment came from a new device"),
        ("failed", "many recent failed attempts were seen"),
        ("velocity", "many quick transactions were attempted"),
        ("burst", "many quick transactions were attempted"),
        ("night", "transaction happened at an unusual hour"),
        ("late", "transaction happened at an unusual hour"),
        ("mule", "receiver is linked to suspicious accounts"),
        ("graph", "receiver is linked to a risky transaction network"),
        ("network", "receiver is linked to a risky transaction network"),
        ("deviation", "amount is unusual for this sender"),
        ("high amount", "amount is much higher than usual"),
        ("drift", "recent behavior differs from the sender's normal pattern"),
        ("anomaly", "transaction behavior is unusual"),
    ]

    for needle, phrase in phrase_rules:
        if needle in lowered:
            return phrase

    cleaned = raw.replace("_", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    if len(cleaned) > 88:
        cleaned = cleaned[:85].rstrip() + "..."
    return cleaned[0].upper() + cleaned[1:]


def _top_reason_snippets(
    shap_reasons: list[str] | None,
    behavior_reasons: list[str] | None,
    graph_reasons: list[str] | None,
    rule_reasons: list[str] | None,
    limit: int = 3,
) -> list[str]:
    ordered_sources = [
        _dedupe_text(rule_reasons, limit=2),
        _dedupe_text(graph_reasons, limit=2),
        _dedupe_text(behavior_reasons, limit=2),
        _dedupe_text(shap_reasons, limit=2),
    ]

    merged: list[str] = []
    for source in ordered_sources:
        for reason in source:
            if reason not in merged:
                merged.append(reason)
            if len(merged) >= limit:
                return merged
    return merged


def build_pipeline_reasoning(
    decision: str,
    risk_score: float,
    shap_reasons: list[str] | None = None,
    behavior_reasons: list[str] | None = None,
    graph_reasons: list[str] | None = None,
    rule_reasons: list[str] | None = None,
) -> list[str]:
    """Build concise plain-language reasoning from strongest risk signals."""
    score = max(0.0, min(1.0, float(risk_score or 0.0)))
    score_pct = int(round(score * 100))
    decision_norm = str(decision or "ALLOW").strip().upper()

    if decision_norm == "BLOCK":
        sentence1 = f"The payment was blocked because the combined fraud risk reached {score_pct}%."
    elif decision_norm in {"VERIFY", "STEP-UP"}:
        sentence1 = f"The payment was flagged for additional verification with a fraud risk of {score_pct}%."
    else:
        sentence1 = f"The payment was allowed after evaluating a fraud risk score of {score_pct}%."

    top_reasons = _top_reason_snippets(
        shap_reasons=shap_reasons,
        behavior_reasons=behavior_reasons,
        graph_reasons=graph_reasons,
        rule_reasons=rule_reasons,
        limit=3,
    )

    if top_reasons:
        sentence2 = "Top reasons: " + "; ".join(top_reasons[:3]) + "."
    else:
        sentence2 = "No strong risk signals were found across rules, behavior, or network checks."

    sentences = [sentence1, sentence2]

    if decision_norm in {"VERIFY", "STEP-UP"}:
        sentences.append("User verification was requested before payment completion.")
    elif decision_norm == "BLOCK":
        sentences.append("The payment can be retried after confirming beneficiary and device details.")

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

    # Keep transaction-specific first sentence and add one concise reasoning sentence.
    tail = narrative[1:2] if len(narrative) > 1 else ["No dominant risk indicators were identified."]
    return " ".join([sentence1, *tail])


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
