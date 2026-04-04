"""End-to-end verification of all critical endpoints."""
from datetime import datetime
import requests
import sys

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0

# Use per-run identifiers so repeated runs don't accumulate sender-history
# and accidentally trip velocity/rapid-fire rules.
RUN_ID = datetime.utcnow().strftime("%Y%m%d%H%M%S")
ALICE = f"alice_e2e_{RUN_ID}@upi"
BOB = f"bob_e2e_{RUN_ID}@upi"
FRAUD = f"fraud_e2e_{RUN_ID}@upi"
NEWUSER = f"newuser_e2e_{RUN_ID}@upi"
SHOP = f"shop_e2e_{RUN_ID}@upi"

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name} {detail}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")

print("=" * 60)
print("E2E VERIFICATION")
print("=" * 60)

# 1. Legit transaction -> ALLOW
print("\n--- 1. Legit Transaction ---")
r = requests.post(f"{BASE}/predict", json={
    "transaction_id": f"e2e_{RUN_ID}_legit_001",
    "sender_upi": ALICE, "receiver_upi": BOB,
    "amount": 500, "transaction_type": "purchase",
    "sender_device_id": "DEV_001"
})
d = r.json()
check("HTTP 200", r.status_code == 200, f"(got {r.status_code})")
check("Decision=ALLOW", d["decision"] == "ALLOW", f"(got {d['decision']})")
check("Score < 0.5", d["fraud_score"] < 0.5, f"(got {d['fraud_score']})")
check("3 models used", len(d["models_used"]) == 3, f"(got {d['models_used']})")
check("Has risk_breakdown", d.get("risk_breakdown") is not None)
check("Has model_version", d.get("model_version") is not None, f"(got {d.get('model_version')})")

# 2. Self-transfer -> BLOCK (rule)
print("\n--- 2. Self-Transfer (should BLOCK) ---")
r2 = requests.post(f"{BASE}/predict", json={
    "transaction_id": f"e2e_{RUN_ID}_self_001",
    "sender_upi": FRAUD, "receiver_upi": FRAUD,
    "amount": 5000, "transaction_type": "transfer",
    "sender_device_id": "DEV_002"
})
d2 = r2.json()
check("HTTP 200", r2.status_code == 200)
check("Decision=BLOCK", d2["decision"] == "BLOCK", f"(got {d2['decision']})")
check("SELF_TRANSFER rule", any(r["rule_name"] == "SELF_TRANSFER" for r in d2["rules_triggered"]),
      f"(rules: {[r['rule_name'] for r in d2['rules_triggered']]})")

# 3. High amount new account -> BLOCK (rule)
print("\n--- 3. High Amount New Account (should BLOCK) ---")
r3 = requests.post(f"{BASE}/predict", json={
    "transaction_id": f"e2e_{RUN_ID}_newacct_001",
    "sender_upi": NEWUSER, "receiver_upi": SHOP,
    "amount": 150000, "transaction_type": "transfer",
    "sender_device_id": "DEV_003"
})
d3 = r3.json()
check("HTTP 200", r3.status_code == 200)
check("Decision=BLOCK", d3["decision"] == "BLOCK", f"(got {d3['decision']})")
check("HIGH_AMOUNT rule", any(r["rule_name"] == "HIGH_AMOUNT_NEW_ACCOUNT" for r in d3["rules_triggered"]),
      f"(rules: {[r['rule_name'] for r in d3['rules_triggered']]})")

# 4. Input validation
print("\n--- 4. Input Validation ---")
r4 = requests.post(f"{BASE}/predict", json={
    "sender_upi": "a@upi", "receiver_upi": "b@upi",
    "amount": -500, "transaction_type": "purchase",
    "sender_device_id": "DEV_001"
})
check("Negative amount rejected", r4.status_code == 422, f"(got {r4.status_code})")

r5 = requests.post(f"{BASE}/predict", json={
    "sender_upi": "a@upi", "receiver_upi": "b@upi",
    "amount": 500, "transaction_type": "invalid_type",
    "sender_device_id": "DEV_001"
})
check("Invalid txn_type rejected", r5.status_code == 422, f"(got {r5.status_code})")

# 5. Health endpoints
print("\n--- 5. Health Checks ---")
r6 = requests.get(f"{BASE}/health")
check("/health returns 200", r6.status_code == 200)
h = r6.json()
check("Has model_version", h.get("model_version") is not None)

r7 = requests.get(f"{BASE}/health/ready")
check("/health/ready returns 200", r7.status_code == 200)
hr = r7.json()
check("DB check present", "database" in hr.get("checks", {}))
check("Models loaded", hr.get("checks", {}).get("models", {}).get("status") == "ok",
      f"(got {hr.get('checks', {}).get('models')})")

# 6. Feedback
print("\n--- 6. Feedback ---")
r8 = requests.post(f"{BASE}/feedback", json={
    "transaction_id": f"e2e_{RUN_ID}_feedback_001",
    "analyst_verdict": "confirmed_fraud"
})
check("Feedback accepted", r8.status_code == 200, f"(got {r8.status_code})")

# 7. Model info
print("\n--- 7. Model Info ---")
r9 = requests.get(f"{BASE}/model/info")
check("/model/info returns 200", r9.status_code == 200)
mi = r9.json()
check("Has trained_at", mi.get("trained_at") is not None)
check("Has feature_columns", mi.get("feature_columns") is not None)
check("Has thresholds", mi.get("thresholds") is not None)

# 8. Transactions
print("\n--- 8. Transactions ---")
r10 = requests.get(f"{BASE}/transactions?limit=5")
check("/transactions returns 200", r10.status_code == 200)

# 9. Monitoring
print("\n--- 9. Monitoring ---")
r11 = requests.get(f"{BASE}/monitoring/stats")
check("/monitoring/stats returns 200", r11.status_code == 200)

r12 = requests.get(f"{BASE}/monitoring/store")
check("/monitoring/store returns 200", r12.status_code == 200)
store = r12.json()
check("Store backend reported", store.get("backend") in ("redis", "memory"))

# Summary
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL}")
print("=" * 60)

if FAIL > 0:
    sys.exit(1)
