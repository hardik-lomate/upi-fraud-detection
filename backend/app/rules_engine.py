"""
Rules Engine — Pre-ML hard-coded fraud rules.
These fire BEFORE the ML model and can instantly block obvious fraud.
Industry systems always have a rules layer as the first line of defense.
"""

from datetime import datetime
from typing import Optional


class RuleResult:
    def __init__(self, triggered: bool, rule_name: str = "", reason: str = "", action: str = "ALLOW"):
        self.triggered = triggered
        self.rule_name = rule_name
        self.reason = reason
        self.action = action  # "BLOCK", "FLAG", or "ALLOW"


# --- Rule Definitions ---

def rule_burst_1min(txn: dict) -> RuleResult:
    """Block bursty payment behavior that resembles scripted bot execution."""
    count = max(
        int(txn.get("sender_txn_count_1min", 0) or 0),
        int(txn.get("_sender_txn_count_1min", 0) or 0),
        int(txn.get("_sender_txn_count_60s", 0) or 0),
    )
    if count >= 5:
        return RuleResult(
            True,
            "BURST_1MIN",
            f"{count} payments in the last 60 seconds — possible automated fraud",
            "BLOCK",
        )
    return RuleResult(False)


def rule_unknown_receiver_high_amount(txn: dict) -> RuleResult:
    """Flag high-value transfer to a first-time receiver."""
    amount = float(txn.get("amount", 0) or 0)
    is_new_receiver = int(txn.get("is_new_receiver", 0) or 0) == 1
    if is_new_receiver and amount > 10000:
        return RuleResult(
            True,
            "UNKNOWN_RECEIVER_HIGH_AMOUNT",
            f"First-ever payment of Rs.{amount:,.0f} to unknown UPI ID",
            "FLAG",
        )
    return RuleResult(False)


def rule_impossible_travel(txn: dict) -> RuleResult:
    """Block when current location is impossible relative to last known transaction."""
    distance = float(txn.get("geo_distance_km", 0.0) or 0.0)
    minutes = float(txn.get("_time_since_last_txn_minutes", -1.0) or -1.0)
    impossible = int(txn.get("is_impossible_travel", 0) or 0) == 1
    if impossible or (distance > 500 and 0 <= minutes < 30):
        return RuleResult(
            True,
            "IMPOSSIBLE_TRAVEL",
            f"Location jump of {distance:.1f}km in {max(minutes, 0):.1f} minutes is physically impossible",
            "BLOCK",
        )
    return RuleResult(False)


def rule_suspicious_vpa(txn: dict) -> RuleResult:
    """Flag receiver UPI IDs that look suspicious or unverified."""
    score = float(txn.get("vpa_suffix_risk_score", 0.0) or 0.0)
    if score >= 0.8:
        return RuleResult(
            True,
            "SUSPICIOUS_VPA",
            "Receiver UPI ID pattern matches known scam identifiers",
            "FLAG",
        )
    return RuleResult(False)


def rule_otp_time_correlation(txn: dict) -> RuleResult:
    """Flag potential OTP/social-engineering behavior near recharge-like actions."""
    explicit = bool(txn.get("_otp_time_correlation", False))
    txn_type = str(txn.get("_transaction_type") or txn.get("transaction_type") or "").lower()
    is_new_receiver = int(txn.get("is_new_receiver", 0) or 0) == 1
    count_1min = int(txn.get("_sender_txn_count_1min", 0) or 0)

    inferred = txn_type in {"recharge", "bill_payment"} and is_new_receiver and count_1min >= 1
    if explicit or inferred:
        return RuleResult(
            True,
            "OTP_TIME_CORRELATION",
            "Payment immediately after OTP-type activity — possible SIM swap / social-engineering scam",
            "FLAG",
        )
    return RuleResult(False)


def rule_receiver_flagged_history(txn: dict) -> RuleResult:
    """Block if receiver has repeated fraud-linked history."""
    count = int(txn.get("receiver_fraud_flag_count", 0) or 0)
    if count >= 3:
        return RuleResult(
            True,
            "RECEIVER_FLAGGED_HISTORY",
            f"Receiver UPI has been flagged {count} times for fraud previously",
            "BLOCK",
        )
    return RuleResult(False)


def rule_amount_limit(txn: dict) -> RuleResult:
    """Block transactions above ₹1,00,000 from accounts with < 5 historical txns."""
    amount = txn.get("amount", 0)
    sender_txn_count = txn.get("_sender_txn_count", 0)
    if amount > 100000 and sender_txn_count < 5:
        return RuleResult(True, "HIGH_AMOUNT_NEW_ACCOUNT",
                          f"₹{amount:,.0f} from account with only {sender_txn_count} prior transactions",
                          "BLOCK")
    return RuleResult(False)


def rule_rapid_fire(txn: dict) -> RuleResult:
    """Flag if sender has > 10 transactions in last hour; BLOCK on extreme bursts."""
    count_1h = txn.get("_sender_txn_count_1h", 0)
    if count_1h >= 25:
        return RuleResult(True, "RAPID_FIRE_TRANSACTIONS",
                          f"{count_1h} transactions in the last hour",
                          "BLOCK")
    if count_1h > 10:
        return RuleResult(True, "RAPID_FIRE_TRANSACTIONS",
                          f"{count_1h} transactions in the last hour",
                          "FLAG")
    return RuleResult(False)


def rule_midnight_high_value(txn: dict) -> RuleResult:
    """Flag high-value transactions between midnight and 5 AM."""
    ts = txn.get("timestamp", "")
    amount = txn.get("amount", 0)
    try:
        hour = datetime.fromisoformat(ts).hour
    except (ValueError, TypeError):
        hour = datetime.now().hour

    if hour <= 5 and amount > 10000:
        return RuleResult(True, "MIDNIGHT_HIGH_VALUE",
                          f"₹{amount:,.0f} transaction at {hour}:00 hours",
                          "FLAG")
    return RuleResult(False)


def rule_self_transfer(txn: dict) -> RuleResult:
    """Block if sender == receiver (potential circular fraud)."""
    if txn.get("sender_upi", "") == txn.get("receiver_upi", ""):
        return RuleResult(True, "SELF_TRANSFER",
                          "Sender and receiver are the same account",
                          "BLOCK")
    return RuleResult(False)


def rule_velocity_amount(txn: dict) -> RuleResult:
    """Flag if total amount in last 24h exceeds ₹5,00,000."""
    total_24h = txn.get("_sender_total_24h", 0) + txn.get("amount", 0)
    if total_24h > 500000:
        return RuleResult(True, "DAILY_LIMIT_EXCEEDED",
                          f"24h cumulative amount: ₹{total_24h:,.0f} exceeds ₹5,00,000 limit",
                          "BLOCK")
    return RuleResult(False)


def rule_new_device_high_amount(txn: dict) -> RuleResult:
    """Flag if transaction from a new device exceeds ₹25,000."""
    if txn.get("_is_new_device", False) and txn.get("amount", 0) > 25000:
        return RuleResult(True, "NEW_DEVICE_HIGH_AMOUNT",
                          f"₹{txn['amount']:,.0f} from an unrecognized device",
                          "FLAG")
    return RuleResult(False)


# --- Rule Registry ---

ALL_RULES = [
    rule_burst_1min,
    rule_impossible_travel,
    rule_receiver_flagged_history,
    rule_unknown_receiver_high_amount,
    rule_suspicious_vpa,
    rule_otp_time_correlation,
    rule_amount_limit,
    rule_rapid_fire,
    rule_midnight_high_value,
    rule_self_transfer,
    rule_velocity_amount,
    rule_new_device_high_amount,
]


def evaluate_rules(txn: dict) -> list[RuleResult]:
    """Run all rules against a transaction. Returns list of triggered rules."""
    triggered = []
    for rule_fn in ALL_RULES:
        result = rule_fn(txn)
        if result.triggered:
            triggered.append(result)
    return triggered


def get_rule_decision(triggered_rules: list[RuleResult]) -> Optional[str]:
    """
    Returns the most severe action from triggered rules.
    BLOCK > FLAG > None (let ML decide)
    """
    if not triggered_rules:
        return None
    actions = [r.action for r in triggered_rules]
    if "BLOCK" in actions:
        return "BLOCK"
    if "FLAG" in actions:
        return "FLAG"
    return None
