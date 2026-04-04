"""Decision engine.

Keeps the system stable and predictable for demo usage:
- Uses thresholds for LOW/MEDIUM/HIGH
- Requires biometric verification for MEDIUM
- For HIGH, blocks only when multiple strong signals exist or user has strong fraud history

Outputs a short, readable list of reasons suitable for UI display.
"""

import sys
import os
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import THRESHOLD_FLAG, THRESHOLD_BLOCK

from .database import get_user_fraud_history, increment_fraud_count


def _derive_signals(features: dict, device_anomalies: Optional[list], graph_info: Optional[dict]) -> tuple[list[str], int, bool]:
    reasons: list[str] = []

    amount_dev = float(features.get("amount_deviation", 0) or 0)
    is_new_device = int(features.get("is_new_device", 0) or 0) == 1
    is_new_receiver = int(features.get("is_new_receiver", 0) or 0) == 1
    tx_1h = int(features.get("_sender_txn_count_1h", 0) or 0)
    tx_24h = int(features.get("sender_txn_count_24h", 0) or 0)
    is_night = int(features.get("is_night", 0) or 0) == 1
    cooldown_active = int(features.get("_cooldown_active", 0) or 0) == 1

    trusted_receiver = not is_new_receiver

    strong = 0
    if cooldown_active:
        reasons.append("Recent verification")
    if abs(amount_dev) >= 3.0:
        reasons.append("High amount anomaly")
        strong += 1
    if is_new_device:
        reasons.append("New device")
        strong += 1
    if is_new_receiver:
        reasons.append("New receiver")
        strong += 1
    if tx_1h >= 5:
        reasons.append("High velocity (last 1h)")
        strong += 1
    elif tx_24h >= 20:
        reasons.append("High activity (last 24h)")
        strong += 1
    if is_night:
        reasons.append("Unusual time (night)")

    for a in (device_anomalies or []):
        t = a.get("type")
        if t == "IMPOSSIBLE_TRAVEL":
            reasons.append("Location anomaly")
            strong += 1
        elif t == "IP_SUBNET_CHANGE":
            reasons.append("IP subnet change")
        elif t == "NEW_DEVICE":
            # Avoid duplicate text; still counts as strong.
            if "New device" not in reasons:
                reasons.append("New device")
                strong += 1

    if graph_info and graph_info.get("is_mule_suspect"):
        reasons.append("Mule account pattern")
        strong += 1

    # Keep readable and stable
    deduped: list[str] = []
    seen = set()
    for r in reasons:
        if r not in seen:
            seen.add(r)
            deduped.append(r)

    return deduped[:8], strong, trusted_receiver


def make_decision(
    fraud_score: float,
    sender_upi: str = None,
    features: Optional[dict] = None,
    rules_triggered: list = None,
    device_anomalies: Optional[list] = None,
    graph_info: Optional[dict] = None,
) -> tuple:
    """
    Enhanced 3-level decision with step-up biometric auth.

    Returns: (decision, risk_level, message, reasons)
      decision: ALLOW | REQUIRE_BIOMETRIC | BLOCK
    """
    features = features or {}
    # If rules triggered a hard BLOCK, respect that — no biometric bypass
    if rules_triggered:
        hard_blocks = [r for r in rules_triggered if r.get("action") == "BLOCK"]
        if hard_blocks:
            rule_names = ", ".join(r.get("rule_name", "RULE") for r in hard_blocks)
            # Track fraud count for rule-blocked transactions
            if sender_upi:
                increment_fraud_count(sender_upi, was_blocked=True)
            return (
                "BLOCK", "HIGH",
                f"Transaction blocked by security rules ({rule_names}). Cannot bypass.",
                [f"Rule block: {rule_names}"]
            )

    # Derive human-readable risk signals
    signal_reasons, strong_count, trusted_receiver = _derive_signals(
        features=features,
        device_anomalies=device_anomalies,
        graph_info=graph_info,
    )

    # Fraud history weighting (kept simple + predictable)
    fraud_hist = None
    if sender_upi:
        fraud_hist = get_user_fraud_history(sender_upi)
    fraud_count = int((fraud_hist or {}).get("fraud_count") or 0)
    is_flagged = bool((fraud_hist or {}).get("is_flagged") or False)

    # Fraud history is a signal (not an automatic hard-block) to avoid over-blocking.
    if fraud_count > 0 or is_flagged:
        if "Prior fraud history" not in signal_reasons:
            signal_reasons = ["Prior fraud history", *signal_reasons]
        if fraud_count >= 3 or is_flagged:
            strong_count += 1

    effective_score = float(fraud_score)
    if int(features.get("_cooldown_active", 0) or 0) == 1:
        # Small reduction to avoid immediate re-flagging right after successful verification.
        effective_score = max(0.0, effective_score - 0.10)
    if fraud_count > 0:
        # Small additive bump to reflect prior behavior.
        effective_score = min(1.0, effective_score + 0.03 * min(fraud_count, 5))

    # LOW risk — instant ALLOW
    if effective_score < THRESHOLD_FLAG:
        return (
            "ALLOW", "LOW",
            f"Transaction appears legitimate ({effective_score*100:.1f}%). Approved.",
            signal_reasons[:6]
        )

    # MEDIUM risk — require identity verification
    if effective_score < THRESHOLD_BLOCK:
        msg = "This transaction is unusual. Please verify your identity to prevent fraud."
        # Track the flag
        if sender_upi:
            increment_fraud_count(sender_upi, was_blocked=False)
        return ("REQUIRE_BIOMETRIC", "MEDIUM", msg, signal_reasons[:6])

    # HIGH risk — spec-aligned logic:
    # - Trusted receiver → VERIFY
    # - Block only when multiple strong risk signals
    # - Else → VERIFY
    if trusted_receiver:
        if sender_upi:
            increment_fraud_count(sender_upi, was_blocked=False)
        return (
            "REQUIRE_BIOMETRIC", "HIGH",
            "This transaction is high risk, but the receiver is trusted. Please verify to continue.",
            (signal_reasons + ["Trusted receiver"])[:6],
        )

    if strong_count >= 2:
        if sender_upi:
            increment_fraud_count(sender_upi, was_blocked=True)
        return (
            "BLOCK", "HIGH",
            f"Transaction blocked ({effective_score*100:.1f}%). Multiple strong risk signals detected.",
            signal_reasons[:6],
        )

    if sender_upi:
        increment_fraud_count(sender_upi, was_blocked=False)
    return (
        "REQUIRE_BIOMETRIC", "HIGH",
        "This transaction is high risk. Please verify your identity to prevent fraud.",
        signal_reasons[:6],
    )


# Backward-compatible alias
def make_decision_simple(fraud_score: float) -> tuple:
    """Simple 3-level decision without user history (for batch/live-feed use)."""
    if fraud_score < THRESHOLD_FLAG:
        return ("ALLOW", "LOW", f"Transaction appears legitimate ({fraud_score*100:.1f}%). Approved.")
    elif fraud_score < THRESHOLD_BLOCK:
        return ("REQUIRE_BIOMETRIC", "MEDIUM", f"Suspicious activity detected ({fraud_score*100:.1f}%). Biometric verification required.")
    else:
        return ("REQUIRE_BIOMETRIC", "HIGH", f"High risk detected ({fraud_score*100:.1f}%). Biometric verification required before transaction can proceed.")
