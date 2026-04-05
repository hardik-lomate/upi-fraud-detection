"""Decision engine v3.0 — Production-grade UPI fraud decisioning.

Calibrated for real Indian UPI fraud patterns:
  - ALLOW threshold: 0.18 (any moderate signal → VERIFY)
  - BLOCK threshold: 0.60 (catches real fraud)
  - Compound signal detection (new_device + high_amount = +0.35)
  - Geo risk, VPA risk, impossible travel integration
  - Rich contextual messages explaining every decision
"""

from datetime import datetime
from typing import Optional


# ─── Signal weights (recalibrated for real UPI fraud rates) ──────────

SIGNAL_WEIGHTS = {
    "new_device": 0.25,
    "new_receiver": 0.15,
    "high_amount": 0.25,
    "medium_amount": 0.10,
    "night_time": 0.15,
    "velocity": 0.35,
    # Compound signals (much stronger than individual)
    "new_device_AND_high_amount": 0.35,
    "new_device_AND_night": 0.28,
    "new_receiver_AND_high_amount": 0.22,
    "transfer_to_unknown_at_night": 0.12,
    # External risk signals
    "geo_risk_high": 0.20,
    "vpa_suspicious": 0.15,
    "mule_suspect_receiver": 0.30,
    "impossible_travel": 0.40,
    "amount_deviation_extreme": 0.20,
}

HIGH_AMOUNT_THRESHOLD = 15000.0
MEDIUM_AMOUNT_THRESHOLD = 5000.0

# Decision boundaries (recalibrated)
THRESHOLD_ALLOW = 0.18
THRESHOLD_BLOCK = 0.60


def _to_bool(value) -> bool:
    return int(value or 0) == 1


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def format_inr(amount: float) -> str:
    """Format amount in Indian number system."""
    n = abs(amount)
    if n >= 10000000:
        return f"Rs.{n / 10000000:.1f}Cr"
    if n >= 100000:
        return f"Rs.{n / 100000:.1f}L"
    if n >= 1000:
        return f"Rs.{n:,.0f}"
    return f"Rs.{n:,.0f}"


def _time_context(hour: int) -> str:
    if 0 <= hour < 5:
        return "late night"
    if 5 <= hour < 8:
        return "early morning"
    if 8 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "late evening"


def _extract_flags(features: dict, geo_risk: dict = None, vpa_risk: dict = None) -> dict:
    """Extract all risk flags from features + external risk signals."""
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
    medium_amount = MEDIUM_AMOUNT_THRESHOLD <= amount < HIGH_AMOUNT_THRESHOLD
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

    # Geo risk integration
    geo_risk = geo_risk or {}
    geo_risk_high = geo_risk.get("risk_level") in ("HIGH", "CRITICAL")
    geo_region = geo_risk.get("city") or geo_risk.get("region") or ""
    geo_multiplier = float(geo_risk.get("risk_multiplier", 1.0) or 1.0)
    impossible_travel = geo_risk.get("impossible_travel", False)

    # VPA risk integration
    vpa_risk = vpa_risk or {}
    receiver_vpa = vpa_risk.get("receiver", {})
    vpa_suspicious = receiver_vpa.get("risk_level") in ("HIGH", "CRITICAL")
    vpa_pattern = receiver_vpa.get("pattern_type", "")

    # Amount deviation extreme
    amount_deviation_extreme = amount_deviation > 3.0

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
        "medium_amount": medium_amount,
        "velocity_flag": velocity_flag,
        "velocity_strong": velocity_strong,
        "emergency_like": emergency_like,
        "repeated_safe_behavior": repeated_safe_behavior,
        "txn_type": txn_type,
        # Geo
        "geo_risk_high": geo_risk_high,
        "geo_region": geo_region,
        "geo_multiplier": geo_multiplier,
        "impossible_travel": impossible_travel,
        # VPA
        "vpa_suspicious": vpa_suspicious,
        "vpa_pattern": vpa_pattern,
        # Amount deviation
        "amount_deviation": amount_deviation,
        "amount_deviation_extreme": amount_deviation_extreme,
    }


def compute_signal_score(features: dict, geo_risk: dict = None, vpa_risk: dict = None) -> tuple[float, dict]:
    """Compute deterministic rule-signal score with compound signals."""
    flags = _extract_flags(features, geo_risk, vpa_risk)
    score = 0.0

    # Individual signals
    if flags["new_device"]:
        score += SIGNAL_WEIGHTS["new_device"]
    if flags["new_receiver"]:
        score += SIGNAL_WEIGHTS["new_receiver"]
    if flags["high_amount"]:
        score += SIGNAL_WEIGHTS["high_amount"]
    elif flags["medium_amount"]:
        score += SIGNAL_WEIGHTS["medium_amount"]
    if flags["night_time"]:
        score += SIGNAL_WEIGHTS["night_time"]
    if flags["velocity_flag"]:
        score += SIGNAL_WEIGHTS["velocity"]

    # Compound signals (much more dangerous together)
    if flags["new_device"] and flags["high_amount"]:
        score += SIGNAL_WEIGHTS["new_device_AND_high_amount"]
    if flags["new_device"] and flags["night_time"]:
        score += SIGNAL_WEIGHTS["new_device_AND_night"]
    if flags["new_receiver"] and flags["high_amount"]:
        score += SIGNAL_WEIGHTS["new_receiver_AND_high_amount"]
    if flags["txn_type"] == "transfer" and flags["new_receiver"] and flags["night_time"]:
        score += SIGNAL_WEIGHTS["transfer_to_unknown_at_night"]

    # External risk signals
    if flags["geo_risk_high"]:
        score += SIGNAL_WEIGHTS["geo_risk_high"]
    if flags["vpa_suspicious"]:
        score += SIGNAL_WEIGHTS["vpa_suspicious"]
    if flags["impossible_travel"]:
        score += SIGNAL_WEIGHTS["impossible_travel"]
    if flags["amount_deviation_extreme"]:
        score += SIGNAL_WEIGHTS["amount_deviation_extreme"]

    return (_clamp(score), flags)


def compute_risk_score(ml_score: float, features: dict,
                       geo_risk: dict = None, vpa_risk: dict = None) -> tuple[float, dict]:
    """Blend ML score + signal score with recalibrated weights."""
    signal_score, flags = compute_signal_score(features, geo_risk, vpa_risk)
    ml_score = _clamp(float(ml_score))

    # Blend: ML probability + explicit behavioral signals.
    risk_score = (0.55 * ml_score) + (0.45 * signal_score)

    # False-positive reduction for known-safe patterns — smaller now.
    if flags["trusted_receiver"] and not flags["high_amount"] and not flags["velocity_flag"]:
        risk_score -= 0.05
    if flags["known_device"] and not flags["high_amount"] and not flags["velocity_flag"] and not flags["night_time"]:
        risk_score -= 0.05
    if flags["cooldown_active"]:
        risk_score -= 0.10
    if flags["repeated_safe_behavior"]:
        risk_score -= 0.08

    # Floor: important risk contexts must stay in VERIFY or above.
    if flags["high_amount"]:
        risk_score = max(risk_score, 0.28)
    if flags["medium_amount"] and flags["new_device"]:
        risk_score = max(risk_score, 0.22)
    if flags["high_amount"] and flags["new_device"]:
        risk_score = max(risk_score, 0.52)
    if flags["high_amount"] and flags["new_receiver"]:
        risk_score = max(risk_score, 0.42)

    # Very high ML confidence should stay in high-risk lane.
    if ml_score >= 0.75 and not flags["cooldown_active"]:
        risk_score = max(risk_score, 0.65)

    # Velocity attacks are deterministic fraud.
    if flags["velocity_strong"] and not flags["trusted_receiver"]:
        risk_score = max(risk_score, 0.82)
    if flags["velocity_flag"] and not flags["trusted_receiver"]:
        risk_score = max(risk_score, 0.45)

    # Impossible travel is near-certain fraud.
    if flags["impossible_travel"]:
        risk_score = max(risk_score, 0.78)

    # Geo risk + high amount = elevated risk.
    if flags["geo_risk_high"] and flags["high_amount"]:
        risk_score = max(risk_score, 0.55)

    # VPA suspicious receiver = elevated risk.
    if flags["vpa_suspicious"] and flags["new_receiver"]:
        risk_score = max(risk_score, 0.50)

    # Emergency-like bill payments should be stepped up, not hard-blocked.
    if flags["emergency_like"] and not flags["velocity_strong"]:
        risk_score -= 0.05

    return (_clamp(risk_score), flags)


def build_reasons(features: dict, geo_risk: dict = None, vpa_risk: dict = None) -> list[str]:
    """Build human-readable risk/safe reason list."""
    flags = _extract_flags(features, geo_risk, vpa_risk)
    risk_reasons: list[str] = []
    safe_reasons: list[str] = []

    if flags["impossible_travel"]:
        risk_reasons.append("Impossible travel detected — location change too fast")
    if flags["velocity_strong"]:
        risk_reasons.append(f"Very high velocity ({flags['velocity_count']}+ transactions/min)")
    elif flags["velocity_flag"]:
        risk_reasons.append(f"Rapid transactions ({flags['velocity_count']} in last minute)")
    if flags["new_device"] and flags["high_amount"]:
        risk_reasons.append(f"Unrecognized device with high-value transfer ({format_inr(flags['amount'])})")
    elif flags["new_device"]:
        risk_reasons.append("Transaction from unrecognized device")
    if flags["new_receiver"] and flags["high_amount"]:
        risk_reasons.append(f"First-time receiver with large amount ({format_inr(flags['amount'])})")
    elif flags["new_receiver"]:
        risk_reasons.append("First-time payment to this receiver")
    if flags["high_amount"] and not flags["new_device"]:
        risk_reasons.append(f"High-value transaction: {format_inr(flags['amount'])}")
    elif flags["medium_amount"] and flags["night_time"]:
        risk_reasons.append(f"Medium amount ({format_inr(flags['amount'])}) during unusual hours")
    if flags["night_time"] and "Unusual" not in " ".join(risk_reasons):
        risk_reasons.append("Unusual transaction time (late night)")
    if flags["geo_risk_high"]:
        region = flags.get("geo_region", "high-fraud region")
        risk_reasons.append(f"High-fraud zone: {region} ({flags['geo_multiplier']:.1f}x risk)")
    if flags["vpa_suspicious"]:
        pattern = flags.get("vpa_pattern", "suspicious pattern")
        risk_reasons.append(f"Suspicious receiver UPI: {pattern}")
    if flags["amount_deviation_extreme"]:
        risk_reasons.append(f"Amount {flags['amount_deviation']:.1f}x above your average")

    if flags["trusted_receiver"]:
        safe_reasons.append("Trusted receiver — previous history")
    if flags["known_device"]:
        safe_reasons.append("Known device")
    if flags["cooldown_active"]:
        safe_reasons.append("Recent verification cooldown active")

    combined = risk_reasons[:5]
    if not combined:
        combined = safe_reasons[:3] or ["No strong risk signals detected"]
    return combined


def build_decision_message(
    decision: str,
    risk_score: float,
    flags: dict,
    amount: float,
    sender: str = "",
    receiver: str = "",
    timestamp: str = "",
    geo_risk: dict = None,
    vpa_risk: dict = None,
    rules_triggered: list = None,
) -> str:
    """Generate rich, contextual decision messages like a real banking platform."""
    amount_str = format_inr(amount)
    receiver_short = receiver.split("@")[0] if receiver else "recipient"

    # Parse hour for time context
    hour = 12
    try:
        if timestamp:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            hour = dt.hour
    except Exception:
        pass
    time_str = _time_context(hour)

    # Check for rule reasons
    rule_reason = ""
    if rules_triggered:
        for r in rules_triggered:
            reason = r.get("reason", "") if isinstance(r, dict) else getattr(r, "reason", "")
            if reason:
                rule_reason = reason
                break

    geo_risk = geo_risk or {}
    vpa_risk = vpa_risk or {}

    if decision == "ALLOW":
        if flags.get("trusted_receiver") and flags.get("known_device"):
            return f"Transaction of {amount_str} to {receiver_short} approved. Known device, trusted receiver."
        if flags.get("known_device"):
            return f"{amount_str} transaction approved. Normal spending pattern from your device."
        return f"{amount_str} transaction approved. Low risk score ({risk_score:.2f})."

    if decision == "VERIFY":
        parts = []

        if flags.get("impossible_travel"):
            region = geo_risk.get("city", "another location")
            parts.append(f"Verification required: transaction originates from {region} — impossible travel detected.")
        elif flags.get("new_device") and flags.get("high_amount"):
            avg_str = f"{flags.get('amount_deviation', 0):.1f}x" if flags.get("amount_deviation", 0) > 1.5 else "elevated"
            parts.append(f"Verification required: {amount_str} transfer from an unrecognized device. Amount is {avg_str} your average.")
        elif flags.get("night_time") and flags.get("high_amount"):
            parts.append(f"Verification required: {amount_str} transaction at {time_str} is unusual. High-value transfers after midnight require identity confirmation.")
        elif flags.get("geo_risk_high"):
            region = geo_risk.get("city") or geo_risk.get("region") or "high-fraud zone"
            mult = geo_risk.get("risk_multiplier", 1.0)
            parts.append(f"Verification required: transaction originates from {region} (risk multiplier {mult:.1f}x). Please confirm.")
        elif flags.get("new_receiver") and flags.get("high_amount"):
            parts.append(f"Verification required: first-time payment of {amount_str} to {receiver_short}. Confirm to proceed.")
        elif flags.get("vpa_suspicious"):
            pattern = vpa_risk.get("receiver", {}).get("pattern_type", "suspicious pattern")
            parts.append(f"Verification required: receiver UPI ID shows {pattern}. Confirm this is intentional.")
        elif flags.get("new_device"):
            parts.append(f"Verification required: {amount_str} from an unrecognized device. Tap to verify with fingerprint or face ID.")
        elif flags.get("new_receiver"):
            parts.append(f"Verification required: first-time payment to {receiver_short}. Confirm to proceed.")
        elif flags.get("velocity_flag"):
            parts.append(f"Verification required: {flags.get('velocity_count', 5)} transactions in rapid succession. Confirm this activity is you.")
        else:
            parts.append(f"Verification required: {amount_str} transaction has elevated risk ({risk_score:.0%}). Confirm your identity.")

        if rule_reason and len(parts[0]) < 180:
            parts.append(f"Policy: {rule_reason}")

        return " ".join(parts[:2])

    # BLOCK
    parts = []

    if flags.get("impossible_travel"):
        region = geo_risk.get("city", "another city")
        parts.append(f"Transaction blocked: impossible travel detected. Previous activity was in a different location — {region} is physically unreachable in the elapsed time.")
    elif flags.get("velocity_strong"):
        count = flags.get("velocity_count", 10)
        parts.append(f"Transaction blocked: {count} transfers in the last minute totaling {amount_str}. This velocity pattern matches account takeover attacks.")
    elif flags.get("vpa_suspicious") and flags.get("new_receiver"):
        parts.append(f"Transaction blocked: recipient {receiver_short} has high-entropy patterns matching auto-generated mule account signatures.")
    elif flags.get("new_device") and flags.get("high_amount") and flags.get("night_time"):
        parts.append(f"Transaction blocked: {amount_str} from new device at {time_str}. This combination is a strong SIM swap indicator.")
    elif flags.get("geo_risk_high") and flags.get("high_amount"):
        region = geo_risk.get("city") or geo_risk.get("region") or "high-fraud zone"
        parts.append(f"Transaction blocked: {amount_str} from {region} (high-fraud zone). Contact your bank if legitimate.")
    elif rule_reason:
        parts.append(f"Transaction blocked: {rule_reason}")
    elif flags.get("new_device") and flags.get("high_amount"):
        parts.append(f"Transaction blocked: {amount_str} transfer from unrecognized device. Multiple risk signals detected.")
    else:
        parts.append(f"Transaction blocked: risk score {risk_score:.0%} exceeds safety threshold. Multiple anomalies detected.")

    parts.append("Contact 1800-XXX-XXXX if you initiated this transaction.")
    return " ".join(parts[:2])


def make_decision(
    fraud_score: float,
    sender_upi: str = None,
    features: Optional[dict] = None,
    rules_triggered: list = None,
    device_anomalies: Optional[list] = None,
    graph_info: Optional[dict] = None,
    geo_risk: Optional[dict] = None,
    vpa_risk: Optional[dict] = None,
    timestamp: str = "",
    receiver_upi: str = "",
) -> tuple:
    """Return (decision, risk_level, message, reasons, risk_score)."""
    features = features or {}
    risk_score, flags = compute_risk_score(fraud_score, features, geo_risk, vpa_risk)

    strong_signals = sum(
        1
        for s in (
            flags["new_device"],
            flags["new_receiver"],
            flags["high_amount"],
            flags["velocity_strong"],
            flags["geo_risk_high"],
            flags["vpa_suspicious"],
            flags["impossible_travel"],
        )
        if s
    )

    reasons = build_reasons(features, geo_risk, vpa_risk)[:5]
    amount = float(features.get("amount", 0) or 0)

    # ─── Decision logic (recalibrated) ───

    if risk_score < THRESHOLD_ALLOW:
        decision = "ALLOW"
        risk_level = "LOW"
    elif risk_score < THRESHOLD_BLOCK:
        decision = "VERIFY"
        risk_level = "MEDIUM" if risk_score < 0.40 else "HIGH"
    else:
        # risk_score >= 0.60
        if flags["trusted_receiver"] and not flags["velocity_strong"] and not flags["impossible_travel"]:
            # Trusted receiver gets a chance to verify even at high risk
            decision = "VERIFY"
            risk_level = "HIGH"
        elif flags["velocity_strong"] or strong_signals >= 2 or flags["impossible_travel"]:
            decision = "BLOCK"
            risk_level = "HIGH"
        else:
            decision = "VERIFY"
            risk_level = "HIGH"

    # Emergency overrides
    if decision == "BLOCK" and flags["emergency_like"] and not flags["velocity_strong"] and not flags["impossible_travel"]:
        decision = "VERIFY"

    # Build rich message
    message = build_decision_message(
        decision=decision,
        risk_score=risk_score,
        flags=flags,
        amount=amount,
        sender=sender_upi or "",
        receiver=receiver_upi,
        timestamp=timestamp,
        geo_risk=geo_risk,
        vpa_risk=vpa_risk,
        rules_triggered=rules_triggered,
    )

    return (decision, risk_level, message, reasons, round(risk_score, 4))


# Backward-compatible alias
def make_decision_simple(fraud_score: float) -> tuple:
    """Simple 3-level decision without user history."""
    if fraud_score < THRESHOLD_ALLOW:
        return ("ALLOW", "LOW", "Approved.")
    if fraud_score < THRESHOLD_BLOCK:
        return ("VERIFY", "MEDIUM", "Verification required.")
    return ("BLOCK", "HIGH", "Blocked — multiple risk signals detected.")
