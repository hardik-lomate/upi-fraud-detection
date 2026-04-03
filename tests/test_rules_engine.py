"""Tests for all 6 rules — each rule has a should_trigger and should_not_trigger test."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.rules_engine import (
    rule_amount_limit, rule_rapid_fire, rule_midnight_high_value,
    rule_self_transfer, rule_velocity_amount, rule_new_device_high_amount,
    evaluate_rules, get_rule_decision,
)


# === rule_amount_limit ===

def test_amount_limit_triggers():
    result = rule_amount_limit({"amount": 150000, "_sender_txn_count": 3})
    assert result.triggered
    assert result.action == "BLOCK"

def test_amount_limit_no_trigger_low_amount():
    result = rule_amount_limit({"amount": 5000, "_sender_txn_count": 3})
    assert not result.triggered

def test_amount_limit_no_trigger_high_count():
    result = rule_amount_limit({"amount": 150000, "_sender_txn_count": 10})
    assert not result.triggered


# === rule_rapid_fire ===

def test_rapid_fire_triggers():
    result = rule_rapid_fire({"_sender_txn_count_1h": 15})
    assert result.triggered
    assert result.action == "FLAG"

def test_rapid_fire_no_trigger():
    result = rule_rapid_fire({"_sender_txn_count_1h": 5})
    assert not result.triggered


# === rule_midnight_high_value ===

def test_midnight_triggers():
    result = rule_midnight_high_value({"timestamp": "2026-04-03T02:30:00", "amount": 15000})
    assert result.triggered
    assert result.action == "FLAG"

def test_midnight_no_trigger_daytime():
    result = rule_midnight_high_value({"timestamp": "2026-04-03T14:00:00", "amount": 15000})
    assert not result.triggered

def test_midnight_no_trigger_low_amount():
    result = rule_midnight_high_value({"timestamp": "2026-04-03T02:30:00", "amount": 500})
    assert not result.triggered


# === rule_self_transfer ===

def test_self_transfer_triggers():
    result = rule_self_transfer({"sender_upi": "same@upi", "receiver_upi": "same@upi"})
    assert result.triggered
    assert result.action == "BLOCK"

def test_self_transfer_no_trigger():
    result = rule_self_transfer({"sender_upi": "alice@upi", "receiver_upi": "bob@upi"})
    assert not result.triggered


# === rule_velocity_amount ===

def test_velocity_triggers():
    result = rule_velocity_amount({"_sender_total_24h": 400000, "amount": 200000})
    assert result.triggered
    assert result.action == "BLOCK"

def test_velocity_no_trigger():
    result = rule_velocity_amount({"_sender_total_24h": 50000, "amount": 1000})
    assert not result.triggered


# === rule_new_device_high_amount ===

def test_new_device_triggers():
    result = rule_new_device_high_amount({"_is_new_device": True, "amount": 30000})
    assert result.triggered
    assert result.action == "FLAG"

def test_new_device_no_trigger_known_device():
    result = rule_new_device_high_amount({"_is_new_device": False, "amount": 30000})
    assert not result.triggered

def test_new_device_no_trigger_low_amount():
    result = rule_new_device_high_amount({"_is_new_device": True, "amount": 500})
    assert not result.triggered


# === Composite: evaluate_rules ===

def test_evaluate_rules_multiple_triggers():
    txn = {
        "sender_upi": "same@upi", "receiver_upi": "same@upi",
        "amount": 200000, "_sender_txn_count": 2,
        "_sender_txn_count_1h": 15, "_sender_total_24h": 100000,
        "_is_new_device": True, "timestamp": "2026-04-03T14:00:00",
    }
    triggered = evaluate_rules(txn)
    assert len(triggered) >= 2
    names = [r.rule_name for r in triggered]
    assert "SELF_TRANSFER" in names


def test_get_rule_decision_block_over_flag():
    from backend.app.rules_engine import RuleResult
    rules = [
        RuleResult(True, "FLAG_RULE", "test", "FLAG"),
        RuleResult(True, "BLOCK_RULE", "test", "BLOCK"),
    ]
    assert get_rule_decision(rules) == "BLOCK"


def test_get_rule_decision_none_when_empty():
    assert get_rule_decision([]) is None
