"""
Pipeline Controller — Central orchestrator for the prediction pipeline.

This is the ONLY place where the execution flow is defined.
No scattered logic — one clear sequence:

    input → validate → features → rules → ML → decide → explain → log

Every step returns structured data. Every step is independently testable.
"""

from datetime import datetime
import uuid
from dataclasses import dataclass, field
from typing import Optional
from hashlib import sha1

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import MODEL_VERSION

from .feature_columns import get_feature_columns, validate_feature_dict


@dataclass
class PipelineContext:
    """Carries data through every pipeline step. Single object, no scattered state."""
    # Input
    txn_id: str = ""
    raw_txn: dict = field(default_factory=dict)
    timestamp: str = ""

    # Step 1: Features
    features: dict = field(default_factory=dict)

    # Step 2: Rules
    rules_triggered: list = field(default_factory=list)
    rule_decision: Optional[str] = None  # "BLOCK", "FLAG", or None

    # Step 3: ML
    fraud_score: float = 0.0
    individual_scores: dict = field(default_factory=dict)
    models_used: list = field(default_factory=list)

    # Step 4: Decision
    decision: str = "ALLOW"
    risk_level: str = "LOW"
    message: str = ""

    # Step 5: Explainability
    reasons: list = field(default_factory=list)
    decision_reasons: list = field(default_factory=list)

    # Step 6: Device
    device_anomalies: list = field(default_factory=list)

    # Step 7: Graph
    graph_info: dict = field(default_factory=dict)

    # Metadata
    model_version: str = MODEL_VERSION
    processing_steps: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def step_validate(ctx: PipelineContext, txn_dict: dict) -> PipelineContext:
    """Step 0: Validate and normalize input."""
    ctx.txn_id = txn_dict.get("transaction_id") or (
        f"TXN_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )
    raw_ts = txn_dict.get("timestamp")
    if raw_ts:
        try:
            ts_str = str(raw_ts)
            if ts_str.endswith("Z"):
                ts_str = ts_str[:-1] + "+00:00"
            parsed = datetime.fromisoformat(ts_str)
            ctx.timestamp = parsed.isoformat()
        except Exception:
            ctx.timestamp = datetime.now().isoformat()
            ctx.errors.append("Validation warning: invalid timestamp; using server time")
    else:
        ctx.timestamp = datetime.now().isoformat()

    raw = {**txn_dict, "timestamp": ctx.timestamp}

    sender = (raw.get("sender_upi") or "").strip()
    receiver = (raw.get("receiver_upi") or "").strip()
    raw["sender_upi"] = sender
    raw["receiver_upi"] = receiver

    if not sender or not receiver:
        ctx.errors.append("Validation failed: sender_upi and receiver_upi are required")

    try:
        raw["amount"] = float(raw.get("amount"))
    except (TypeError, ValueError):
        raw["amount"] = 0.0
        ctx.errors.append("Validation failed: amount must be a number")

    # Context auto-generation (do not rely on frontend): device_id, IP, location.
    sender_hash = sha1(sender.encode("utf-8")).hexdigest() if sender else sha1(b"unknown").hexdigest()

    dev = raw.get("sender_device_id")
    if not dev:
        raw["sender_device_id"] = f"DEV_{sender_hash[:10]}"

    ip = raw.get("sender_ip")
    if not ip:
        b1 = int(sender_hash[0:2], 16)
        b2 = int(sender_hash[2:4], 16)
        b3 = int(sender_hash[4:6], 16)
        raw["sender_ip"] = f"10.{b1}.{b2}.{b3}"

    if raw.get("sender_location_lat") is None or raw.get("sender_location_lon") is None:
        # Stable pseudo-location roughly within India bounds.
        lat_seed = int(sender_hash[6:10], 16) / 0xFFFF
        lon_seed = int(sender_hash[10:14], 16) / 0xFFFF
        raw.setdefault("sender_location_lat", round(8.0 + lat_seed * (37.0 - 8.0), 6))
        raw.setdefault("sender_location_lon", round(68.0 + lon_seed * (97.0 - 68.0), 6))

    ctx.raw_txn = raw
    ctx.processing_steps.append("validate")
    return ctx


def step_extract_features(ctx: PipelineContext, extract_fn) -> PipelineContext:
    """Step 1: Extract ML features."""
    try:
        ctx.features = extract_fn(ctx.raw_txn)
        missing = validate_feature_dict(ctx.features)
        if missing:
            raise ValueError(f"Feature contract violation: missing {missing}")
        ctx.processing_steps.append("features")
    except Exception as e:
        ctx.errors.append(f"Feature extraction failed: {e}")
    return ctx


def step_rules_engine(ctx: PipelineContext, evaluate_fn, decision_fn) -> PipelineContext:
    """Step 2: Run pre-ML rules engine."""
    try:
        enriched = {
            **ctx.raw_txn,
            "_sender_txn_count": ctx.features.get("sender_txn_count_24h", 0),
            "_sender_txn_count_1h": ctx.features.get("_sender_txn_count_1h", 0),
            "_sender_total_24h": (ctx.features.get("sender_avg_amount", 0) *
                                  ctx.features.get("sender_txn_count_24h", 0)),
            "_is_new_device": ctx.features.get("is_new_device", 0) == 1,
        }
        ctx.rules_triggered = evaluate_fn(enriched)
        ctx.rule_decision = decision_fn(ctx.rules_triggered)
        ctx.processing_steps.append("rules")
    except Exception as e:
        ctx.errors.append(f"Rules engine failed: {e}")
    return ctx


def step_ml_predict(ctx: PipelineContext, predict_fn) -> PipelineContext:
    """Step 3: Ensemble ML prediction."""
    try:
        result = predict_fn(ctx.features)
        ctx.fraud_score = result["ensemble_score"]
        ctx.individual_scores = result["individual_scores"]
        ctx.models_used = result["models_used"]
        ctx.processing_steps.append("ml_predict")
    except Exception as e:
        ctx.errors.append(f"ML prediction failed: {e}")
    return ctx


def step_decide(ctx: PipelineContext) -> PipelineContext:
    """Step 4: Make final decision (rules can override ML; step-up biometric for medium risk)."""
    from .decision_engine import make_decision

    if any(
        m.startswith("Feature extraction failed") or m.startswith("ML prediction failed")
        for m in (ctx.errors or [])
    ):
        ctx.decision = "REQUIRE_BIOMETRIC"
        ctx.risk_level = "MEDIUM"
        ctx.message = "Verification required due to a processing error."
        ctx.decision_reasons = ["System processing issue"]
        ctx.processing_steps.append("decide")
        return ctx

    rules_list = [{"rule_name": r.rule_name, "action": r.action} for r in ctx.rules_triggered]
    ctx.decision, ctx.risk_level, ctx.message, ctx.decision_reasons = make_decision(
        fraud_score=ctx.fraud_score,
        sender_upi=ctx.raw_txn.get("sender_upi"),
        features=ctx.features,
        rules_triggered=rules_list,
        device_anomalies=ctx.device_anomalies,
        graph_info=ctx.graph_info,
    )
    ctx.processing_steps.append("decide")
    return ctx


def step_explain(ctx: PipelineContext, explain_fn, format_fn) -> PipelineContext:
    """Step 5: Generate SHAP explanations."""
    try:
        explanations = explain_fn(ctx.features, get_feature_columns(), top_n=5)
        shap_reasons = format_fn(explanations)
        ctx.reasons = [*ctx.decision_reasons, *shap_reasons]
        ctx.processing_steps.append("explain")
    except Exception as e:
        ctx.reasons = [*ctx.decision_reasons] or [f"Explainability unavailable: {e}"]
        ctx.errors.append(f"SHAP failed: {e}")
    return ctx


def step_device_check(ctx: PipelineContext, check_fn, update_fn, sender_history) -> PipelineContext:
    """Step 6: Device fingerprinting."""
    try:
        # Device history is persisted via history_store; avoid passing empty dicts.
        anomalies = check_fn(ctx.raw_txn, ctx.features)
        ctx.device_anomalies = anomalies
        update_fn(ctx.raw_txn)
        ctx.processing_steps.append("device_check")
    except Exception as e:
        ctx.errors.append(f"Device check failed: {e}")
    return ctx


def step_graph_analysis(ctx: PipelineContext, graph) -> PipelineContext:
    """Step 7: Graph-based network analysis."""
    try:
        sender = (ctx.raw_txn.get("sender_upi") or "").strip()
        receiver = (ctx.raw_txn.get("receiver_upi") or "").strip()
        if not sender or not receiver:
            ctx.processing_steps.append("graph_analysis")
            return ctx
        graph.add_transaction(
            sender, receiver,
            ctx.raw_txn["amount"], ctx.timestamp,
        )
        ctx.graph_info = graph.get_node_features(sender)

        ctx.processing_steps.append("graph_analysis")
    except Exception as e:
        ctx.errors.append(f"Graph analysis failed: {e}")
    return ctx


def run_pipeline(
    txn_dict: dict,
    extract_fn, evaluate_rules_fn, get_rule_decision_fn,
    predict_fn, explain_fn, format_reasons_fn,
    check_device_fn, update_device_fn, sender_history,
    graph,
) -> PipelineContext:
    """
    Run the full prediction pipeline in order:
    validate → features → rules → ML → decide → explain → device → graph

    Each step is isolated. If one step fails, the pipeline continues
    with degraded functionality instead of crashing.
    """
    ctx = PipelineContext()
    ctx = step_validate(ctx, txn_dict)
    ctx = step_extract_features(ctx, extract_fn)
    ctx = step_rules_engine(ctx, evaluate_rules_fn, get_rule_decision_fn)
    ctx = step_ml_predict(ctx, predict_fn)
    ctx = step_device_check(ctx, check_device_fn, update_device_fn, sender_history)
    ctx = step_graph_analysis(ctx, graph)
    ctx = step_decide(ctx)
    ctx = step_explain(ctx, explain_fn, format_reasons_fn)
    return ctx
