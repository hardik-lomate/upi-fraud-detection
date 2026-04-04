"""
Enhanced Decision Engine — Step-up authentication with biometric verification.

Decision logic:
  LOW  (<THRESHOLD_FLAG):  ALLOW immediately
  MEDIUM (FLAG..BLOCK):    REQUIRE_BIOMETRIC (step-up auth)
  HIGH (>=THRESHOLD_BLOCK):
        - If user has any prior fraud history → BLOCK immediately
    - Else → REQUIRE_BIOMETRIC with extra scrutiny
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import THRESHOLD_FLAG, THRESHOLD_BLOCK

from .database import get_user_fraud_history, increment_fraud_count


def make_decision(fraud_score: float, sender_upi: str = None, rules_triggered: list = None) -> tuple:
    """
    Enhanced 3-level decision with step-up biometric auth.

    Returns: (decision, risk_level, message)
      decision: ALLOW | REQUIRE_BIOMETRIC | BLOCK
    """
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
                f"Transaction blocked by security rules ({rule_names}). Cannot bypass."
            )

    # LOW risk — instant ALLOW
    if fraud_score < THRESHOLD_FLAG:
        return (
            "ALLOW", "LOW",
            f"Transaction appears legitimate ({fraud_score*100:.1f}%). Approved."
        )

    # MEDIUM risk — require identity verification
    if fraud_score < THRESHOLD_BLOCK:
        msg = (
            f"Suspicious activity detected ({fraud_score*100:.1f}%). "
            "Biometric verification required to proceed."
        )
        # Track the flag
        if sender_upi:
            increment_fraud_count(sender_upi, was_blocked=False)
        return ("REQUIRE_BIOMETRIC", "MEDIUM", msg)

    # HIGH risk — check fraud history
    if sender_upi:
        fraud_hist = get_user_fraud_history(sender_upi)

        # Any prior fraud history → hard block (repeat offender)
        if fraud_hist["is_flagged"] or (fraud_hist["fraud_count"] or 0) > 0:
            increment_fraud_count(sender_upi, was_blocked=True)
            return (
                "BLOCK", "HIGH",
                f"Transaction blocked ({fraud_score*100:.1f}%). "
                f"Account has {fraud_hist['fraud_count']} prior fraud flags. Cannot proceed."
            )

    # First-time high risk → give them a chance via biometric
    if sender_upi:
        increment_fraud_count(sender_upi, was_blocked=False)
    return (
        "REQUIRE_BIOMETRIC", "HIGH",
        f"High risk detected ({fraud_score*100:.1f}%). "
        "Biometric verification required before transaction can proceed."
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
