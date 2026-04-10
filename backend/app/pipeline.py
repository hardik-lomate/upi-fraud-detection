"""
Pipeline Controller - Central orchestrator for the prediction pipeline.

Execution order:
input_transaction -> feature_extraction -> rules_engine -> ml_model_prediction
-> behavioral_analysis -> graph_analysis -> risk_scoring -> decision_engine
-> explainability -> audit_logging
"""

from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from hashlib import sha1

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import (
    MODEL_VERSION,
    FEATURE_COLUMNS,
    RISK_TIER_MAP,
    get_risk_tier,
    validate_feature_schema,
)

from .feature_columns import get_feature_columns, validate_feature_dict
from .behavior_drift import compute_user_behavior_drift
from .pattern_detector import detect_fraud_patterns
from .history_store import get_sender_history
from .nlg_summary import build_pipeline_reasoning


@dataclass
class PipelineContext:
    # Input
    txn_id: str = ""
    raw_txn: dict = field(default_factory=dict)
    timestamp: str = ""

    # Features
    features: dict = field(default_factory=dict)
    feature_summary: dict = field(default_factory=dict)
    advanced_signals: dict = field(default_factory=dict)

    # Rules
    rules_triggered: list = field(default_factory=list)
    rule_decision: Optional[str] = None
    rules_score: float = 0.0

    # Model / component scores
    fraud_score: float = 0.0
    ml_score: float = 0.0
    anomaly_score: Optional[float] = None
    behavior_score: float = 0.0
    graph_score: float = 0.0
    risk_score: float = 0.0
    bank_risk_score: float = 0.0
    risk_components: dict = field(default_factory=dict)

    # Model metadata
    individual_scores: dict = field(default_factory=dict)
    models_used: list = field(default_factory=list)

    # Decision
    decision: str = "ALLOW"
    bank_decision: str = "ALLOW"
    risk_level: str = "LOW"
    risk_tier: str = "LOW"
    message: str = ""
    personalized_threshold: float = 0.75
    decision_mode: str = "legacy"

    # Explainability
    reasons: list = field(default_factory=list)
    decision_reasons: list = field(default_factory=list)
    behavior_reasons: list = field(default_factory=list)
    graph_reasons: list = field(default_factory=list)

    # User warning payload (legacy UX)
    user_warning: dict = field(default_factory=dict)

    # Device / graph
    device_anomalies: list = field(default_factory=list)
    graph_info: dict = field(default_factory=dict)

    # Metadata
    model_version: str = MODEL_VERSION
    processing_steps: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def step_validate(ctx: PipelineContext, txn_dict: dict) -> PipelineContext:
    provided_txn_id = txn_dict.get("transaction_id")
    if provided_txn_id:
        ctx.txn_id = str(provided_txn_id)
    else:
        sender_part = str(txn_dict.get("sender_upi") or "").strip()
        receiver_part = str(txn_dict.get("receiver_upi") or "").strip()
        amount_part = str(txn_dict.get("amount") or "")
        type_part = str(txn_dict.get("transaction_type") or "purchase")
        seed = f"{sender_part}|{receiver_part}|{amount_part}|{type_part}"
        ctx.txn_id = f"TXN_{sha1(seed.encode('utf-8')).hexdigest()[:16]}"

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
        base = datetime(2026, 1, 5, 10, 0, 0)
        seconds = int(sha1(ctx.txn_id.encode("utf-8")).hexdigest()[:8], 16) % (8 * 3600)
        ctx.timestamp = (base + timedelta(seconds=seconds)).isoformat()

    raw = {**txn_dict, "transaction_id": ctx.txn_id, "timestamp": ctx.timestamp}

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

    sender_hash = sha1(sender.encode("utf-8")).hexdigest() if sender else sha1(b"unknown").hexdigest()

    if not raw.get("sender_device_id"):
        raw["sender_device_id"] = f"DEV_{sender_hash[:10]}"

    if not raw.get("sender_ip"):
        b1 = int(sender_hash[0:2], 16)
        b2 = int(sender_hash[2:4], 16)
        b3 = int(sender_hash[4:6], 16)
        raw["sender_ip"] = f"10.{b1}.{b2}.{b3}"

    if raw.get("sender_location_lat") is None or raw.get("sender_location_lon") is None:
        lat_seed = int(sender_hash[6:10], 16) / 0xFFFF
        lon_seed = int(sender_hash[10:14], 16) / 0xFFFF
        raw.setdefault("sender_location_lat", round(8.0 + lat_seed * (37.0 - 8.0), 6))
        raw.setdefault("sender_location_lon", round(68.0 + lon_seed * (97.0 - 68.0), 6))

    ctx.raw_txn = raw
    ctx.processing_steps.append("validate")
    return ctx


def step_extract_features(ctx: PipelineContext, extract_fn) -> PipelineContext:
    try:
        extracted = dict(extract_fn(ctx.raw_txn) or {})
        strict_contract = validate_feature_schema(extracted, allow_extra=True)
        if not strict_contract.get("is_valid", False):
            missing_contract = list(strict_contract.get("missing", []) or [])
            # Hard-fail when extraction is severely incomplete.
            if len(extracted) <= 1 or (len(extracted) / max(1, len(FEATURE_COLUMNS))) < 0.25:
                raise ValueError(f"Feature contract violation: missing {missing_contract}")
            for col in missing_contract:
                extracted[col] = 0.0

        ctx.features = extracted
        ctx.processing_steps.append("feature_validation")

        missing_model_columns = validate_feature_dict(ctx.features)
        for col in missing_model_columns:
            ctx.features[col] = 0.0

        ctx.processing_steps.append("features")
    except Exception as e:
        ctx.errors.append(f"Feature extraction failed: {e}")
    return ctx


def step_rules_engine(ctx: PipelineContext, evaluate_fn, decision_fn) -> PipelineContext:
    try:
        enriched = {
            **ctx.raw_txn,
            **ctx.features,
            "_sender_txn_count": ctx.features.get("sender_txn_count_24h", 0),
            "_sender_txn_count_1h": ctx.features.get("_sender_txn_count_1h", 0),
            "_sender_total_24h": ctx.features.get(
                "_sender_total_amount_24h",
                (ctx.features.get("sender_avg_amount", 0) * ctx.features.get("sender_txn_count_24h", 0)),
            ),
            "_is_new_device": ctx.features.get("is_new_device", 0) == 1,
        }
        ctx.rules_triggered = evaluate_fn(enriched)
        ctx.rule_decision = decision_fn(ctx.rules_triggered)
        ctx.processing_steps.append("rules")
    except Exception as e:
        ctx.errors.append(f"Rules engine failed: {e}")
    return ctx


def step_ml_predict(ctx: PipelineContext, predict_fn) -> PipelineContext:
    try:
        result = predict_fn(ctx.features)
        ctx.fraud_score = float(result.get("ensemble_score", result.get("ml_score", 0.0)) or 0.0)
        ctx.ml_score = ctx.fraud_score
        ctx.risk_score = ctx.fraud_score
        ctx.individual_scores = dict(result.get("individual_scores", {}) or {})
        ctx.models_used = list(result.get("models_used", []) or [])
        anomaly_raw = result.get("anomaly_score", None)
        if anomaly_raw is None and "isolation_forest" in ctx.individual_scores:
            anomaly_raw = ctx.individual_scores.get("isolation_forest", 0.0)
        if anomaly_raw is None:
            ctx.anomaly_score = None
        else:
            ctx.anomaly_score = max(0.0, min(1.0, float(anomaly_raw or 0.0)))
        ctx.processing_steps.append("ml_predict")
    except Exception as e:
        ctx.errors.append(f"ML prediction failed: {e}")
    return ctx


def step_behavior_analysis(ctx: PipelineContext, behavior_fn) -> PipelineContext:
    if behavior_fn is None:
        ctx.processing_steps.append("behavior_analysis")
        return ctx

    try:
        payload = behavior_fn(
            sender_upi=ctx.raw_txn.get("sender_upi", ""),
            features=ctx.features,
            current_txn=ctx.raw_txn,
        )
        ctx.behavior_score = float(payload.get("behavior_score", 0.0) or 0.0)
        ctx.behavior_reasons = list(payload.get("reasons", []) or [])
        ctx.feature_summary["behavior"] = {
            "drift_score": float(payload.get("drift_score", 0.0) or 0.0),
            "pattern_score": float(payload.get("pattern_score", 0.0) or 0.0),
            "context_score": float(payload.get("context_score", 0.0) or 0.0),
        }
        ctx.processing_steps.append("behavior_analysis")
    except Exception as e:
        ctx.errors.append(f"Behavior analysis failed: {e}")
    return ctx



def _history_rows_for_patterns(sender_upi: str, history: dict, current_txn: dict, fallback_ts: str) -> list[dict]:
    rows: list[dict] = []
    for item in history.get("transactions", []):
        try:
            ts, amt, dev, recv = item
            rows.append(
                {
                    "sender_upi": sender_upi,
                    "receiver_upi": str(recv or "").strip().lower(),
                    "amount": float(amt or 0.0),
                    "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                    "sender_device_id": str(dev or ""),
                }
            )
        except Exception:
            continue

    rows.append(
        {
            "sender_upi": sender_upi,
            "receiver_upi": str(current_txn.get("receiver_upi") or "").strip().lower(),
            "amount": float(current_txn.get("amount") or 0.0),
            "timestamp": str(current_txn.get("timestamp") or fallback_ts or datetime.utcnow().isoformat()),
            "sender_device_id": str(current_txn.get("sender_device_id") or ""),
        }
    )
    return rows[-60:]


def step_advanced_signals(ctx: PipelineContext) -> PipelineContext:
    sender = str(ctx.raw_txn.get("sender_upi") or "").strip().lower()
    if not sender:
        ctx.processing_steps.append("advanced_signals")
        return ctx

    drift_payload = {}
    pattern_hits = []
    history = {}

    try:
        drift_payload = compute_user_behavior_drift(sender) or {}
    except Exception:
        drift_payload = {}

    try:
        history = get_sender_history(sender) or {}
        rows = _history_rows_for_patterns(sender, history, ctx.raw_txn, ctx.timestamp)
        pattern_hits = detect_fraud_patterns(rows) if rows else []
    except Exception:
        history = {}
        pattern_hits = []

    drift_score = float(drift_payload.get("drift_score", 0.0) or 0.0)
    pattern_score = min(1.0, len(pattern_hits) / 3.0)
    current_receiver = str(ctx.raw_txn.get("receiver_upi") or "").strip().lower()
    recent_receivers = []
    for item in (history.get("transactions", []) or [])[-4:]:
        try:
            recent_receivers.append(str(item[3] or "").strip().lower())
        except Exception:
            continue

    consecutive_same_receiver = int(
        bool(current_receiver)
        and len(recent_receivers) >= 3
        and all(r == current_receiver for r in recent_receivers[-3:])
    )

    risky_beneficiary_pattern = int(
        any(
            str(p.get("name", "")).upper() == "SAME_RECEIVER_MULTI_SENDER"
            and bool(p.get("matched"))
            for p in pattern_hits
        )
    )
    transaction_burst = int(
        any(
            str(p.get("name", "")).upper() in {"ROUND_AMOUNT_BURST", "VELOCITY_RAMP"}
            and bool(p.get("matched"))
            for p in pattern_hits
        )
    )

    ctx.advanced_signals = {
        "drift_score": round(drift_score, 4),
        "pattern_score": round(pattern_score, 4),
        "risky_beneficiary_pattern": risky_beneficiary_pattern,
        "transaction_burst": transaction_burst,
        "consecutive_same_receiver": consecutive_same_receiver,
        "matched_patterns": list(pattern_hits),
    }

    ctx.feature_summary["advanced_signals"] = {
        "drift_score": round(drift_score, 4),
        "pattern_score": round(pattern_score, 4),
        "risky_beneficiary_pattern": risky_beneficiary_pattern,
        "transaction_burst": transaction_burst,
        "consecutive_same_receiver": consecutive_same_receiver,
    }

    if drift_score >= 0.6 and "User behavior drift is unusually high" not in ctx.behavior_reasons:
        ctx.behavior_reasons.append("User behavior drift is unusually high")
    if risky_beneficiary_pattern and "Receiver pattern resembles mule aggregation" not in ctx.behavior_reasons:
        ctx.behavior_reasons.append("Receiver pattern resembles mule aggregation")
    if transaction_burst and "Recent transaction burst pattern detected" not in ctx.behavior_reasons:
        ctx.behavior_reasons.append("Recent transaction burst pattern detected")
    if consecutive_same_receiver and "Repeated transfers to same receiver in short window" not in ctx.behavior_reasons:
        ctx.behavior_reasons.append("Repeated transfers to same receiver in short window")


    ctx.processing_steps.append("advanced_signals")
    return ctx

def step_device_check(ctx: PipelineContext, check_fn, update_fn, sender_history) -> PipelineContext:
    try:
        anomalies = check_fn(ctx.raw_txn, ctx.features)
        ctx.device_anomalies = anomalies
        update_fn(ctx.raw_txn)
        ctx.processing_steps.append("device_check")
    except Exception as e:
        ctx.errors.append(f"Device check failed: {e}")
    return ctx


def step_graph_analysis(ctx: PipelineContext, graph, graph_score_fn=None) -> PipelineContext:
    try:
        sender = (ctx.raw_txn.get("sender_upi") or "").strip()
        receiver = (ctx.raw_txn.get("receiver_upi") or "").strip()
        if not sender or not receiver:
            ctx.processing_steps.append("graph_analysis")
            return ctx

        graph.add_transaction(
            sender,
            receiver,
            ctx.raw_txn["amount"],
            ctx.timestamp,
            transaction_id=ctx.txn_id,
        )

        sender_graph = graph.get_node_features(sender)
        receiver_graph = graph.get_node_features(receiver)
        ctx.graph_info = receiver_graph if receiver_graph.get("in_degree", 0) >= sender_graph.get("in_degree", 0) else sender_graph

        if graph_score_fn is not None:
            graph_payload = graph_score_fn(ctx.graph_info)
            ctx.graph_score = float(graph_payload.get("graph_score", 0.0) or 0.0)
            ctx.graph_reasons = list(graph_payload.get("reasons", []) or [])
            ctx.feature_summary["graph"] = {
                "score": ctx.graph_score,
                "components": dict(graph_payload.get("components", {}) or {}),
            }

        ctx.processing_steps.append("graph_analysis")
    except Exception as e:
        ctx.errors.append(f"Graph analysis failed: {e}")
    return ctx


def step_risk_scoring(ctx: PipelineContext, rules_score_fn, combine_risk_fn) -> PipelineContext:
    """Step 7: Unified risk composition from rules, ML, behavior, graph, and anomaly."""
    if rules_score_fn is None or combine_risk_fn is None:
        ctx.processing_steps.append("risk_scoring")
        return ctx

    try:
        ctx.rules_score = float(rules_score_fn(ctx.rule_decision, ctx.rules_triggered) or 0.0)
        risk_payload = combine_risk_fn(
            rules_score=ctx.rules_score,
            ml_score=ctx.ml_score,
            behavior_score=ctx.behavior_score,
            graph_score=ctx.graph_score,
            anomaly_score=ctx.anomaly_score,
        )
        ctx.bank_risk_score = float(risk_payload.get("risk_score", 0.0) or 0.0)
        ctx.risk_components = {
            **dict(risk_payload.get("components", {}) or {}),
            "contributions": dict(risk_payload.get("contributions", {}) or {}),
            "weights": dict(risk_payload.get("weights", {}) or {}),
        }
        ctx.feature_summary["risk_components"] = dict(ctx.risk_components)
        ctx.processing_steps.append("risk_scoring")
    except Exception as e:
        ctx.errors.append(f"Risk scoring failed: {e}")
    return ctx


def step_decide(ctx: PipelineContext) -> PipelineContext:
    from .decision_engine import (
        make_decision,
        make_bank_decision,
        build_reasons,
        compute_personalized_threshold,
    )

    if ctx.decision_mode == "bank":
        has_rule_block = ctx.rule_decision == "BLOCK" or any(
            getattr(r, "action", None) == "BLOCK" for r in (ctx.rules_triggered or [])
        )
        has_rule_flag = ctx.rule_decision == "FLAG" or any(
            getattr(r, "action", None) == "FLAG" for r in (ctx.rules_triggered or [])
        )

        bank_score = float(ctx.bank_risk_score or ctx.fraud_score or 0.0)
        bank_decision, risk_level, message = make_bank_decision(bank_score)

        # Rule layer must remain authoritative in bank mode too.
        if has_rule_block:
            bank_decision = "BLOCK"
            risk_level = "HIGH"
            message = "Blocked for safety."
            bank_score = max(bank_score, 0.9)
        elif has_rule_flag and bank_decision == "ALLOW":
            bank_decision = "STEP-UP"
            risk_level = "MEDIUM" if bank_score < 0.75 else "HIGH"
            message = "Verification required."

        ctx.bank_decision = bank_decision
        ctx.risk_level = risk_level
        ctx.message = message
        ctx.decision = bank_decision
        ctx.risk_score = bank_score
        ctx.risk_tier = get_risk_tier(ctx.risk_score)

        reasons = []
        reasons.extend(list(ctx.behavior_reasons or []))
        reasons.extend(list(ctx.graph_reasons or []))
        reasons.extend([
            getattr(r, "reason", "")
            for r in (ctx.rules_triggered or [])
            if getattr(r, "reason", "")
        ])
        reasons.extend(build_reasons(ctx.features))

        merged = []
        for reason in reasons:
            if reason and reason not in merged:
                merged.append(reason)
        ctx.decision_reasons = merged[:5] if merged else ["No strong risk signals detected"]

        ctx.processing_steps.append("decide")
        return ctx

    # Legacy compatibility mode
    if ctx.rule_decision == "BLOCK" or any(getattr(r, "action", None) == "BLOCK" for r in (ctx.rules_triggered or [])):
        ctx.decision = "BLOCK"
        ctx.bank_decision = "BLOCK"
        ctx.risk_level = "HIGH"
        ctx.message = "Blocked for safety."
        ctx.risk_score = max(ctx.fraud_score, 0.9)
        ctx.risk_tier = "HIGH"
        ctx.personalized_threshold = compute_personalized_threshold(ctx.raw_txn.get("sender_upi"), ctx.features)

        rule_reasons = [getattr(r, "reason", "") for r in (ctx.rules_triggered or []) if getattr(r, "reason", "")]
        signal_reasons = [
            r
            for r in build_reasons(ctx.features)
            if r
            not in {
                "Trusted receiver history",
                "Known device history",
                "Recent successful verification cooldown",
                "No strong risk signals detected",
            }
        ]
        merged = []
        for reason in [*rule_reasons, *signal_reasons]:
            if reason and reason not in merged:
                merged.append(reason)
        ctx.decision_reasons = merged[:4] if merged else ["Rule-based block"]
        ctx.processing_steps.append("decide")
        return ctx

    if any(
        m.startswith("Feature extraction failed") or m.startswith("ML prediction failed")
        for m in (ctx.errors or [])
    ):
        ctx.decision = "VERIFY"
        ctx.bank_decision = "STEP-UP"
        ctx.risk_level = "MEDIUM"
        ctx.message = "Verification required due to a processing error."
        ctx.risk_score = max(ctx.fraud_score, 0.5)
        ctx.risk_tier = get_risk_tier(ctx.risk_score)
        ctx.personalized_threshold = compute_personalized_threshold(ctx.raw_txn.get("sender_upi"), ctx.features)
        ctx.decision_reasons = build_reasons(ctx.features) or ["System processing issue"]
        ctx.processing_steps.append("decide")
        return ctx

    rules_list = [{"rule_name": r.rule_name, "action": r.action} for r in (ctx.rules_triggered or [])]
    ctx.personalized_threshold = compute_personalized_threshold(ctx.raw_txn.get("sender_upi"), ctx.features)
    ctx.decision, ctx.risk_level, ctx.message, ctx.decision_reasons, ctx.risk_score = make_decision(
        fraud_score=ctx.fraud_score,
        sender_upi=ctx.raw_txn.get("sender_upi"),
        features=ctx.features,
        rules_triggered=rules_list,
        device_anomalies=ctx.device_anomalies,
        graph_info=ctx.graph_info,
        personalized_threshold=ctx.personalized_threshold,
    )
    ctx.risk_tier = get_risk_tier(ctx.risk_score)

    bank_score = float(ctx.bank_risk_score or ctx.risk_score or 0.0)
    ctx.bank_decision, _, _ = make_bank_decision(bank_score)

    ctx.processing_steps.append("decide")
    return ctx


def step_explain(ctx: PipelineContext, explain_fn, format_fn) -> PipelineContext:
    """Step 5: Generate SHAP explanations."""
    rule_reasons = [
        str(getattr(r, "reason", "") or "").strip()
        for r in (ctx.rules_triggered or [])
        if str(getattr(r, "reason", "") or "").strip()
    ]

    try:
        feature_columns = get_feature_columns()
        explanations = explain_fn(ctx.features, feature_columns, top_n=8)
        shap_reasons = format_fn(explanations)

        merged = []
        for reason in [*(shap_reasons or []), *(ctx.decision_reasons or [])]:
            if reason and reason not in merged:
                merged.append(reason)

        reasoning = build_pipeline_reasoning(
            decision=ctx.decision,
            risk_score=float(ctx.bank_risk_score or ctx.risk_score or ctx.fraud_score or 0.0),
            shap_reasons=list(shap_reasons or []),
            behavior_reasons=list(ctx.behavior_reasons or []),
            graph_reasons=list(ctx.graph_reasons or []),
            rule_reasons=rule_reasons,
        )

        if reasoning:
            ctx.reasons = reasoning[:3]
            ctx.feature_summary["reasoning_summary"] = " ".join(reasoning[:3])
        else:
            ctx.reasons = merged[:5] if merged else list(ctx.decision_reasons or [])

        ctx.processing_steps.append("shap_explain")
    except Exception as e:
        fallback = build_pipeline_reasoning(
            decision=ctx.decision,
            risk_score=float(ctx.bank_risk_score or ctx.risk_score or ctx.fraud_score or 0.0),
            shap_reasons=list(ctx.decision_reasons or []),
            behavior_reasons=list(ctx.behavior_reasons or []),
            graph_reasons=list(ctx.graph_reasons or []),
            rule_reasons=rule_reasons,
        )
        if fallback:
            ctx.reasons = fallback[:3]
            ctx.feature_summary["reasoning_summary"] = " ".join(fallback[:3])
        else:
            ctx.reasons = [*ctx.decision_reasons] or [f"Explainability unavailable: {e}"]
        ctx.errors.append(f"SHAP failed: {e}")
    return ctx


def step_user_warning_payload(ctx: PipelineContext) -> PipelineContext:
    tier = get_risk_tier(float(ctx.risk_score or 0.0))
    tier_cfg = RISK_TIER_MAP.get(tier, RISK_TIER_MAP["LOW"])

    receiver = str(ctx.raw_txn.get("receiver_upi") or "receiver")
    amount = float(ctx.raw_txn.get("amount") or 0.0)
    amount_str = f"Rs.{amount:,.0f}"

    if tier == "HIGH":
        title = "High Risk - Payment Blocked"
        body = "This payment was blocked to protect your account."
    elif tier == "MEDIUM":
        title = "Suspicious Transaction Detected"
        body = f"This payment to {receiver} for {amount_str} looks risky."
    else:
        title = "Transaction Looks Safe"
        body = tier_cfg.get("user_message", "Transaction looks safe. Proceed!")

    show_warning = tier in {"MEDIUM", "HIGH"}
    risk_pct = int(round(float(ctx.risk_score or 0.0) * 100))

    ctx.user_warning = {
        "show_warning": show_warning,
        "warning_title": title,
        "warning_body": body,
        "risk_score_display": round(float(ctx.risk_score or 0.0), 4),
        "risk_percentage": risk_pct,
        "risk_tier": tier,
        "reasons_display": list(ctx.reasons[:3]),
        "action_buttons": {
            "proceed": {"label": "Proceed Anyway", "action": "USER_OVERRIDE", "color": "warning"},
            "cancel": {"label": "Cancel Payment", "action": "CANCEL", "color": "safe"},
        },
        "block_screen": {
            "show": tier == "HIGH",
            "title": "Payment Blocked",
            "body": "This payment was blocked to protect your account.",
            "cta": "Contact support if this was genuine",
        },
    }
    ctx.processing_steps.append("user_warning")
    return ctx


def step_audit_logging(ctx: PipelineContext, audit_fn) -> PipelineContext:
    if audit_fn is None:
        return ctx
    try:
        audit_fn(ctx)
        ctx.processing_steps.append("audit_logging")
    except Exception as e:
        ctx.errors.append(f"Audit logging failed: {e}")
    return ctx


def run_pipeline(
    txn_dict: dict,
    extract_fn,
    evaluate_rules_fn,
    get_rule_decision_fn,
    predict_fn,
    explain_fn,
    format_reasons_fn,
    check_device_fn,
    update_device_fn,
    sender_history,
    graph,
    behavior_fn=None,
    graph_score_fn=None,
    rules_score_fn=None,
    combine_risk_fn=None,
    audit_fn=None,
    decision_mode: str = "legacy",
) -> PipelineContext:
    ctx = PipelineContext()
    ctx.decision_mode = str(decision_mode or "legacy").strip().lower()

    ctx = step_validate(ctx, txn_dict)
    ctx = step_extract_features(ctx, extract_fn)
    ctx = step_rules_engine(ctx, evaluate_rules_fn, get_rule_decision_fn)
    ctx = step_ml_predict(ctx, predict_fn)
    ctx = step_device_check(ctx, check_device_fn, update_device_fn, sender_history)
    ctx = step_behavior_analysis(ctx, behavior_fn)
    ctx = step_advanced_signals(ctx)
    ctx = step_graph_analysis(ctx, graph, graph_score_fn=graph_score_fn)
    ctx = step_risk_scoring(ctx, rules_score_fn, combine_risk_fn)
    ctx = step_decide(ctx)
    ctx = step_explain(ctx, explain_fn, format_reasons_fn)
    ctx = step_user_warning_payload(ctx)
    ctx = step_audit_logging(ctx, audit_fn)
    return ctx

