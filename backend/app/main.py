"""
UPI Fraud Detection API — Industry-Grade Main Application.

Integrates: Ensemble ML, Rules Engine, SHAP Explainability, Graph Analysis,
Device Fingerprinting, Model Monitoring, JWT Auth, Audit Trail, Async DB.
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from datetime import datetime
import uuid

from .models import (
    TransactionRequest, PredictionResponse, TokenRequest, TokenResponse,
    RuleDetail, DeviceAnomaly, GraphInfo,
)
from .predict import predict_fraud, load_all_models, get_feature_columns
from .feature_extract import extract_features, sender_history
from .decision_engine import make_decision
from .database import save_transaction, get_transactions, init_db, load_recent_history
from .rules_engine import evaluate_rules, get_rule_decision
from .explainability import explain_prediction, format_reasons
from .audit import log_prediction, log_auth_event, get_audit_logs, MODEL_VERSION
from .auth import get_current_client, check_permission, create_access_token
from .monitoring import record_prediction, get_drift_report, get_prediction_stats, load_reference_distribution
from .device_fingerprint import check_device_anomalies, update_device_history
from .graph_features import get_graph

# --- Rate Limiter ---
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="UPI Fraud Detection API",
    version="2.0.0",
    description="Industry-grade real-time fraud detection with ensemble ML, SHAP explainability, graph analysis, and compliance logging.",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
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
    """Rebuild in-memory sender history from DB on startup."""
    records = load_recent_history(days=7)
    graph = get_graph()
    count = 0
    for r in records:
        sender = r["sender_upi"]
        if sender not in sender_history:
            sender_history[sender] = {
                "transactions": [], "devices": set(), "receivers": set(),
            }
        hist = sender_history[sender]
        try:
            ts = datetime.fromisoformat(r["timestamp"])
        except (ValueError, TypeError):
            ts = datetime.utcnow()
        hist["transactions"].append((ts, r["amount"], r["device_id"], r["receiver_upi"]))
        hist["devices"].add(r["device_id"])
        hist["receivers"].add(r["receiver_upi"])

        # Also hydrate graph
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

def _background_save(txn_id, sender, receiver, amount, fraud_score, decision, timestamp, device_id):
    """Non-blocking DB write."""
    save_transaction(txn_id, sender, receiver, amount, fraud_score, decision, timestamp, device_id)


def _background_audit(txn_id, sender, receiver, amount, fraud_score, decision, risk_level,
                       reasons, rules_names, features, timestamp):
    """Non-blocking audit log write."""
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
        txn_id = txn.transaction_id or f"TXN_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        timestamp = txn.timestamp or datetime.now().isoformat()
        txn_dict = txn.dict()
        txn_dict["timestamp"] = timestamp

        # --- Step 1: Extract ML features ---
        features = extract_features(txn_dict)

        # --- Step 2: Rules Engine (pre-ML) ---
        # Enrich txn_dict with behavioral context for rules
        txn_dict["_sender_txn_count"] = features.get("sender_txn_count_24h", 0)
        txn_dict["_sender_txn_count_1h"] = features.get("sender_txn_count_24h", 0)  # approximation
        txn_dict["_sender_total_24h"] = features.get("sender_avg_amount", 0) * features.get("sender_txn_count_24h", 0)
        txn_dict["_is_new_device"] = features.get("is_new_device", 0) == 1

        triggered_rules = evaluate_rules(txn_dict)
        rule_decision = get_rule_decision(triggered_rules)

        rules_detail = [
            RuleDetail(rule_name=r.rule_name, reason=r.reason, action=r.action)
            for r in triggered_rules
        ]

        # --- Step 3: Ensemble ML prediction ---
        prediction = predict_fraud(features)
        fraud_score = prediction["ensemble_score"]
        individual_scores = prediction["individual_scores"]
        models_used = prediction["models_used"]

        # --- Step 4: Decision (rules override ML) ---
        if rule_decision == "BLOCK":
            decision, risk_level = "BLOCK", "HIGH"
            message = f"Blocked by rule: {triggered_rules[0].rule_name}"
        elif rule_decision == "FLAG":
            ml_decision, ml_risk, ml_message = make_decision(fraud_score)
            decision = "FLAG"  # Upgrade to FLAG at minimum
            risk_level = "HIGH" if ml_risk == "HIGH" else "MEDIUM"
            message = f"Flagged by rule: {triggered_rules[0].rule_name}. ML score: {fraud_score:.1%}"
        else:
            decision, risk_level, message = make_decision(fraud_score)

        # --- Step 5: SHAP Explainability ---
        try:
            feature_columns = get_feature_columns()
            explanations = explain_prediction(features, feature_columns, top_n=5)
            reasons = format_reasons(explanations)
        except Exception as e:
            reasons = [f"Explainability unavailable: {str(e)}"]

        # --- Step 6: Device Fingerprinting ---
        device_anomalies_raw = check_device_anomalies(txn_dict, sender_history)
        device_anomalies = [
            DeviceAnomaly(type=a["type"], severity=a["severity"], detail=a["detail"])
            for a in device_anomalies_raw
        ]
        update_device_history(txn_dict, sender_history)

        # Upgrade decision if impossible travel detected
        if any(a.type == "IMPOSSIBLE_TRAVEL" for a in device_anomalies):
            if decision == "ALLOW":
                decision, risk_level = "FLAG", "MEDIUM"
                message = "Flagged: Impossible travel detected"

        # --- Step 7: Graph Analysis ---
        graph = get_graph()
        graph.add_transaction(txn.sender_upi, txn.receiver_upi, txn.amount, timestamp)
        graph_data = graph.get_node_features(txn.sender_upi)
        graph_info = GraphInfo(
            out_degree=graph_data["out_degree"],
            in_degree=graph_data["in_degree"],
            pagerank=graph_data["pagerank"],
            is_hub=graph_data["is_hub"],
            is_mule_suspect=graph_data["is_mule_suspect"],
            cycle_count=graph_data["cycle_count"],
        )

        # Flag mule suspects
        if graph_data["is_mule_suspect"] and decision == "ALLOW":
            decision, risk_level = "FLAG", "MEDIUM"
            message = "Flagged: Receiver shows mule account pattern"

        # --- Step 8: Monitoring ---
        record_prediction(fraud_score, features)

        # --- Step 9: Background DB + Audit (async, non-blocking) ---
        rules_names = [r.rule_name for r in triggered_rules]
        background_tasks.add_task(
            _background_save, txn_id, txn.sender_upi, txn.receiver_upi,
            txn.amount, fraud_score, decision, timestamp, txn.sender_device_id,
        )
        background_tasks.add_task(
            _background_audit, txn_id, txn.sender_upi, txn.receiver_upi,
            txn.amount, fraud_score, decision, risk_level, reasons, rules_names,
            features, timestamp,
        )

        return PredictionResponse(
            transaction_id=txn_id,
            fraud_score=fraud_score,
            decision=decision,
            risk_level=risk_level,
            message=message,
            reasons=reasons,
            individual_scores=individual_scores,
            models_used=models_used,
            rules_triggered=rules_detail,
            device_anomalies=device_anomalies,
            graph_info=graph_info,
            model_version=MODEL_VERSION,
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
    """Exchange an API key for a JWT token."""
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
    graph = get_graph()
    return graph.get_graph_stats()


@app.get("/audit/logs")
@limiter.limit("10/minute")
async def audit_logs(request: Request, date: str = None, limit: int = 100,
                     client: dict = Depends(get_current_client)):
    check_permission(client, "audit")
    return get_audit_logs(date, limit)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "model_version": MODEL_VERSION,
        "timestamp": datetime.now().isoformat(),
    }
