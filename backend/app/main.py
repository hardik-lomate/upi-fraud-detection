"""
UPI Fraud Detection API — Main Application (v2.0.0).
Central controller: pipeline.py. All features wired. Zero business logic here.
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, WebSocket, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from datetime import datetime, timedelta
from typing import Optional
import logging
import time
import io
import csv
import os
import json
from uuid import uuid4
from pydantic import BaseModel, Field
from sqlalchemy import func

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import MODEL_VERSION, THRESHOLD_BLOCK, get_risk_tier

from .models import (
    TransactionRequest, PredictionResponse, TokenRequest, TokenResponse,
    RuleDetail, DeviceAnomaly, GraphInfo, RiskBreakdown, BankPredictionResponse,
    FeedbackRequest, BatchPredictSummary,
)
from .predict import predict_fraud, load_all_models, get_metadata
from .feature_extract import extract_features
from .history_store import hydrate_from_db, get_store_stats
from .database import (
    save_transaction,
    get_transactions,
    init_db,
    load_recent_history,
    get_flagged_users,
    get_transaction_by_id,
    SessionLocal,
    TransactionRecord,
    FraudHistory,
)
from .rules_engine import evaluate_rules, get_rule_decision
from .explainability_engine import explain_prediction, format_reasons
from .shap_service import load_shap_explainer
from .audit import log_prediction, get_audit_logs, get_prediction_audit_record
from .auth import get_current_client, check_permission, create_access_token
from .monitoring import (
    record_prediction,
    get_drift_report,
    get_prediction_stats,
    load_reference_distribution,
    record_latency,
    get_latency_stats,
)
from .device_fingerprint import check_device_anomalies, update_device_history
from .graph_features import get_graph
from .pipeline import run_pipeline
from .pipeline import PipelineContext, step_validate
from .behavioral_engine import analyze_behavioral_risk
from .graph_engine import score_graph_risk
from .risk_engine import compute_rules_score, combine_risk_scores
from .audit_logger import log_pipeline_decision
from .ml_model import predict_ml_probability
from .feedback import save_feedback, get_feedback_stats
from .live_feed import live_feed_handler
from .biometric import verify_biometric
from .consumer_messages import (
    build_security_note,
    build_user_message,
    build_user_reason,
    derive_receiver_name,
    detect_primary_pattern,
    format_inr,
)
from .cases import init_cases_table, CaseRecord, router as cases_router
from .rbi_report import router as rbi_router, rbi_report as generate_rbi_report
from .user_api import router as user_router
from .metrics_api import router as metrics_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("upi_fraud")

# --- App ---
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="UPI Fraud Detection API",
    version="2.0.0",
    description=(
        "Real-time UPI fraud detection with ensemble ML (LightGBM + XGBoost), "
        "SHAP explainability, graph analysis, rules engine, and compliance audit logging."
    ),
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _resolve_cors_origins() -> list[str]:
    raw = str(os.getenv("CORS_ORIGINS", "")).strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]

    fallback = []
    frontend_url = str(os.getenv("FRONTEND_URL", "")).strip()
    if frontend_url:
        fallback.append(frontend_url)
    fallback.append("http://localhost:3000")
    return fallback

app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics_router)


# =============================================
# Startup
# =============================================

@app.on_event("startup")
def startup():
    logger.info("=== Starting UPI Fraud Detection API ===")
    init_db()
    init_cases_table()
    load_all_models()
    records = load_recent_history(days=7)
    hydrate_from_db(records)
    graph = get_graph()
    graph_stats = graph.get_graph_stats()
    has_persisted_edges = int(graph_stats.get("total_edges", 0) or 0) > 0
    if not has_persisted_edges and records:
        for r in records:
            graph.add_transaction(
                r["sender_upi"],
                r["receiver_upi"],
                r["amount"],
                r["timestamp"],
                transaction_id=r.get("transaction_id"),
                persist=False,
            )
        graph.save_state()
        logger.info("Graph hydrated from %s DB records and persisted", len(records))
    else:
        logger.info("Graph state loaded from disk: %s", graph_stats)
    load_reference_distribution()
    load_shap_explainer()
    logger.info(f"Store: {get_store_stats()}")
    logger.info("=== Ready ===")


# =============================================
# Helpers
# =============================================

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


class PreCheckConfirmRequest(BaseModel):
    user_override: bool = True


class PreCheckCancelRequest(BaseModel):
    reason: Optional[str] = Field(default="User cancelled from warning prompt")


_PRE_CHECK_STORE: dict[str, dict] = {}
_PRE_CHECK_TTL = timedelta(minutes=30)


def _cleanup_prechecks(now: Optional[datetime] = None) -> None:
    current = now or datetime.utcnow()
    expired = []
    for pre_id, item in _PRE_CHECK_STORE.items():
        created = item.get("created_at")
        if not isinstance(created, datetime):
            expired.append(pre_id)
            continue
        if (current - created) > _PRE_CHECK_TTL:
            expired.append(pre_id)
    for pre_id in expired:
        _PRE_CHECK_STORE.pop(pre_id, None)


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

def _compute_risk_breakdown(ctx) -> RiskBreakdown:
    """Multi-dimensional risk scoring."""
    f = ctx.features

    # Behavioral (amount deviation + high count + many receivers)
    dev = min(abs(f.get("amount_deviation", 0)) / 3.0, 1.0)
    cnt = min(f.get("sender_txn_count_24h", 0) / 20, 1.0)
    rcv = min(f.get("sender_unique_receivers_24h", 0) / 10, 1.0)
    behavioral = round((dev * 0.4 + cnt * 0.3 + rcv * 0.3) * 100, 1)

    # Temporal (night + weekend)
    hour = f.get("hour", 12)
    t_score = 1.0 if hour <= 5 else (0.5 if hour >= 22 else 0.0)
    t_score += 0.3 if f.get("is_weekend", 0) else 0.0
    temporal = round(min(t_score, 1.0) * 100, 1)

    # Network
    gi = ctx.graph_info or {}
    n_score = 0.0
    if gi.get("is_mule_suspect"):
        n_score += 0.6
    n_score += min(gi.get("cycle_count", 0) / 5, 0.3)
    n_score += min(gi.get("in_degree", 0) / 15, 0.1)
    network = round(min(n_score, 1.0) * 100, 1)

    # Device
    d_score = 0.0
    if f.get("is_new_device", 0):
        d_score += 0.5
    if any(a.get("type") == "IMPOSSIBLE_TRAVEL" for a in ctx.device_anomalies):
        d_score += 0.5
    device = round(min(d_score, 1.0) * 100, 1)

    return RiskBreakdown(behavioral=behavioral, temporal=temporal, network=network, device=device)


def _run_prediction(
    txn_dict: dict,
    decision_mode: str = "legacy",
    enable_pipeline_audit: bool = False,
    predict_fn_override=None,
):
    """Run the full pipeline on a transaction dict and return ctx."""
    return run_pipeline(
        txn_dict=txn_dict,
        extract_fn=extract_features,
        evaluate_rules_fn=evaluate_rules,
        get_rule_decision_fn=get_rule_decision,
        predict_fn=predict_fn_override or predict_fraud,
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
        audit_fn=log_pipeline_decision if enable_pipeline_audit else None,
        decision_mode=decision_mode,
    )


def _ctx_to_response(ctx) -> dict:
    risk = _compute_risk_breakdown(ctx)
    is_biometric = ctx.decision == "VERIFY"
    if is_biometric:
        status = "PENDING"
    elif ctx.decision == "BLOCK":
        status = "BLOCKED"
    else:
        status = "ALLOWED"
    return {
        "transaction_id": ctx.txn_id,
        "fraud_score": ctx.fraud_score,
        "risk_score": ctx.risk_score,
        "decision": ctx.decision,
        "risk_level": ctx.risk_level,
        "risk_tier": get_risk_tier(float(ctx.risk_score or 0.0)),
        "message": ctx.message,
        "requires_biometric": is_biometric,
        "biometric_methods": ["fingerprint", "face", "iris"] if is_biometric else [],
        "status": status,
        "reasons": ctx.reasons,
        "timestamp": ctx.timestamp,
        "individual_scores": ctx.individual_scores,
        "models_used": ctx.models_used,
        "rules_triggered": [
            {"rule_name": r.rule_name, "reason": r.reason, "action": r.action}
            for r in ctx.rules_triggered
        ],
        "device_anomalies": [
            {"type": a["type"], "severity": a["severity"], "detail": a["detail"]}
            for a in ctx.device_anomalies
        ],
        "graph_info": {k: v for k, v in ctx.graph_info.items()
                        if k in GraphInfo.model_fields} if ctx.graph_info else None,
        "risk_breakdown": risk.model_dump(),
        "advanced_signals": dict(getattr(ctx, "advanced_signals", {}) or {}),
        "user_warning": ctx.user_warning,
        "personalized_threshold": float(getattr(ctx, "personalized_threshold", THRESHOLD_BLOCK) or THRESHOLD_BLOCK),
        "model_version": ctx.model_version,
    }


def _ctx_to_precheck_response(ctx, pre_check_id: str, latency_ms: float) -> dict:
    response = _ctx_to_response(ctx)
    response.update(
        {
            "pre_check_id": pre_check_id,
            "latency_ms": round(float(latency_ms), 2),
        }
    )
    return response


def _ctx_to_bank_response(ctx) -> dict:
    """Return bank-side response contract.

    Contract:
    {
      transaction_id,
      risk_score,
      decision: ALLOW|BLOCK|STEP-UP,
      reason: [...],
                        component_scores: {rules, ml, behavior, graph, anomaly},
      feature_summary: {...}
    }
    """
    bank_score = float(getattr(ctx, "bank_risk_score", 0.0) or getattr(ctx, "risk_score", 0.0) or 0.0)
    decision = str(getattr(ctx, "bank_decision", "") or "").upper()
    if not decision:
        legacy = str(getattr(ctx, "decision", "ALLOW") or "ALLOW").upper()
        decision = "STEP-UP" if legacy == "VERIFY" else legacy

    reasons = list(getattr(ctx, "reasons", []) or [])
    if not reasons:
        reasons = list(getattr(ctx, "decision_reasons", []) or [])

    component_scores = {
        "rules": round(float(getattr(ctx, "rules_score", 0.0) or 0.0), 4),
        "ml": round(float(getattr(ctx, "ml_score", 0.0) or 0.0), 4),
        "behavior": round(float(getattr(ctx, "behavior_score", 0.0) or 0.0), 4),
        "graph": round(float(getattr(ctx, "graph_score", 0.0) or 0.0), 4),
        "anomaly": round(float(getattr(ctx, "anomaly_score", 0.0) or 0.0), 4),
    }

    summary = {
        "rules_score": float(getattr(ctx, "rules_score", 0.0) or 0.0),
        "ml_score": float(getattr(ctx, "ml_score", 0.0) or 0.0),
        "behavior_score": float(getattr(ctx, "behavior_score", 0.0) or 0.0),
        "graph_score": float(getattr(ctx, "graph_score", 0.0) or 0.0),
        "anomaly_score": float(getattr(ctx, "anomaly_score", 0.0) or 0.0),
        "advanced_signals": dict(getattr(ctx, "advanced_signals", {}) or {}),
        "risk_components": dict(getattr(ctx, "risk_components", {}) or {}),
        "key_features": {
            "amount": float((ctx.features or {}).get("amount", 0.0) or 0.0),
            "is_new_device": int((ctx.features or {}).get("is_new_device", 0) or 0),
            "is_new_receiver": int((ctx.features or {}).get("is_new_receiver", 0) or 0),
            "sender_txn_count_1min": float((ctx.features or {}).get("sender_txn_count_1min", 0.0) or 0.0),
            "is_impossible_travel": int((ctx.features or {}).get("is_impossible_travel", 0) or 0),
            "receiver_fraud_flag_count": int((ctx.features or {}).get("receiver_fraud_flag_count", 0) or 0),
        },
    }

    return {
        "transaction_id": str(ctx.txn_id),
        "risk_score": round(bank_score, 4),
        "decision": decision,
        "reason": reasons[:5] if reasons else ["No strong risk signals detected"],
        "component_scores": component_scores,
        "feature_summary": summary,
    }


def _bg_audit(txn_id, sender, receiver, amount, fraud_score, decision, risk_level,
              reasons, rules_names, features, timestamp):
    try:
        log_prediction(
            transaction_id=txn_id, sender_upi=sender, receiver_upi=receiver,
            amount=amount, fraud_score=fraud_score, decision=decision,
            risk_level=risk_level, reasons=reasons, rules_triggered=rules_names,
            features=features, timestamp=timestamp,
        )
    except Exception as e:
        logger.error(f"Audit log failed: {e}")


# =============================================
# Core Endpoints
# =============================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "UPI Fraud Detection API running"
    }


@app.get("/api/v1/predict", include_in_schema=False)
@app.get("/predict", include_in_schema=False)
async def predict_usage_help():
    return {
        "status": "method_help",
        "message": "Do NOT test in browser. Use POST request.",
        "allowed_method": "POST",
        "note": "GET /predict only returns usage guidance.",
        "sample_request": {
            "sender_upi": "alice@upi",
            "receiver_upi": "merchant@upi",
            "amount": 15000,
            "transaction_type": "transfer",
        },
    }

@app.post("/api/v1/predict", response_model=PredictionResponse, include_in_schema=False)
@app.post("/predict", response_model=PredictionResponse,
          summary="Predict fraud for a single transaction",
          description="Runs the full 8-step pipeline: validate → features → rules → ML → decide → explain → device → graph")
@limiter.limit("100/minute")
async def predict(
    request: Request,
    txn: TransactionRequest,
    background_tasks: BackgroundTasks,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "predict")
    start_perf = time.perf_counter()

    def _finish(resp: dict, cache_hit: bool = False):
        elapsed_ms = (time.perf_counter() - start_perf) * 1000.0
        record_latency(elapsed_ms, cache_hit=cache_hit)
        logger.info(
            "predict txn=%s decision=%s risk_score=%.4f latency_ms=%.2f cache_hit=%s",
            resp.get("transaction_id"),
            resp.get("decision"),
            float(resp.get("risk_score") or 0.0),
            elapsed_ms,
            cache_hit,
        )
        return PredictionResponse(**resp)

    try:
        # Idempotency for deterministic demos: compute the final transaction_id (even if omitted)
        # and if it already exists, return the stored outcome.
        tmp_ctx = PipelineContext()
        tmp_ctx = step_validate(tmp_ctx, txn.model_dump())
        txn_id = tmp_ctx.txn_id

        if txn_id:
            existing = get_transaction_by_id(txn_id)
            if existing:
                cached = existing.get("response_json")
                if cached:
                    try:
                        return _finish(json.loads(cached), cache_hit=True)
                    except Exception:
                        # Fall back to legacy reconstruction if cache is invalid.
                        pass

                audit_rec = get_prediction_audit_record(txn_id)
                fraud_score = float(existing.get("fraud_score") or 0.0)
                decision = existing.get("decision") or "ALLOW"

                if decision == "ALLOW":
                    risk_level = "LOW"
                elif decision == "BLOCK":
                    risk_level = "HIGH"
                else:
                    risk_level = "HIGH" if fraud_score >= THRESHOLD_BLOCK else "MEDIUM"

                reasons = []
                if audit_rec and isinstance(audit_rec.get("reasons"), list):
                    reasons = audit_rec.get("reasons")

                if decision == "ALLOW":
                    msg = "Transaction looks normal. Approved."
                elif decision == "BLOCK":
                    msg = "Transaction is high risk and was blocked to protect the user."
                else:
                    msg = "This transaction is unusual. Please verify your identity to prevent fraud."

                # Simplified API status per lock-check spec
                status_simple = "PENDING" if decision == "VERIFY" else ("BLOCKED" if decision == "BLOCK" else "ALLOWED")

                timestamp = existing.get("timestamp") or tmp_ctx.timestamp

                resp = {
                    "transaction_id": existing["transaction_id"],
                    "fraud_score": fraud_score,
                    "risk_score": fraud_score,
                    "decision": decision,
                    "risk_level": risk_level,
                    "message": msg,
                    "requires_biometric": decision == "VERIFY",
                    "biometric_methods": ["fingerprint", "face", "iris"] if decision == "VERIFY" else [],
                    "status": status_simple,
                    "reasons": reasons,
                    "timestamp": timestamp,
                    "individual_scores": {},
                    "models_used": [],
                    "rules_triggered": [],
                    "device_anomalies": [],
                    "graph_info": None,
                    "risk_breakdown": None,
                    "advanced_signals": {},
                    "model_version": MODEL_VERSION,
                }
                return _finish(resp, cache_hit=True)

            ctx = _run_prediction(txn.model_dump())

        if ctx.errors:
            logger.warning(f"Pipeline errors for {ctx.txn_id}: {ctx.errors}")

        record_prediction(ctx.fraud_score, ctx.features)

        resp = _ctx_to_response(ctx)

        rules_names = [r.rule_name for r in ctx.rules_triggered]

        # Persist synchronously for demo stability (immediate idempotent reads).
        save_transaction(
            ctx.txn_id,
            txn.sender_upi,
            txn.receiver_upi,
            txn.amount,
            ctx.fraud_score,
            ctx.decision,
            ctx.timestamp,
            ctx.raw_txn.get("sender_device_id") or "",
            response_json=json.dumps(resp, ensure_ascii=False, separators=(",", ":")),
        )
        _bg_audit(
            ctx.txn_id,
            txn.sender_upi,
            txn.receiver_upi,
            txn.amount,
            ctx.fraud_score,
            ctx.decision,
            ctx.risk_level,
            ctx.reasons,
            rules_names,
            ctx.features,
            ctx.timestamp,
        )

        return _finish(resp, cache_hit=False)
    except Exception as e:
        logger.exception(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/v2/bank/predict",
    response_model=BankPredictionResponse,
    summary="Bank-side real-time fraud decision",
    description=(
        "Unified decision pipeline: feature_extraction -> rules -> ml -> behavior -> graph -> "
        "risk_scoring -> decision -> audit"
    ),
)
@limiter.limit("120/minute")
async def bank_predict(
    request: Request,
    txn: TransactionRequest,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "predict")
    started = time.perf_counter()

    try:
        ctx = _run_prediction(
            txn.model_dump(),
            decision_mode="bank",
            enable_pipeline_audit=True,
            predict_fn_override=predict_ml_probability,
        )
        if ctx.errors:
            logger.warning("Bank pipeline warnings txn=%s: %s", ctx.txn_id, ctx.errors)

        # Monitor bank-side score stream.
        record_prediction(float(ctx.bank_risk_score or ctx.fraud_score or 0.0), ctx.features)

        response = _ctx_to_bank_response(ctx)

        storage_decision = "VERIFY" if response["decision"] == "STEP-UP" else response["decision"]
        save_transaction(
            ctx.txn_id,
            txn.sender_upi,
            txn.receiver_upi,
            txn.amount,
            float(response["risk_score"]),
            storage_decision,
            ctx.timestamp,
            ctx.raw_txn.get("sender_device_id") or "",
            status=_internal_status_from_decision(storage_decision),
            response_json=json.dumps(response, ensure_ascii=False, separators=(",", ":")),
        )

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        record_latency(elapsed_ms, cache_hit=False)
        logger.info(
            "bank_predict txn=%s decision=%s risk_score=%.4f latency_ms=%.2f",
            response.get("transaction_id"),
            response.get("decision"),
            float(response.get("risk_score") or 0.0),
            elapsed_ms,
        )
        return BankPredictionResponse(**response)
    except Exception as exc:
        logger.exception("bank_predict failed: %s", exc)
        raise HTTPException(status_code=500, detail="Unable to process bank-side prediction")


@app.post(
    "/api/v1/pre-check",
    summary="Pre-payment fraud check",
    description="Run risk scoring before UPI PIN entry. Returns user warning payload and pre_check_id.",
)
@limiter.limit("120/minute")
async def pre_check(
    request: Request,
    txn: TransactionRequest,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "predict")
    started = time.perf_counter()
    _cleanup_prechecks()

    try:
        ctx = _run_prediction(txn.model_dump())
        if ctx.errors:
            logger.warning("Pipeline warnings for /api/v1/pre-check txn=%s: %s", ctx.txn_id, ctx.errors)

        record_prediction(ctx.fraud_score, ctx.features)

        pre_check_id = str(uuid4())
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response = _ctx_to_precheck_response(ctx, pre_check_id=pre_check_id, latency_ms=elapsed_ms)

        _PRE_CHECK_STORE[pre_check_id] = {
            "created_at": datetime.utcnow(),
            "txn": txn.model_dump(),
            "ctx_response": response,
            "status": "OPEN",
        }

        record_latency(elapsed_ms, cache_hit=False)
        return response
    except Exception as exc:
        logger.exception("pre-check failed: %s", exc)
        raise HTTPException(status_code=500, detail="Unable to run pre-check right now")


@app.post(
    "/api/v1/pre-check/{pre_check_id}/confirm",
    summary="Confirm warned payment",
    description="User confirms proceed-anyway on warned transaction.",
)
@limiter.limit("120/minute")
async def pre_check_confirm(
    request: Request,
    pre_check_id: str,
    body: PreCheckConfirmRequest,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "predict")
    _cleanup_prechecks()

    item = _PRE_CHECK_STORE.get(pre_check_id)
    if not item:
        raise HTTPException(status_code=404, detail="pre_check_id not found or expired")

    if item.get("status") == "CANCELLED":
        raise HTTPException(status_code=409, detail="This pre-check was cancelled by user")

    txn_payload = dict(item.get("txn") or {})
    ctx = _run_prediction(txn_payload)
    response = _ctx_to_response(ctx)
    response["pre_check_id"] = pre_check_id
    response["user_override"] = bool(body.user_override)

    final_decision = "ALLOW" if bool(body.user_override) else str(ctx.decision or "ALLOW").upper()
    final_status = "ALLOWED" if final_decision == "ALLOW" else _internal_status_from_decision(final_decision)

    response["decision"] = final_decision
    response["status"] = final_status

    save_transaction(
        ctx.txn_id,
        txn_payload.get("sender_upi"),
        txn_payload.get("receiver_upi"),
        float(txn_payload.get("amount", 0.0) or 0.0),
        float(ctx.fraud_score or 0.0),
        final_decision,
        ctx.timestamp,
        txn_payload.get("sender_device_id") or "",
        status=final_status,
        response_json=json.dumps(response, ensure_ascii=False, separators=(",", ":")),
    )

    _bg_audit(
        ctx.txn_id,
        str(txn_payload.get("sender_upi") or ""),
        str(txn_payload.get("receiver_upi") or ""),
        float(txn_payload.get("amount", 0.0) or 0.0),
        float(ctx.fraud_score or 0.0),
        final_decision,
        str(ctx.risk_level or "MEDIUM"),
        list(ctx.reasons or []),
        [r.rule_name for r in (ctx.rules_triggered or [])],
        ctx.features,
        ctx.timestamp,
    )

    item["status"] = "CONFIRMED"
    item["confirmed_at"] = datetime.utcnow()
    item["transaction_id"] = ctx.txn_id
    return response


@app.post(
    "/api/v1/pre-check/{pre_check_id}/cancel",
    summary="Cancel warned payment",
    description="User cancels transaction from warning popup.",
)
@limiter.limit("120/minute")
async def pre_check_cancel(
    request: Request,
    pre_check_id: str,
    body: PreCheckCancelRequest,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "predict")
    _cleanup_prechecks()

    item = _PRE_CHECK_STORE.get(pre_check_id)
    if not item:
        raise HTTPException(status_code=404, detail="pre_check_id not found or expired")

    txn_payload = dict(item.get("txn") or {})
    cached = dict(item.get("ctx_response") or {})
    txn_id = str(cached.get("transaction_id") or f"PRECHK_{uuid4().hex[:12]}")
    score = float(cached.get("fraud_score") or 0.0)

    response = {
        "status": "CANCELLED",
        "pre_check_id": pre_check_id,
        "transaction_id": txn_id,
        "message": str(body.reason or "User cancelled payment after warning"),
        "risk_score": score,
    }

    save_transaction(
        txn_id,
        txn_payload.get("sender_upi"),
        txn_payload.get("receiver_upi"),
        float(txn_payload.get("amount", 0.0) or 0.0),
        score,
        "BLOCK",
        datetime.utcnow().isoformat(),
        txn_payload.get("sender_device_id") or "",
        status="CANCELLED",
        response_json=json.dumps(response, ensure_ascii=False, separators=(",", ":")),
    )

    item["status"] = "CANCELLED"
    item["cancelled_at"] = datetime.utcnow()
    return response


@app.post(
    "/pay",
    summary="User-facing UPI payment with ShieldPay protection",
    description="Runs the fraud pipeline and returns user-friendly language without exposing internal model fields.",
)
@limiter.limit("80/minute")
async def pay_transaction(
    request: Request,
    body: PayRequest,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "predict")
    start_perf = time.perf_counter()

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
        if ctx.errors:
            logger.warning("Pipeline warnings for /pay txn=%s: %s", ctx.txn_id, ctx.errors)

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
        _bg_audit(
            ctx.txn_id,
            sender_upi,
            receiver_upi,
            body.amount,
            ctx.fraud_score,
            decision,
            ctx.risk_level,
            [user_reason],
            [r.rule_name for r in ctx.rules_triggered],
            ctx.features,
            ctx.timestamp,
        )

        elapsed_ms = (time.perf_counter() - start_perf) * 1000.0
        record_latency(elapsed_ms, cache_hit=False)
        logger.info(
            "pay txn=%s decision=%s status=%s latency_ms=%.2f",
            ctx.txn_id,
            decision,
            status,
            elapsed_ms,
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/pay failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to process payment right now")


@app.get(
    "/receiver/info",
    summary="Receiver lookup for payment entry",
    description="Returns receiver display information and risk level while user types a UPI ID.",
)
@limiter.limit("240/minute")
async def receiver_info(
    request: Request,
    upi_id: str,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "transactions")
    normalized_upi = _normalize_upi(upi_id)
    if not normalized_upi:
        raise HTTPException(status_code=422, detail="upi_id is required")
    return _receiver_info_snapshot(normalized_upi)


@app.get(
    "/my/transactions",
    summary="Fetch current user's transaction history",
    description="Returns sender-filtered, user-friendly transaction rows.",
)
@limiter.limit("60/minute")
async def my_transactions(
    request: Request,
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


@app.get(
    "/my/security-score",
    summary="Get personal ShieldPay security score",
    description="Returns a personal score, level, protected amount, and recent alerts for one UPI profile.",
)
@limiter.limit("60/minute")
async def my_security_score(
    request: Request,
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


@app.post(
    "/my/report-fraud",
    summary="Report unauthorized transaction",
    description="Creates a support case and marks the sender profile as compromised.",
)
@limiter.limit("30/minute")
async def report_fraud(
    request: Request,
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
    except Exception as e:
        db.rollback()
        logger.exception("/my/report-fraud failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to submit report right now")
    finally:
        db.close()


@app.post("/predict/batch", response_model=BatchPredictSummary,
          summary="Batch predict from CSV upload",
          description="Upload a CSV file with columns: sender_upi, receiver_upi, amount, transaction_type, sender_device_id")
@limiter.limit("10/minute")
async def batch_predict(
    request: Request,
    file: UploadFile = File(...),
    client: dict = Depends(get_current_client),
):
    check_permission(client, "predict")
    start = time.time()

    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))

    results = []
    blocked, flagged, allowed = 0, 0, 0

    for row in reader:
        try:
            txn_dict = {
                "sender_upi": row.get("sender_upi", ""),
                "receiver_upi": row.get("receiver_upi", ""),
                "amount": float(row.get("amount", 0)),
                "transaction_type": row.get("transaction_type", "purchase"),
                "sender_device_id": row.get("sender_device_id", "BATCH"),
                "timestamp": row.get("timestamp", datetime.now().isoformat()),
            }
            ctx = _run_prediction(txn_dict)
            record_prediction(ctx.fraud_score, ctx.features)

            if ctx.decision == "BLOCK":
                blocked += 1
            elif ctx.decision == "VERIFY":
                flagged += 1
            else:
                allowed += 1

            results.append({
                "transaction_id": ctx.txn_id,
                "fraud_score": ctx.fraud_score,
                "decision": ctx.decision,
                "reasons": ctx.reasons[:2],
            })
        except Exception as e:
            results.append({"error": str(e), "row": row})

    elapsed = round((time.time() - start) * 1000, 1)

    # Top 10 high risk
    high_risk = sorted([r for r in results if "fraud_score" in r],
                       key=lambda x: x["fraud_score"], reverse=True)[:10]

    return BatchPredictSummary(
        total_processed=len(results),
        blocked_count=blocked,
        flagged_count=flagged,
        allowed_count=allowed,
        processing_time_ms=elapsed,
        high_risk_transactions=high_risk,
    )


# =============================================
# Feedback
# =============================================

@app.post("/feedback", summary="Submit analyst feedback",
          description="Label a transaction as confirmed_fraud, false_positive, or true_negative. Feeds into retraining pipeline.")
@limiter.limit("60/minute")
async def submit_feedback(request: Request, fb: FeedbackRequest, client: dict = Depends(get_current_client)):
    check_permission(client, "predict")
    save_feedback(fb.transaction_id, fb.analyst_verdict, fb.analyst_notes or "")
    return {"status": "ok", "transaction_id": fb.transaction_id, "verdict": fb.analyst_verdict}

@app.get("/feedback/stats", summary="Feedback statistics",
         description="Aggregate stats on analyst verdicts -- false positive rate, confirmed fraud rate, etc.")
async def feedback_stats(client: dict = Depends(get_current_client)):
    return get_feedback_stats()


# =============================================
# Biometric Verification
# =============================================

@app.post("/api/v1/biometric/verify", include_in_schema=False)
@app.post("/verify", summary="Simulate biometric verification",
          description="Alias for /verify-biometric")
@app.post("/verify-biometric", summary="Simulate biometric verification",
          description="Simulate fingerprint/face verification for a PENDING_VERIFICATION transaction. Returns VERIFIED/FAILED and final decision.")
@limiter.limit("30/minute")
async def verify_biometric_endpoint(
    request: Request,
    body: dict,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "predict")
    txn_id = body.get("transaction_id")
    method = body.get("method", "fingerprint")
    if not txn_id:
        raise HTTPException(status_code=422, detail="transaction_id is required")
    if method not in ("fingerprint", "face", "iris"):
        raise HTTPException(status_code=422, detail="method must be one of: fingerprint, face, iris")
    result = verify_biometric(txn_id, method=method)
    if result["verification_status"] == "ERROR":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


# =============================================
# Fraud History / Flagged Users
# =============================================

@app.get("/fraud-history/flagged", summary="Get flagged users",
         description="List users with fraud history, sorted by fraud count.")
async def flagged_users(limit: int = 50, client: dict = Depends(get_current_client)):
    check_permission(client, "audit")
    users = get_flagged_users(limit=limit)
    return {"flagged_users": users, "total": len(users)}


# =============================================
# WebSocket Live Feed
# =============================================

@app.websocket("/ws/live-feed")
async def ws_live_feed(websocket: WebSocket):
    def pipeline_fn(txn):
        ctx = _run_prediction(txn)
        return _ctx_to_response(ctx)
    await live_feed_handler(websocket, pipeline_fn)


# =============================================
# Monitoring & Model Info
# =============================================

@app.get("/model/info", summary="Model metadata and performance metrics",
         description="Returns training metrics, CV results, thresholds, feature importances, and version info.")
async def model_info(client: dict = Depends(get_current_client)):
    return get_metadata()

@app.get("/transactions", summary="Recent transactions")
@limiter.limit("60/minute")
async def list_transactions(request: Request, limit: int = 50, client: dict = Depends(get_current_client)):
    check_permission(client, "transactions")
    return get_transactions(limit)

@app.post("/api/v1/token", response_model=TokenResponse, include_in_schema=False)
@app.post("/auth/token", response_model=TokenResponse, summary="Get JWT token from API key")
async def get_token(req: TokenRequest):
    try:
        return TokenResponse(access_token=create_access_token(req.api_key))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.get("/monitoring/drift", summary="Feature drift report (PSI)")
@limiter.limit("10/minute")
async def drift_report(request: Request, client: dict = Depends(get_current_client)):
    check_permission(client, "audit")
    return get_drift_report()

@app.get("/monitoring/stats", summary="Prediction statistics")
@limiter.limit("30/minute")
async def prediction_stats(request: Request, client: dict = Depends(get_current_client)):
    return get_prediction_stats()

@app.get("/monitoring/latency", summary="Predict API latency statistics")
@limiter.limit("30/minute")
async def latency_stats(request: Request, client: dict = Depends(get_current_client)):
    return get_latency_stats()

@app.get("/monitoring/graph", summary="Transaction graph statistics")
@limiter.limit("10/minute")
async def graph_stats(request: Request, client: dict = Depends(get_current_client)):
    return get_graph().get_graph_stats()

@app.get("/monitoring/store", summary="History store backend info")
async def store_stats():
    return get_store_stats()

@app.get("/api/v1/audit", include_in_schema=False)
@app.get("/audit/logs", summary="Immutable audit trail")
@limiter.limit("10/minute")
async def audit_logs(request: Request, date: str = None, limit: int = 100,
                     client: dict = Depends(get_current_client)):
    check_permission(client, "audit")
    return get_audit_logs(date, limit)


@app.get("/api/v1/rbi/report", include_in_schema=False)
async def rbi_report_alias(days: int = 30, client: dict = Depends(get_current_client)):
    check_permission(client, "audit")
    return generate_rbi_report(days)


# Legacy/API-v1 compatibility routers.
# Added after primary routes so duplicate root paths continue using primary handlers.
app.include_router(user_router)
app.include_router(cases_router, prefix="/api/v1")
app.include_router(rbi_router, prefix="/api/v1")


# =============================================
# Health Checks
# =============================================

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/health/live", summary="Liveness probe (Kubernetes)")
async def liveness():
    return {"status": "alive"}

@app.get("/health/ready", summary="Readiness probe — checks all subsystems")
async def readiness():
    checks = {}
    all_ok = True

    # DB
    try:
        from .database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        all_ok = False

    # Models
    from .predict import _models
    if _models:
        checks["models"] = {"status": "ok", "loaded": list(_models.keys()), "version": MODEL_VERSION}
    else:
        checks["models"] = "not loaded"
        all_ok = False

    # Graph
    try:
        checks["graph"] = get_graph().get_graph_stats()
    except Exception:
        checks["graph"] = "error"

    # Store
    checks["store"] = get_store_stats()

    status_code = 200 if all_ok else 503
    return {"status": "ready" if all_ok else "degraded", "checks": checks}
