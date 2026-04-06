"""Consumer-safe messaging helpers for the ShieldPay user app.

This module translates internal pipeline signals into plain-English messages
that never expose analyst-only terms.
"""

from __future__ import annotations

from typing import Optional

from .india_fraud_patterns import detect_patterns


consumer_message_map = {
    "velocity_attack": "Multiple payments in quick succession from your account.",
    "impossible_travel": "Your location does not match your last transaction. This could indicate a cloned device.",
    "mule_receiver": "This recipient is linked to reported fraud in our network.",
    "govt_impersonation": "This UPI ID is impersonating a government agency. This is a known scam.",
    "sim_swap": "New device plus new recipient plus high amount is a pattern we see in SIM swap fraud.",
    "overnight_drain": "Large transfers at this hour are unusual for your account.",
    "smurfing": "Repeated payments just below Rs.5,000 match a known evasion pattern.",
    "fake_kyc": "This recipient appears to be running a fake KYC verification scam.",
    "new_device_high_amount": "You have not used this device before, and this is a large payment.",
    "geo_risk_high": "This transaction comes from an area with high reported UPI fraud.",
    "amount_deviation": "This amount is much larger than your usual payments.",
    "default_block": "This payment shows multiple unusual signals that suggest it may not be safe.",
    "default_verify": "This payment is larger or more unusual than your normal activity.",
}


_RECEIVER_ALIASES = {
    "swiggy": "Swiggy",
    "zomato": "Zomato",
    "amazon": "Amazon",
    "msedcl": "Electricity Board",
    "landlord": "Landlord",
    "mom": "Mom",
    "mother": "Mom",
    "npci": "NPCI Helpdesk",
}


def format_inr(amount: float) -> str:
    """Format amounts using Indian digit grouping."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return "Rs.0"

    sign = "-" if value < 0 else ""
    value = abs(value)
    whole_str, frac_str = f"{value:.2f}".split(".")

    if len(whole_str) <= 3:
        grouped = whole_str
    else:
        last_three = whole_str[-3:]
        remaining = whole_str[:-3]
        pairs = []
        while len(remaining) > 2:
            pairs.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            pairs.insert(0, remaining)
        grouped = ",".join([*pairs, last_three])

    if frac_str == "00":
        return f"{sign}₹{grouped}"
    return f"{sign}₹{grouped}.{frac_str}"


def derive_receiver_name(upi_id: str) -> str:
    local = (upi_id or "").split("@")[0].strip().lower()
    if not local:
        return "recipient"
    for key, alias in _RECEIVER_ALIASES.items():
        if key in local:
            return alias
    clean = local.replace(".", " ").replace("_", " ").strip()
    return " ".join(part.capitalize() for part in clean.split()) or "recipient"


def infer_reason_key(raw_reason: str, decision: str, receiver_upi: str = "") -> str:
    reason = (raw_reason or "").lower()
    receiver_local = (receiver_upi or "").split("@")[0].lower()

    if any(k in receiver_local for k in ("npci", "govt", "rbi", "sbi", "tax", "helpdesk")):
        return "govt_impersonation"
    if any(k in receiver_local for k in ("kyc", "verify", "support", "refund")):
        return "fake_kyc"

    if "velocity" in reason or "rapid" in reason or "quick succession" in reason:
        return "velocity_attack"
    if "impossible travel" in reason or "cloned device" in reason:
        return "impossible_travel"
    if "mule" in reason:
        return "mule_receiver"
    if "impersonation" in reason or "government" in reason:
        return "govt_impersonation"
    if "sim swap" in reason:
        return "sim_swap"
    if "overnight" in reason or "unusual transaction time" in reason or "late-night" in reason:
        return "overnight_drain"
    if "smurf" in reason or "below rs.5000" in reason or "below 5000" in reason:
        return "smurfing"
    if "kyc" in reason:
        return "fake_kyc"
    if "new device" in reason and ("high" in reason or "large" in reason or "amount" in reason):
        return "new_device_high_amount"
    if "high fraud area" in reason or "geo" in reason:
        return "geo_risk_high"
    if "high transaction amount" in reason or "amount" in reason or "larger" in reason:
        return "amount_deviation"

    if decision == "BLOCK":
        return "default_block"
    return "default_verify"


def translate_reason(raw_reason: str, decision: str, receiver_upi: str = "") -> str:
    key = infer_reason_key(raw_reason, decision=decision, receiver_upi=receiver_upi)
    return consumer_message_map.get(key, consumer_message_map["default_verify"])


def detect_primary_pattern(raw_txn: dict, features: dict, graph_info: Optional[dict]) -> Optional[dict]:
    """Detect a primary India fraud pattern for user-facing explanations."""
    matches = detect_patterns(
        sender_upi=raw_txn.get("sender_upi", ""),
        receiver_upi=raw_txn.get("receiver_upi", ""),
        amount=float(raw_txn.get("amount") or 0),
        is_new_device=bool(int(features.get("is_new_device", 0) or 0)),
        is_new_receiver=bool(int(features.get("is_new_receiver", 0) or 0)),
        is_night=bool(int(features.get("is_night", 0) or 0)),
        velocity_count=int(features.get("_sender_txn_count_60s", 0) or 0),
        sender_txn_count_24h=int(features.get("sender_txn_count_24h", 0) or 0),
        receiver_txn_count_24h=int((graph_info or {}).get("in_degree", 0) or 0),
        is_self_transfer=raw_txn.get("sender_upi") == raw_txn.get("receiver_upi"),
        graph_info=graph_info or {},
        hour=int(features.get("hour", 12) or 12),
    )

    if not matches:
        return None

    ranked = sorted(
        matches,
        key=lambda m: (float(m.get("risk_boost", 0)), float(m.get("confidence", 0))),
        reverse=True,
    )
    top = ranked[0]
    return {
        "id": top.get("id"),
        "name": top.get("name"),
        "description": top.get("message"),
    }


def build_user_reason(
    decision: str,
    receiver_upi: str,
    reasons: list[str],
    matched_pattern: Optional[dict],
) -> str:
    if decision == "ALLOW":
        first_reason = (reasons[0] if reasons else "").lower()
        if "trusted receiver" in first_reason:
            return "Regular payment to a trusted recipient."
        if "known device" in first_reason:
            return "Payment from your usual device and typical behavior."
        return "Matches your normal spending patterns."

    if matched_pattern and matched_pattern.get("description"):
        return str(matched_pattern["description"])
    first_reason = reasons[0] if reasons else ""
    return translate_reason(first_reason, decision=decision, receiver_upi=receiver_upi)


def build_user_message(decision: str, amount: float, receiver_name: str, user_reason: str) -> str:
    amount_txt = format_inr(amount)
    if decision == "ALLOW":
        return f"Payment successful! {amount_txt} sent to {receiver_name}."
    if decision == "VERIFY":
        return f"Quick security check needed. {amount_txt} to {receiver_name} requires your fingerprint."
    return f"Your money is safe. Payment stopped for your protection. {user_reason}"


def build_security_note(decision: str, user_reason: str) -> str:
    if decision == "ALLOW":
        return f"ShieldPay verified this payment as safe: {user_reason}"
    if decision == "VERIFY":
        return "This one-time verification protects your money."
    return "Your money is safe. If this was not you, change your UPI PIN and call 1930 immediately."
