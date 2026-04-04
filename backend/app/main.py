"""
UPI Fraud Detection API — Main Application (v2.0.0).
Central controller: pipeline.py. All features wired. Zero business logic here.
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, WebSocket, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from datetime import datetime
import logging
import time
import io
import csv
import os

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import MODEL_VERSION, THRESHOLD_BLOCK

from .models import (
    TransactionRequest, PredictionResponse, TokenRequest, TokenResponse,
    RuleDetail, DeviceAnomaly, GraphInfo, RiskBreakdown,
    FeedbackRequest, BatchPredictSummary,
)
from .predict import predict_fraud, load_all_models, get_metadata, get_thresholds
from .feature_extract import extract_features
from .history_store import hydrate_from_db, get_store_stats
from .database import (
    save_transaction,
    get_transactions,
    init_db,
    load_recent_history,
    get_flagged_users,
    get_transaction_by_id,
)
from .rules_engine import evaluate_rules, get_rule_decision
from .explainability import explain_prediction, format_reasons
from .audit import log_prediction, get_audit_logs, get_prediction_audit_record
from .auth import get_current_client, check_permission, create_access_token
from .monitoring import record_prediction, get_drift_report, get_prediction_stats, load_reference_distribution
from .device_fingerprint import check_device_anomalies, update_device_history
from .graph_features import get_graph
from .pipeline import run_pipeline
from .pipeline import PipelineContext, step_validate
from .feedback import save_feedback, get_feedback_stats
from .live_feed import live_feed_handler
from .biometric import verify_biometric

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("upi_fraud")

# --- App ---
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="UPI Fraud Detection API",
    version="2.0.0",
    description=(
        "Real-time UPI fraud detection with ensemble ML (XGBoost + LightGBM + IsoForest), "
        "SHAP explainability, graph analysis, rules engine, and compliance audit logging."
    ),
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================
# Startup
# =============================================

@app.on_event("startup")
def startup():
    logger.info("=== Starting UPI Fraud Detection API ===")
    init_db()
    load_all_models()
    records = load_recent_history(days=7)
    hydrate_from_db(records)
    graph = get_graph()
    for r in records:
        graph.add_transaction(r["sender_upi"], r["receiver_upi"], r["amount"], r["timestamp"])
    load_reference_distribution()
    logger.info(f"Store: {get_store_stats()}")
    logger.info("=== Ready ===")


# =============================================
# Helpers
# =============================================

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


def _run_prediction(txn_dict: dict):
    """Run the full pipeline on a transaction dict and return ctx."""
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


def _ctx_to_response(ctx) -> dict:
    risk = _compute_risk_breakdown(ctx)
    is_biometric = ctx.decision == "VERIFY"
    if is_biometric:
        status = "PENDING_VERIFICATION"
    elif ctx.decision == "BLOCK":
        status = "BLOCKED"
    else:
        status = "ALLOWED"
    return {
        "transaction_id": ctx.txn_id,
        "fraud_score": ctx.fraud_score,
        "decision": ctx.decision,
        "risk_level": ctx.risk_level,
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
        "model_version": ctx.model_version,
    }


def _bg_save(txn_id, sender, receiver, amount, fraud_score, decision, timestamp, device_id):
    try:
        save_transaction(txn_id, sender, receiver, amount, fraud_score, decision, timestamp, device_id)
    except Exception as e:
        logger.error(f"DB save failed: {e}")


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
    try:
        # Idempotency for deterministic demos: compute the final transaction_id (even if omitted)
        # and if it already exists, return the stored outcome.
        tmp_ctx = PipelineContext()
        tmp_ctx = step_validate(tmp_ctx, txn.model_dump())
        txn_id = tmp_ctx.txn_id

        if txn_id:
            existing = get_transaction_by_id(txn_id)
            if existing:
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

                status = existing.get("status") or (
                    "PENDING_VERIFICATION" if decision == "VERIFY" else ("BLOCKED" if decision == "BLOCK" else "ALLOWED")
                )

                timestamp = existing.get("timestamp") or tmp_ctx.timestamp

                resp = {
                    "transaction_id": existing["transaction_id"],
                    "fraud_score": fraud_score,
                    "decision": decision,
                    "risk_level": risk_level,
                    "message": msg,
                    "requires_biometric": decision == "VERIFY",
                    "biometric_methods": ["fingerprint", "face", "iris"] if decision == "VERIFY" else [],
                    "status": status,
                    "reasons": reasons,
                    "timestamp": timestamp,
                    "individual_scores": {},
                    "models_used": [],
                    "rules_triggered": [],
                    "device_anomalies": [],
                    "graph_info": None,
                    "risk_breakdown": None,
                    "model_version": MODEL_VERSION,
                }
                return PredictionResponse(**resp)

            ctx = _run_prediction(txn.model_dump())

        if ctx.errors:
            logger.warning(f"Pipeline errors for {ctx.txn_id}: {ctx.errors}")

        record_prediction(ctx.fraud_score, ctx.features)

        rules_names = [r.rule_name for r in ctx.rules_triggered]
        # Persist synchronously for demo stability (immediate idempotent reads).
        _bg_save(
            ctx.txn_id,
            txn.sender_upi,
            txn.receiver_upi,
            txn.amount,
            ctx.fraud_score,
            ctx.decision,
            ctx.timestamp,
            ctx.raw_txn.get("sender_device_id") or "",
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

        resp = _ctx_to_response(ctx)
        return PredictionResponse(**resp)
    except Exception as e:
        logger.exception(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

@app.get("/monitoring/graph", summary="Transaction graph statistics")
@limiter.limit("10/minute")
async def graph_stats(request: Request, client: dict = Depends(get_current_client)):
    return get_graph().get_graph_stats()

@app.get("/monitoring/store", summary="History store backend info")
async def store_stats():
    return get_store_stats()

@app.get("/audit/logs", summary="Immutable audit trail")
@limiter.limit("10/minute")
async def audit_logs(request: Request, date: str = None, limit: int = 100,
                     client: dict = Depends(get_current_client)):
    check_permission(client, "audit")
    return get_audit_logs(date, limit)


# =============================================
# Health Checks
# =============================================

@app.get("/health", summary="Quick health check")
async def health():
    return {
        "status": "ok", "version": "2.0.0",
        "model_version": MODEL_VERSION,
        "store": get_store_stats(),
        "timestamp": datetime.now().isoformat(),
    }

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
