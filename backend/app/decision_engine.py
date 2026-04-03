"""
Decision Engine — Uses thresholds from feature_contract.py.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import THRESHOLD_FLAG, THRESHOLD_BLOCK


def make_decision(fraud_score: float) -> tuple:
    if fraud_score < THRESHOLD_FLAG:
        return ("ALLOW", "LOW", "Transaction appears legitimate. Approved.")
    elif fraud_score < THRESHOLD_BLOCK:
        return ("FLAG", "MEDIUM", "Transaction flagged for manual review. Suspicious patterns detected.")
    else:
        return ("BLOCK", "HIGH", "Transaction blocked. High fraud probability detected.")
