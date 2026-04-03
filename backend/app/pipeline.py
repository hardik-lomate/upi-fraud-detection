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

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import FEATURE_COLUMNS, MODEL_VERSION, THRESHOLD_FLAG, THRESHOLD_BLOCK


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
    ctx.timestamp = txn_dict.get("timestamp") or datetime.now().isoformat()
    ctx.raw_txn = {**txn_dict, "timestamp": ctx.timestamp}
    ctx.processing_steps.append("validate")
    return ctx


def step_extract_features(ctx: PipelineContext, extract_fn) -> PipelineContext:
    """Step 1: Extract ML features."""
    try:
        ctx.features = extract_fn(ctx.raw_txn)
        # Verify contract
        missing = set(FEATURE_COLUMNS) - set(ctx.features.keys())
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
    """Step 4: Make final decision (rules override ML)."""
    if ctx.rule_decision == "BLOCK":
        ctx.decision = "BLOCK"
        ctx.risk_level = "HIGH"
        rules_names = [r.rule_name for r in ctx.rules_triggered if r.action == "BLOCK"]
        ctx.message = f"Blocked by rule: {rules_names[0] if rules_names else 'unknown'}"
    elif ctx.rule_decision == "FLAG":
        ctx.decision = "FLAG"
        ctx.risk_level = "MEDIUM"
        rules_names = [r.rule_name for r in ctx.rules_triggered if r.action == "FLAG"]
        ctx.message = f"Flagged by rule: {rules_names[0] if rules_names else 'unknown'}. ML score: {ctx.fraud_score:.1%}"
    else:
        # Pure ML decision
        if ctx.fraud_score >= THRESHOLD_BLOCK:
            ctx.decision, ctx.risk_level = "BLOCK", "HIGH"
            ctx.message = f"High fraud probability ({ctx.fraud_score:.1%}). Transaction blocked."
        elif ctx.fraud_score >= THRESHOLD_FLAG:
            ctx.decision, ctx.risk_level = "FLAG", "MEDIUM"
            ctx.message = f"Moderate fraud risk ({ctx.fraud_score:.1%}). Flagged for review."
        else:
            ctx.decision, ctx.risk_level = "ALLOW", "LOW"
            ctx.message = f"Transaction appears legitimate ({ctx.fraud_score:.1%}). Approved."
    ctx.processing_steps.append("decide")
    return ctx


def step_explain(ctx: PipelineContext, explain_fn, format_fn) -> PipelineContext:
    """Step 5: Generate SHAP explanations."""
    try:
        explanations = explain_fn(ctx.features, FEATURE_COLUMNS, top_n=5)
        ctx.reasons = format_fn(explanations)
        ctx.processing_steps.append("explain")
    except Exception as e:
        ctx.reasons = [f"Explainability unavailable: {e}"]
        ctx.errors.append(f"SHAP failed: {e}")
    return ctx


def step_device_check(ctx: PipelineContext, check_fn, update_fn, sender_history) -> PipelineContext:
    """Step 6: Device fingerprinting."""
    try:
        # sender_history may be None if managed by history_store internally
        history = sender_history or {}
        anomalies = check_fn(ctx.raw_txn, history)
        ctx.device_anomalies = anomalies
        update_fn(ctx.raw_txn, history)

        if any(a["type"] == "IMPOSSIBLE_TRAVEL" for a in anomalies):
            if ctx.decision == "ALLOW":
                ctx.decision, ctx.risk_level = "FLAG", "MEDIUM"
                ctx.message = "Flagged: Impossible travel detected"
        ctx.processing_steps.append("device_check")
    except Exception as e:
        ctx.errors.append(f"Device check failed: {e}")
    return ctx


def step_graph_analysis(ctx: PipelineContext, graph) -> PipelineContext:
    """Step 7: Graph-based network analysis."""
    try:
        graph.add_transaction(
            ctx.raw_txn["sender_upi"], ctx.raw_txn["receiver_upi"],
            ctx.raw_txn["amount"], ctx.timestamp,
        )
        ctx.graph_info = graph.get_node_features(ctx.raw_txn["sender_upi"])

        # Flag mule suspects
        if ctx.graph_info.get("is_mule_suspect") and ctx.decision == "ALLOW":
            ctx.decision, ctx.risk_level = "FLAG", "MEDIUM"
            ctx.message = "Flagged: Mule account pattern detected"
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
    ctx = step_decide(ctx)
    ctx = step_explain(ctx, explain_fn, format_reasons_fn)
    ctx = step_device_check(ctx, check_device_fn, update_device_fn, sender_history)
    ctx = step_graph_analysis(ctx, graph)
    return ctx
