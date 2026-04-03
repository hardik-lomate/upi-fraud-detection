# Thresholds — tune these based on your model's performance
ALLOW_THRESHOLD = 0.3  # Below this → transaction is safe
FLAG_THRESHOLD = 0.7  # Between ALLOW and FLAG → needs manual review
# Above FLAG → auto-block


def make_decision(fraud_score: float) -> tuple:
    """
    Returns: (decision, risk_level, message)
    """
    if fraud_score < ALLOW_THRESHOLD:
        return (
            "ALLOW",
            "LOW",
            "Transaction appears legitimate. Approved.",
        )
    elif fraud_score < FLAG_THRESHOLD:
        return (
            "FLAG",
            "MEDIUM",
            "Transaction flagged for manual review. Suspicious patterns detected.",
        )
    else:
        return (
            "BLOCK",
            "HIGH",
            "Transaction blocked. High fraud probability detected.",
        )
