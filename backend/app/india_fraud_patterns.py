"""
India-Specific Fraud Pattern Database — 12 real UPI fraud patterns
documented by NPCI and RBI.

Each pattern has detection logic and a human-readable explanation.
Used in the pipeline after ML scoring to identify specific fraud types.
"""

from typing import Optional


class FraudPattern:
    def __init__(self, pattern_id, name, risk_boost, message):
        self.pattern_id = pattern_id
        self.name = name
        self.risk_boost = risk_boost
        self.message = message


FRAUD_PATTERNS = [
    {
        "id": "PATTERN_001",
        "name": "SIM Swap Attack",
        "risk_boost": 0.45,
        "message": "Possible SIM swap: new device + new receiver + elevated amount within first activity window",
    },
    {
        "id": "PATTERN_002",
        "name": "OTP Fraud (Social Engineering)",
        "risk_boost": 0.30,
        "message": "OTP sharing pattern: multiple rapid small transfers to different receivers suggests victim was tricked into sharing OTP",
    },
    {
        "id": "PATTERN_003",
        "name": "Fake KYC Scam",
        "risk_boost": 0.55,
        "message": "Possible fake KYC scam: payment to an account name matching KYC/support patterns",
    },
    {
        "id": "PATTERN_004",
        "name": "Smurfing (Structuring)",
        "risk_boost": 0.50,
        "message": "Smurfing pattern: multiple transactions just below Rs.5000 threshold — possible structuring to avoid detection",
    },
    {
        "id": "PATTERN_005",
        "name": "Money Mule Consolidation",
        "risk_boost": 0.60,
        "message": "Money mule consolidation: account aggregating funds from multiple sources before forwarding — classic mule behavior",
    },
    {
        "id": "PATTERN_006",
        "name": "Deepfake/Fake QR Merchant",
        "risk_boost": 0.35,
        "message": "New isolated merchant UPI: this merchant has no transaction history in our network — verify QR code authenticity",
    },
    {
        "id": "PATTERN_007",
        "name": "Loan App Fraud",
        "risk_boost": 0.45,
        "message": "Possible loan app fraud: payment to a lending service — verify this is legitimate before proceeding",
    },
    {
        "id": "PATTERN_008",
        "name": "Overnight Account Drain",
        "risk_boost": 0.55,
        "message": "Overnight drain pattern: unusual volume of transfers in the 1-4 AM window — account may be compromised",
    },
    {
        "id": "PATTERN_009",
        "name": "Impersonation (Bank/Govt)",
        "risk_boost": 0.65,
        "message": "CRITICAL: Government/bank impersonation detected. Legitimate agencies never collect payments via UPI. Do NOT proceed.",
    },
    {
        "id": "PATTERN_010",
        "name": "Rapid Account Cycling",
        "risk_boost": 0.70,
        "message": "Transaction cycle detected: funds flowing in a loop — indicative of layering in money laundering",
    },
    {
        "id": "PATTERN_011",
        "name": "Refund Fraud",
        "risk_boost": 0.50,
        "message": "Refund fraud pattern: you are sending more than you received from this person — classic overpayment scam",
    },
    {
        "id": "PATTERN_012",
        "name": "Account Takeover via UPI PIN Reset",
        "risk_boost": 0.75,
        "message": "Account takeover pattern: failed access attempts followed by unusual transaction from new device — block and verify",
    },
]

# Known scam UPI patterns
SCAM_VPA_KEYWORDS = [
    "kyc", "verify", "update", "paytmcare", "support",
    "refund", "helpdesk", "customer", "service",
    "rbi_", "npci_", "sbi_", "pm_", "govt_", "tax_",
]

LOAN_VPA_KEYWORDS = [
    "loan", "credit", "finserv", "lending", "emi", "cashbean",
    "moneytap", "kreditbee", "dhani", "branch",
]


def detect_patterns(
    sender_upi: str,
    receiver_upi: str,
    amount: float,
    is_new_device: bool = False,
    is_new_receiver: bool = False,
    is_night: bool = False,
    velocity_count: int = 0,
    sender_txn_count_24h: int = 0,
    receiver_txn_count_24h: int = 0,
    is_self_transfer: bool = False,
    graph_info: Optional[dict] = None,
    hour: int = 12,
) -> list:
    """Detect which India-specific fraud patterns match this transaction."""
    matches = []
    receiver_local = (receiver_upi.split("@")[0] if receiver_upi else "").lower()
    sender_local = (sender_upi.split("@")[0] if sender_upi else "").lower()
    graph_info = graph_info or {}

    # PATTERN_001: SIM Swap Attack
    if is_new_device and amount > 5000 and is_new_receiver and sender_txn_count_24h <= 2:
        matches.append({**FRAUD_PATTERNS[0], "confidence": 0.85})

    # PATTERN_002: OTP Fraud
    if velocity_count >= 3 and amount < 2000 and is_new_receiver:
        matches.append({**FRAUD_PATTERNS[1], "confidence": 0.70})

    # PATTERN_003: Fake KYC Scam
    if any(kw in receiver_local for kw in SCAM_VPA_KEYWORDS[:9]) and 1 <= amount <= 5000:
        matches.append({**FRAUD_PATTERNS[2], "confidence": 0.80})

    # PATTERN_004: Smurfing
    if 4500 <= amount <= 4999 and velocity_count >= 2:
        matches.append({**FRAUD_PATTERNS[3], "confidence": 0.75})

    # PATTERN_005: Money Mule Consolidation
    receiver_in_degree = graph_info.get("in_degree", 0)
    if receiver_in_degree >= 5 and amount > 10000:
        matches.append({**FRAUD_PATTERNS[4], "confidence": 0.80})

    # PATTERN_006: Fake QR Merchant
    if receiver_txn_count_24h == 0 and "merchant" in receiver_local and amount > 10000:
        matches.append({**FRAUD_PATTERNS[5], "confidence": 0.65})

    # PATTERN_007: Loan App Fraud
    if any(kw in receiver_local for kw in LOAN_VPA_KEYWORDS) and amount < 5000:
        matches.append({**FRAUD_PATTERNS[6], "confidence": 0.70})

    # PATTERN_008: Overnight Account Drain
    if 1 <= hour <= 4 and velocity_count >= 2 and amount > 5000:
        matches.append({**FRAUD_PATTERNS[7], "confidence": 0.80})

    # PATTERN_009: Impersonation
    if any(kw in receiver_local for kw in SCAM_VPA_KEYWORDS[9:]) and is_new_receiver:
        matches.append({**FRAUD_PATTERNS[8], "confidence": 0.90})

    # PATTERN_010: Rapid Account Cycling
    if is_self_transfer:
        matches.append({**FRAUD_PATTERNS[9], "confidence": 0.85})

    # PATTERN_011: Refund Fraud (simplified — would need tx history)
    # Detected when sender receives from same entity and sends back more

    # PATTERN_012: Account Takeover
    if is_new_device and amount > 25000 and is_new_receiver and is_night:
        matches.append({**FRAUD_PATTERNS[11], "confidence": 0.90})

    return matches


def get_pattern_boost(matches: list) -> float:
    """Get the highest risk boost from matched patterns."""
    if not matches:
        return 0.0
    return max(m.get("risk_boost", 0) for m in matches)


def get_pattern_summary(matches: list) -> str:
    """Get a human-readable summary of matched patterns."""
    if not matches:
        return ""
    names = [m["name"] for m in matches[:3]]
    return f"Detected: {', '.join(names)}"
