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
    """Flag if sender has > 10 transactions in last hour."""
    count_1h = txn.get("_sender_txn_count_1h", 0)
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
