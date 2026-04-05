"""Decision engine.

Deterministic production-style logic:
- Build a weighted signal score from explicit fraud indicators.
- Blend ML score with signal score into a final risk score.
- Apply layered ALLOW/VERIFY/BLOCK policy using trusted receiver and velocity strength.
"""

from typing import Optional


SIGNAL_WEIGHTS = {
    "new_device": 0.2,
    "new_receiver": 0.2,
    "high_amount": 0.2,
    "night_time": 0.1,
    "velocity": 0.3,
}

HIGH_AMOUNT_THRESHOLD = 25000.0


def _to_bool(value) -> bool:
    return int(value or 0) == 1


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _extract_flags(features: dict) -> dict:
    amount = float(features.get("amount", 0) or 0)
    velocity_count = int(features.get("_sender_txn_count_60s", 0) or 0)

    has_device_signal = "is_new_device" in features
    has_receiver_signal = "is_new_receiver" in features

    new_device = _to_bool(features.get("is_new_device", 0)) if has_device_signal else False
    new_receiver = _to_bool(features.get("is_new_receiver", 0)) if has_receiver_signal else False
    night_time = _to_bool(features.get("is_night", 0))
    cooldown_active = _to_bool(features.get("_cooldown_active", 0))
    trusted_receiver = (not new_receiver) if has_receiver_signal else False
    known_device = (not new_device) if has_device_signal else False
    high_amount = amount >= HIGH_AMOUNT_THRESHOLD
    velocity_flag = velocity_count >= 5
    velocity_strong = velocity_count >= 10

    txn_type = str(features.get("_transaction_type", features.get("transaction_type", "")) or "")
    emergency_like = txn_type in {"bill_payment", "recharge"} and amount <= 50000

    sender_txn_count_24h = int(features.get("sender_txn_count_24h", 0) or 0)
    amount_deviation = abs(float(features.get("amount_deviation", 0) or 0))
    repeated_safe_behavior = (
        sender_txn_count_24h >= 3
        and amount_deviation <= 1.25
        and known_device
        and trusted_receiver
        and not velocity_flag
    )

    return {
        "amount": amount,
        "velocity_count": velocity_count,
        "new_device": new_device,
        "new_receiver": new_receiver,
        "night_time": night_time,
        "cooldown_active": cooldown_active,
        "trusted_receiver": trusted_receiver,
        "known_device": known_device,
        "high_amount": high_amount,
        "velocity_flag": velocity_flag,
        "velocity_strong": velocity_strong,
        "emergency_like": emergency_like,
        "repeated_safe_behavior": repeated_safe_behavior,
    }


def compute_signal_score(features: dict) -> tuple[float, dict]:
    """Compute deterministic rule-signal score with fixed weights."""
    flags = _extract_flags(features)
    score = 0.0

    if flags["new_device"]:
        score += SIGNAL_WEIGHTS["new_device"]
    if flags["new_receiver"]:
        score += SIGNAL_WEIGHTS["new_receiver"]
    if flags["high_amount"]:
        score += SIGNAL_WEIGHTS["high_amount"]
    if flags["night_time"]:
        score += SIGNAL_WEIGHTS["night_time"]
    if flags["velocity_flag"]:
        score += SIGNAL_WEIGHTS["velocity"]

    return (_clamp(score), flags)


def compute_risk_score(ml_score: float, features: dict) -> tuple[float, dict]:
    """Blend ML score + signal score with deterministic false-positive controls."""
    signal_score, flags = compute_signal_score(features)
    ml_score = _clamp(float(ml_score))

    # Blend: ML probability remains primary, explicit behavioral signals refine it.
    risk_score = (0.6 * ml_score) + (0.4 * signal_score)

    # False-positive reduction for known-safe patterns.
    if flags["trusted_receiver"] and not flags["high_amount"] and not flags["velocity_flag"]:
        risk_score -= 0.08
    if flags["known_device"] and not flags["high_amount"] and not flags["velocity_flag"] and not flags["night_time"]:
        risk_score -= 0.08
    if flags["cooldown_active"]:
        risk_score -= 0.12
    if flags["repeated_safe_behavior"]:
        risk_score -= 0.1

    # Keep important risk contexts in VERIFY lane even with low ML score.
    if flags["high_amount"]:
        risk_score = max(risk_score, 0.34)
    if flags["high_amount"] and flags["new_device"]:
        risk_score = max(risk_score, 0.46)

    # Very high ML confidence should stay in high-risk lane unless strongly mitigated.
    if ml_score >= 0.8 and not flags["cooldown_active"]:
        risk_score = max(risk_score, 0.72)

    # Velocity attacks are a strong deterministic fraud signal.
    if flags["velocity_strong"] and not flags["trusted_receiver"]:
        risk_score = max(risk_score, 0.82)

    # Emergency-like bill payments should be stepped up, not hard-blocked by default.
    if flags["emergency_like"] and not flags["velocity_strong"]:
        risk_score -= 0.07

    return (_clamp(risk_score), flags)


def build_reasons(features: dict) -> list[str]:
    flags = _extract_flags(features)
    risk_reasons: list[str] = []
    safe_reasons: list[str] = []

    if flags["velocity_strong"]:
        risk_reasons.append("Very high velocity (10+ transactions/min)")
    elif flags["velocity_flag"]:
        risk_reasons.append("Multiple rapid transactions (5+ transactions/min)")

    if flags["new_device"]:
        risk_reasons.append("New device")
    if flags["new_receiver"]:
        risk_reasons.append("New receiver")
    if flags["high_amount"]:
        risk_reasons.append("High transaction amount")
    if flags["night_time"]:
        risk_reasons.append("Unusual transaction time")

    if flags["trusted_receiver"]:
        safe_reasons.append("Trusted receiver history")
    if flags["known_device"]:
        safe_reasons.append("Known device history")
    if flags["cooldown_active"]:
        safe_reasons.append("Recent successful verification cooldown")

    combined = risk_reasons[:4]
    if not combined:
        combined = safe_reasons[:3]
    if not combined:
        combined = ["No strong risk signals detected"]
    return combined


def make_decision(
    fraud_score: float,
    sender_upi: str = None,
    features: Optional[dict] = None,
    rules_triggered: list = None,
    device_anomalies: Optional[list] = None,
    graph_info: Optional[dict] = None,
) -> tuple:
    """Return (decision, risk_level, message, reasons, risk_score)."""
    features = features or {}
    risk_score, flags = compute_risk_score(fraud_score, features)

    strong_signals = sum(
        1
        for s in (
            flags["new_device"],
            flags["new_receiver"],
            flags["high_amount"],
            flags["velocity_strong"],
        )
        if s
    )

    reasons = build_reasons(features)[:4]

    # Exact required flow
    if risk_score < 0.3:
        return ("ALLOW", "LOW", "Approved.", reasons, round(risk_score, 4))

    if risk_score <= 0.7:
        return ("VERIFY", "MEDIUM", "Verification required.", reasons, round(risk_score, 4))

    # risk_score > 0.7
    if flags["trusted_receiver"]:
        return ("VERIFY", "HIGH", "Verification required.", reasons, round(risk_score, 4))

    decision = "VERIFY"
    message = "Verification required."
    if flags["velocity_strong"] or strong_signals >= 2:
        decision = "BLOCK"
        message = "Blocked for safety."

    if decision == "BLOCK" and flags["emergency_like"] and not flags["velocity_strong"]:
        decision = "VERIFY"
        message = "Verification required for safety."

    return (decision, "HIGH", message, reasons, round(risk_score, 4))


# Backward-compatible alias
def make_decision_simple(fraud_score: float) -> tuple:
    """Simple 3-level decision without user history (for batch/live-feed use)."""
    if fraud_score < 0.3:
        return ("ALLOW", "LOW", "Approved.")
    if fraud_score <= 0.7:
        return ("VERIFY", "MEDIUM", "Verification required.")
    return ("VERIFY", "HIGH", "Verification required.")
