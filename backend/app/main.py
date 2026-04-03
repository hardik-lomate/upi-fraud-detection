"""
UPI Fraud Detection API — Main Application.
Uses pipeline.py as the central controller. No prediction logic here.
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import MODEL_VERSION

from .models import (
    TransactionRequest, PredictionResponse, TokenRequest, TokenResponse,
    RuleDetail, DeviceAnomaly, GraphInfo,
)
from .predict import predict_fraud, load_all_models
from .feature_extract import extract_features, sender_history
from .database import save_transaction, get_transactions, init_db, load_recent_history
from .rules_engine import evaluate_rules, get_rule_decision
from .explainability import explain_prediction, format_reasons
from .audit import log_prediction, get_audit_logs
from .auth import get_current_client, check_permission, create_access_token
from .monitoring import record_prediction, get_drift_report, get_prediction_stats, load_reference_distribution
from .device_fingerprint import check_device_anomalies, update_device_history
from .graph_features import get_graph
from .pipeline import run_pipeline

# --- Rate Limiter ---
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="UPI Fraud Detection API",
    version="2.0.0",
    description="Industry-grade real-time fraud detection with ensemble ML, SHAP, graph analysis, and compliance logging.",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================
# Startup
# =============================================

def _hydrate_sender_history():
    records = load_recent_history(days=7)
    graph = get_graph()
    count = 0
    for r in records:
        sender = r["sender_upi"]
        if sender not in sender_history:
            sender_history[sender] = {"transactions": [], "devices": set(), "receivers": set()}
        hist = sender_history[sender]
        try:
            ts = datetime.fromisoformat(r["timestamp"])
        except (ValueError, TypeError):
            ts = datetime.utcnow()
        hist["transactions"].append((ts, r["amount"], r["device_id"], r["receiver_upi"]))
        hist["devices"].add(r["device_id"])
        hist["receivers"].add(r["receiver_upi"])
        graph.add_transaction(sender, r["receiver_upi"], r["amount"], r["timestamp"])
        count += 1
    print(f"Hydrated: {count} transactions, {len(sender_history)} senders, "
          f"{graph.get_graph_stats()['total_nodes']} graph nodes")


@app.on_event("startup")
def startup():
    init_db()
    load_all_models()
    _hydrate_sender_history()
    load_reference_distribution()


# =============================================
# Background Tasks
# =============================================

def _bg_save(txn_id, sender, receiver, amount, fraud_score, decision, timestamp, device_id):
    save_transaction(txn_id, sender, receiver, amount, fraud_score, decision, timestamp, device_id)

def _bg_audit(txn_id, sender, receiver, amount, fraud_score, decision, risk_level,
              reasons, rules_names, features, timestamp):
    log_prediction(
        transaction_id=txn_id, sender_upi=sender, receiver_upi=receiver,
        amount=amount, fraud_score=fraud_score, decision=decision,
        risk_level=risk_level, reasons=reasons, rules_triggered=rules_names,
        features=features, timestamp=timestamp,
    )


# =============================================
# Endpoints
# =============================================

@app.post("/predict", response_model=PredictionResponse)
@limiter.limit("100/minute")
async def predict(
    request: Request,
    txn: TransactionRequest,
    background_tasks: BackgroundTasks,
    client: dict = Depends(get_current_client),
):
    check_permission(client, "predict")
    try:
        txn_dict = txn.dict()

        # === CENTRAL PIPELINE ===
        ctx = run_pipeline(
            txn_dict=txn_dict,
            extract_fn=extract_features,
            evaluate_rules_fn=evaluate_rules,
            get_rule_decision_fn=get_rule_decision,
            predict_fn=predict_fraud,
            explain_fn=explain_prediction,
            format_reasons_fn=format_reasons,
            check_device_fn=check_device_anomalies,
            update_device_fn=update_device_history,
            sender_history=sender_history,
            graph=get_graph(),
        )

        # Monitoring
        record_prediction(ctx.fraud_score, ctx.features)

        # Async DB + Audit
        rules_names = [r.rule_name for r in ctx.rules_triggered]
        background_tasks.add_task(
            _bg_save, ctx.txn_id, txn.sender_upi, txn.receiver_upi,
            txn.amount, ctx.fraud_score, ctx.decision, ctx.timestamp, txn.sender_device_id,
        )
        background_tasks.add_task(
            _bg_audit, ctx.txn_id, txn.sender_upi, txn.receiver_upi,
            txn.amount, ctx.fraud_score, ctx.decision, ctx.risk_level,
            ctx.reasons, rules_names, ctx.features, ctx.timestamp,
        )

        return PredictionResponse(
            transaction_id=ctx.txn_id,
            fraud_score=ctx.fraud_score,
            decision=ctx.decision,
            risk_level=ctx.risk_level,
            message=ctx.message,
            reasons=ctx.reasons,
            individual_scores=ctx.individual_scores,
            models_used=ctx.models_used,
            rules_triggered=[
                RuleDetail(rule_name=r.rule_name, reason=r.reason, action=r.action)
                for r in ctx.rules_triggered
            ],
            device_anomalies=[
                DeviceAnomaly(type=a["type"], severity=a["severity"], detail=a["detail"])
                for a in ctx.device_anomalies
            ],
            graph_info=GraphInfo(**{k: v for k, v in ctx.graph_info.items()
                                    if k in GraphInfo.__fields__}) if ctx.graph_info else None,
            model_version=ctx.model_version,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transactions")
@limiter.limit("60/minute")
async def list_transactions(request: Request, limit: int = 50, client: dict = Depends(get_current_client)):
    check_permission(client, "transactions")
    return get_transactions(limit)

@app.post("/auth/token", response_model=TokenResponse)
async def get_token(req: TokenRequest):
    try:
        token = create_access_token(req.api_key)
        return TokenResponse(access_token=token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.get("/monitoring/drift")
@limiter.limit("10/minute")
async def drift_report(request: Request, client: dict = Depends(get_current_client)):
    check_permission(client, "audit")
    return get_drift_report()

@app.get("/monitoring/stats")
@limiter.limit("30/minute")
async def prediction_stats(request: Request, client: dict = Depends(get_current_client)):
    return get_prediction_stats()

@app.get("/monitoring/graph")
@limiter.limit("10/minute")
async def graph_stats(request: Request, client: dict = Depends(get_current_client)):
    return get_graph().get_graph_stats()

@app.get("/audit/logs")
@limiter.limit("10/minute")
async def audit_logs(request: Request, date: str = None, limit: int = 100,
                     client: dict = Depends(get_current_client)):
    check_permission(client, "audit")
    return get_audit_logs(date, limit)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "model_version": MODEL_VERSION,
            "timestamp": datetime.now().isoformat()}
