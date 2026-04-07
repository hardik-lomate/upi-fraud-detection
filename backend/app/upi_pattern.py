"""
UPI ID Pattern Analysis — Zero-latency pre-ML risk signal.

Regex-based UPI ID risk scoring: detects newly-registered patterns,
random string suffixes typical of mule accounts, VPA length anomalies,
and bulk creation patterns.
"""

import re
from typing import Optional

# Known legitimate UPI suffixes (major banks/PSPs)
KNOWN_SUFFIXES = {
    "upi", "ybl", "paytm", "oksbi", "okaxis", "okicici",
    "okhdfcbank", "ibl", "axl", "sbi", "icici", "hdfc",
    "apl", "barodampay", "unionbankofindia", "kotak", "indus",
    "federal", "rbl", "idbi", "citi", "hsbc", "sc", "bob",
    "pnb", "canara", "boi",
}

# Patterns indicating potential fraud
RANDOM_SUFFIX_PATTERN = re.compile(r"[a-z0-9]{6,}@", re.IGNORECASE)
NUMERIC_HEAVY_PATTERN = re.compile(r"\d{4,}@")
SEQUENTIAL_NUMERIC_PATTERN = re.compile(r"(\d)\1{3,}")  # 1111, 2222 etc.
BULK_CREATION_PATTERN = re.compile(r"(user|test|temp|fake|dummy)\d+@", re.IGNORECASE)
SHORT_VPA_PATTERN = re.compile(r"^.{1,3}@")  # Very short local part


def analyze_upi_id(upi_id: str) -> dict:
    """Analyze a UPI ID for fraud risk patterns.

    Returns a dict with risk_score (0.0–1.0) and matched patterns.
    """
    if not upi_id or "@" not in upi_id:
        return {"risk_score": 0.0, "patterns": [], "risk_level": "UNKNOWN"}

    local_part, _, domain = upi_id.partition("@")
    risk_score = 0.0
    patterns = []

    # 1. Check suffix legitimacy
    if domain.lower() not in KNOWN_SUFFIXES:
        risk_score += 0.15
        patterns.append({
            "pattern": "unknown_suffix",
            "risk": "low",
            "detail": f"UPI suffix '@{domain}' is not a recognized major bank/PSP",
        })

    # 2. Random alphanumeric suffix in local part
    entropy = _calculate_entropy(local_part)
    if entropy > 3.5 and len(local_part) > 8:
        risk_score += 0.3
        patterns.append({
            "pattern": "random_alphanumeric_suffix",
            "risk": "high",
            "detail": f"Local part '{local_part}' has high entropy ({entropy:.1f}), typical of auto-generated mule accounts",
        })

    # 3. Numeric-heavy patterns
    if NUMERIC_HEAVY_PATTERN.search(upi_id):
        risk_score += 0.1
        patterns.append({
            "pattern": "numeric_heavy",
            "risk": "medium",
            "detail": "UPI ID contains long numeric sequences",
        })

    # 4. Sequential numeric pattern (bulk creation)
    if SEQUENTIAL_NUMERIC_PATTERN.search(local_part):
        risk_score += 0.25
        patterns.append({
            "pattern": "bulk_creation_pattern",
            "risk": "high",
            "detail": "Sequential repeated digits suggest bulk account creation",
        })

    # 5. Suspicious prefixes
    if BULK_CREATION_PATTERN.match(upi_id):
        risk_score += 0.35
        patterns.append({
            "pattern": "suspicious_prefix",
            "risk": "high",
            "detail": "UPI ID uses test/temp/fake prefix pattern",
        })

    # 6. Very short VPA local part
    if len(local_part) <= 3:
        risk_score += 0.1
        patterns.append({
            "pattern": "short_vpa",
            "risk": "medium",
            "detail": f"Very short VPA local part '{local_part}' (< 4 chars)",
        })

    # 7. Very long VPA (auto-generated)
    if len(local_part) > 20:
        risk_score += 0.15
        patterns.append({
            "pattern": "long_vpa",
            "risk": "medium",
            "detail": f"Unusually long VPA local part ({len(local_part)} chars), possible auto-generation",
        })

    risk_score = min(risk_score, 1.0)

    if risk_score >= 0.5:
        risk_level = "HIGH"
    elif risk_score >= 0.2:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "upi_id": upi_id,
        "risk_score": round(risk_score, 3),
        "risk_level": risk_level,
        "patterns": patterns,
        "pattern_count": len(patterns),
    }


def _calculate_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    import math
    if not s:
        return 0.0
    freq = {}
    for c in s.lower():
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    entropy = 0.0
    for count in freq.values():
        p = count / length
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def get_sender_receiver_vpa_risk(sender_upi: str, receiver_upi: str) -> dict:
    """Analyze both sender and receiver UPI IDs."""
    sender_analysis = analyze_upi_id(sender_upi)
    receiver_analysis = analyze_upi_id(receiver_upi)

    combined_score = max(sender_analysis["risk_score"], receiver_analysis["risk_score"])

    return {
        "sender": sender_analysis,
        "receiver": receiver_analysis,
        "combined_vpa_risk": round(combined_score, 3),
    }


def detect_scam_vpa_pattern(receiver_upi: str) -> dict:
    """
    Detect scam-like receiver UPI handle patterns used in social-engineering attacks.
    Returns normalized detector payload for rules/features.
    """
    upi_id = (receiver_upi or "").strip().lower()
    if "@" not in upi_id:
        return {
            "is_suspicious": True,
            "pattern_matched": "invalid_upi_format",
            "risk_score": 1.0,
            "reason": "Receiver UPI format is invalid",
        }

    local, _, suffix = upi_id.partition("@")
    keywords = ("bank", "helpline", "support", "care", "refund", "reward", "prize")

    if any(k in local for k in keywords):
        return {
            "is_suspicious": True,
            "pattern_matched": "impersonation_keyword",
            "risk_score": 0.95,
            "reason": "UPI handle contains bank/support style impersonation keywords",
        }

    if local.isdigit() and len(local) >= 6:
        return {
            "is_suspicious": True,
            "pattern_matched": "all_digits_handle",
            "risk_score": 0.90,
            "reason": "UPI handle is mostly digits, typical of throwaway fraud IDs",
        }

    if suffix not in KNOWN_SUFFIXES:
        return {
            "is_suspicious": True,
            "pattern_matched": "unknown_suffix",
            "risk_score": 0.80,
            "reason": "UPI suffix is not in the known PSP/bank list",
        }

    if len(local) > 30:
        return {
            "is_suspicious": True,
            "pattern_matched": "very_long_handle",
            "risk_score": 0.85,
            "reason": "UPI handle length is unusually long",
        }

    if re.search(r"\d{4,}$", local):
        return {
            "is_suspicious": True,
            "pattern_matched": "numeric_tail_pattern",
            "risk_score": 0.78,
            "reason": "UPI handle ends with a long numeric tail",
        }

    baseline = analyze_upi_id(upi_id)
    return {
        "is_suspicious": baseline.get("risk_score", 0.0) >= 0.5,
        "pattern_matched": "none",
        "risk_score": float(baseline.get("risk_score", 0.1)),
        "reason": "UPI handle does not match known scam patterns",
    }
