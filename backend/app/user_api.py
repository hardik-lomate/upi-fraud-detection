"""User-facing ShieldPay API routes.

These endpoints provide consumer-safe responses and hide analyst-only fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func

from .auth import get_current_client, check_permission
from .pipeline import run_pipeline
from .feature_extract import extract_features
from .rules_engine import evaluate_rules, get_rule_decision
from .predict import predict_fraud
from .explainability import explain_prediction, format_reasons
from .device_fingerprint import check_device_anomalies, update_device_history
from .graph_features import get_graph
from .database import (
    SessionLocal,
    TransactionRecord,
    FraudHistory,
    save_transaction,
)
from .cases import CaseRecord
from .monitoring import record_prediction
from .consumer_messages import (
    build_security_note,
    build_user_message,
    build_user_reason,
    derive_receiver_name,
    detect_primary_pattern,
    format_inr,
)

router = APIRouter(tags=["ShieldPay User API"])

HIGH_RISK_RECEIVER_KEYWORDS = (
    "kyc",
    "helpdesk",
    "verify",
    "refund",
    "npci",
    "govt",
    "rbi",
    "tax",
    "support",
    "mule",
    "offshore",
)


class PayRequest(BaseModel):
    sender_upi: str = Field(..., min_length=3)
    receiver_upi: str = Field(..., min_length=3)
    amount: float = Field(..., gt=0, le=500000)
    transaction_type: str = Field("transfer")
    note: Optional[str] = Field(None, max_length=100)
    sender_device_id: Optional[str] = Field(None, min_length=1)
    sender_location_lat: Optional[float] = Field(None, ge=-90, le=90)
    sender_location_lon: Optional[float] = Field(None, ge=-180, le=180)


class ReportFraudRequest(BaseModel):
    transaction_id: str = Field(..., min_length=4)
    reporter_upi: str = Field(..., min_length=3)
    description: str = Field(..., min_length=5, max_length=500)


def _normalize_upi(upi_id: str) -> str:
    return (upi_id or "").strip().lower()


def _receipt_id(txn_id: str) -> str:
    compact = (txn_id or "UNKNOWN").replace("TXN_", "").upper()
    return f"SP-{compact}"


def _internal_status_from_decision(decision: str) -> str:
    d = (decision or "").upper()
    if d == "VERIFY":
        return "PENDING_VERIFICATION"
    if d == "BLOCK":
        return "BLOCKED"
    return "ALLOWED"


def _public_status_from_record(decision: str, status: Optional[str]) -> str:
    s = (status or "").upper()
    if s == "VERIFIED":
        return "VERIFIED"
    if s == "PENDING_VERIFICATION":
        return "PENDING_VERIFICATION"
    if s == "BLOCKED":
        return "BLOCKED"

    d = (decision or "").upper()
    if d == "VERIFY":
        return "PENDING_VERIFICATION"
    if d == "BLOCK":
        return "BLOCKED"
    return "COMPLETED"


def _run_prediction(txn_dict: dict):
    return run_pipeline(
        txn_dict=txn_dict,
        extract_fn=extract_features,
        evaluate_rules_fn=evaluate_rules,
        get_rule_decision_fn=get_rule_decision,
        predict_fn=predict_fraud,
        explain_fn=explain_prediction,
        format_reasons_fn=format_reasons,
        check_device_fn=check_device_anomalies,
        update_device_fn=update_device_history,
        sender_history=None,
        graph=get_graph(),
    )


def _load_response_json(record: TransactionRecord) -> dict:
    if not record.response_json:
        return {}
    try:
        payload = json.loads(record.response_json)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {}


def _receiver_info_snapshot(upi_id: str) -> dict:
    receiver_upi = _normalize_upi(upi_id)
    local = receiver_upi.split("@")[0] if receiver_upi else ""
    graph_info = get_graph().get_node_features(receiver_upi)

    db = SessionLocal()
    try:
        txn_count = int(
            db.query(func.count(TransactionRecord.id))
            .filter(TransactionRecord.receiver_upi == receiver_upi)
            .scalar()
            or 0
        )
        blocked_count = int(
            db.query(func.count(TransactionRecord.id))
            .filter(TransactionRecord.receiver_upi == receiver_upi)
            .filter(TransactionRecord.status == "BLOCKED")
            .scalar()
            or 0
        )
    finally:
        db.close()

    keyword_risk = any(k in local for k in HIGH_RISK_RECEIVER_KEYWORDS)
    if keyword_risk or blocked_count >= 2 or graph_info.get("is_mule_suspect") or graph_info.get("in_degree", 0) >= 8:
        vpa_risk = "HIGH"
    elif txn_count == 0 or blocked_count >= 1 or graph_info.get("in_degree", 0) >= 4:
        vpa_risk = "MEDIUM"
    else:
        vpa_risk = "LOW"

    warning = None
    if vpa_risk == "HIGH":
        warning = "This receiver matches scam patterns seen in UPI complaints. Verify before sending money."

    return {
        "upi_id": receiver_upi,
        "display_name": derive_receiver_name(receiver_upi),
        "is_known": txn_count > 0,
        "vpa_risk": vpa_risk,
        "warning": warning,
        "transaction_count": txn_count,
    }


def _user_transaction_view(record: TransactionRecord) -> dict:
    payload = _load_response_json(record)

    decision = (payload.get("decision") or record.decision or "ALLOW").upper()
    receiver_upi = _normalize_upi(payload.get("receiver_upi") or record.receiver_upi)
    receiver_name = payload.get("receiver_name") or derive_receiver_name(receiver_upi)
    amount = float(payload.get("amount") or record.amount or 0)
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []

    matched_pattern = None
    if payload.get("fraud_pattern"):
        matched_pattern = {
            "name": payload.get("fraud_pattern"),
            "description": payload.get("user_reason"),
        }

    user_reason = payload.get("user_reason") or build_user_reason(
        decision=decision,
        receiver_upi=receiver_upi,
        reasons=[str(r) for r in reasons],
        matched_pattern=matched_pattern,
    )
    user_message = payload.get("user_message") or build_user_message(
        decision=decision,
        amount=amount,
        receiver_name=receiver_name,
        user_reason=user_reason,
    )
    security_note = payload.get("security_note") or build_security_note(decision=decision, user_reason=user_reason)

    return {
        "transaction_id": record.transaction_id,
        "sender_upi": _normalize_upi(record.sender_upi),
        "receiver_upi": receiver_upi,
        "receiver_name": receiver_name,
        "amount": amount,
        "amount_display": format_inr(amount),
        "transaction_type": payload.get("transaction_type", "transfer"),
        "status": payload.get("status") or _public_status_from_record(decision, record.status),
        "decision": decision,
        "user_message": user_message,
        "user_reason": user_reason,
        "security_note": security_note,
        "fraud_pattern": payload.get("fraud_pattern"),
        "timestamp": payload.get("timestamp") or record.timestamp,
        "receipt_id": payload.get("receipt_id") or _receipt_id(record.transaction_id),
    }


def _security_level(score: int) -> str:
    if score >= 85:
        return "EXCELLENT"
    if score >= 70:
        return "GOOD"
    if score >= 50:
        return "FAIR"
    return "AT_RISK"


def _mark_compromised_profile(db, upi_id: str):
    profile = db.query(FraudHistory).filter(FraudHistory.upi_id == upi_id).first()
    now = datetime.utcnow()
    if not profile:
        profile = FraudHistory(
            upi_id=upi_id,
            fraud_count=1,
            block_count=1,
            is_flagged=True,
            last_fraud_at=now,
        )
        db.add(profile)
        return

    profile.fraud_count = int(profile.fraud_count or 0) + 1
    profile.block_count = int(profile.block_count or 0) + 1
    profile.is_flagged = True
    profile.last_fraud_at = now


@router.post("/pay")
async def pay_transaction(
    body: PayRequest,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "predict")

    sender_upi = _normalize_upi(body.sender_upi)
    receiver_upi = _normalize_upi(body.receiver_upi)
    if not sender_upi or not receiver_upi:
        raise HTTPException(status_code=422, detail="sender_upi and receiver_upi are required")

    txn_dict = {
        "sender_upi": sender_upi,
        "receiver_upi": receiver_upi,
        "amount": body.amount,
        "transaction_type": body.transaction_type or "transfer",
        "note": body.note or "",
        "sender_device_id": body.sender_device_id,
        "sender_location_lat": body.sender_location_lat,
        "sender_location_lon": body.sender_location_lon,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        ctx = _run_prediction(txn_dict)
        record_prediction(ctx.fraud_score, ctx.features)

        decision = (ctx.decision or "ALLOW").upper()
        receiver_name = derive_receiver_name(receiver_upi)
        matched_pattern = detect_primary_pattern(ctx.raw_txn, ctx.features, ctx.graph_info)
        user_reason = build_user_reason(
            decision=decision,
            receiver_upi=receiver_upi,
            reasons=[str(r) for r in (ctx.reasons or [])],
            matched_pattern=matched_pattern,
        )
        user_message = build_user_message(
            decision=decision,
            amount=body.amount,
            receiver_name=receiver_name,
            user_reason=user_reason,
        )
        security_note = build_security_note(decision=decision, user_reason=user_reason)

        status = "COMPLETED"
        if decision == "VERIFY":
            status = "PENDING_VERIFICATION"
        elif decision == "BLOCK":
            status = "BLOCKED"

        response = {
            "transaction_id": ctx.txn_id,
            "status": status,
            "decision": decision,
            "amount": float(body.amount),
            "receiver_upi": receiver_upi,
            "receiver_name": receiver_name,
            "user_message": user_message,
            "user_reason": user_reason,
            "security_note": security_note,
            "timestamp": ctx.timestamp,
            "receipt_id": _receipt_id(ctx.txn_id),
            "transaction_type": body.transaction_type or "transfer",
        }
        if decision == "VERIFY":
            response["verify_methods"] = ["fingerprint", "face", "pin"]
        if decision == "BLOCK" and matched_pattern:
            response["fraud_pattern"] = matched_pattern.get("name")

        save_transaction(
            ctx.txn_id,
            sender_upi,
            receiver_upi,
            body.amount,
            ctx.fraud_score,
            decision,
            ctx.timestamp,
            ctx.raw_txn.get("sender_device_id") or "",
            status=_internal_status_from_decision(decision),
            response_json=json.dumps(response, ensure_ascii=False, separators=(",", ":")),
        )
        return response
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to process payment right now")


@router.get("/receiver/info")
async def receiver_info(
    upi_id: str,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "transactions")
    normalized_upi = _normalize_upi(upi_id)
    if not normalized_upi:
        raise HTTPException(status_code=422, detail="upi_id is required")
    return _receiver_info_snapshot(normalized_upi)


@router.get("/my/transactions")
async def my_transactions(
    sender_upi: str,
    limit: int = 50,
    status: Optional[str] = None,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "transactions")
    sender = _normalize_upi(sender_upi)
    if not sender:
        raise HTTPException(status_code=422, detail="sender_upi is required")

    limit = max(1, min(limit, 200))
    status_filter = (status or "").strip().upper()

    db = SessionLocal()
    try:
        query = db.query(TransactionRecord).filter(TransactionRecord.sender_upi == sender)

        if status_filter and status_filter != "ALL":
            if status_filter in {"COMPLETED", "SENT", "ALLOWED"}:
                query = query.filter(TransactionRecord.status.in_(["ALLOWED", "VERIFIED"]))
            elif status_filter in {"PENDING", "PENDING_VERIFICATION"}:
                query = query.filter(TransactionRecord.status == "PENDING_VERIFICATION")
            elif status_filter == "BLOCKED":
                query = query.filter(TransactionRecord.status == "BLOCKED")
            elif status_filter == "VERIFIED":
                query = query.filter(TransactionRecord.status == "VERIFIED")
            else:
                raise HTTPException(status_code=422, detail="Unsupported status filter")

        records = query.order_by(TransactionRecord.id.desc()).limit(limit).all()
        txns = [_user_transaction_view(r) for r in records]
        return {
            "sender_upi": sender,
            "transactions": txns,
            "total": len(txns),
        }
    finally:
        db.close()


@router.get("/my/security-score")
async def my_security_score(
    upi_id: str,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "transactions")
    sender = _normalize_upi(upi_id)
    if not sender:
        raise HTTPException(status_code=422, detail="upi_id is required")

    db = SessionLocal()
    try:
        profile = db.query(FraudHistory).filter(FraudHistory.upi_id == sender).first()
        fraud_events = int(profile.fraud_count or 0) if profile else 0
        blocked_events = int(profile.block_count or 0) if profile else 0

        score = int(max(0, min(100, round(100 - (fraud_events * 15) - (blocked_events * 8)))))
        level = _security_level(score)

        protected_amount = float(
            db.query(func.coalesce(func.sum(TransactionRecord.amount), 0.0))
            .filter(TransactionRecord.sender_upi == sender)
            .filter(TransactionRecord.status == "BLOCKED")
            .scalar()
            or 0.0
        )

        recent_records = (
            db.query(TransactionRecord)
            .filter(TransactionRecord.sender_upi == sender)
            .filter(TransactionRecord.status.in_(["PENDING_VERIFICATION", "VERIFIED", "BLOCKED"]))
            .order_by(TransactionRecord.id.desc())
            .limit(5)
            .all()
        )

        recent_alerts = []
        for record in recent_records:
            tx = _user_transaction_view(record)
            recent_alerts.append(
                {
                    "transaction_id": tx["transaction_id"],
                    "status": tx["status"],
                    "decision": tx["decision"],
                    "receiver_upi": tx["receiver_upi"],
                    "receiver_name": tx["receiver_name"],
                    "amount": tx["amount"],
                    "amount_display": tx["amount_display"],
                    "message": tx["user_message"],
                    "timestamp": tx["timestamp"],
                }
            )

        return {
            "score": score,
            "level": level,
            "fraud_events": fraud_events,
            "protected_amount": round(protected_amount, 2),
            "recent_alerts": recent_alerts,
        }
    finally:
        db.close()


@router.post("/my/report-fraud")
async def report_fraud(
    body: ReportFraudRequest,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "transactions")

    transaction_id = (body.transaction_id or "").strip()
    reporter_upi = _normalize_upi(body.reporter_upi)
    if not transaction_id or not reporter_upi:
        raise HTTPException(status_code=422, detail="transaction_id and reporter_upi are required")

    db = SessionLocal()
    try:
        txn = db.query(TransactionRecord).filter(TransactionRecord.transaction_id == transaction_id).first()
        if txn and _normalize_upi(txn.sender_upi) != reporter_upi:
            raise HTTPException(status_code=403, detail="You can only report transactions from your own UPI ID")

        if txn:
            txn.status = "BLOCKED"
            txn.decision = "BLOCK"

        _mark_compromised_profile(db, reporter_upi)

        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        case = CaseRecord(
            txn_id=transaction_id,
            status="OPEN",
            assigned_to="support-queue",
            notes=f"[{ts}] User report from {reporter_upi}: {body.description.strip()}",
        )
        db.add(case)

        db.commit()
        db.refresh(case)
        return {
            "status": "REPORTED",
            "transaction_id": transaction_id,
            "ticket_id": f"CASE-{case.id}",
            "case_id": case.id,
            "message": "Thanks for reporting this payment. We have secured your account and opened a support case.",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to submit report right now")
    finally:
        db.close()
