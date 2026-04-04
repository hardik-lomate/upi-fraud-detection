function randInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function pick(arr) {
  return arr[randInt(0, arr.length - 1)];
}

export function generateTransactionInput() {
  // Backend requires these fields; UI intentionally does NOT ask the user.
  const senders = ['alice@upi', 'bob@upi', 'charlie@upi', 'repeat@upi'];
  const receivers = ['merchant@upi', 'shop@upi', 'wallet@upi', 'billpay@upi'];

  const sender_upi = pick(senders);
  const receiver_upi = pick(receivers);

  // Bias amounts to produce a mix of safe + verify flows.
  const amount = Math.random() < 0.25 ? randInt(26000, 80000) : randInt(50, 8000);

  // New device occasionally to trigger step-up rules.
  const deviceSuffix = randInt(100, 999);
  const sender_device_id = Math.random() < 0.55 ? `WEB_DEMO_NEW_${deviceSuffix}` : 'WEB_DEMO_KNOWN';

  const transaction_type = pick(['purchase', 'transfer', 'bill_payment', 'recharge']);

  return {
    sender_upi,
    receiver_upi,
    amount,
    transaction_type,
    sender_device_id,
  };
}

export function simulatePredictFallback(input) {
  const fraud_score = Math.max(0, Math.min(1, (input.amount / 90000) + Math.random() * 0.2));

  let decision = 'ALLOW';
  let status = 'ALLOWED';
  let message = 'Transaction appears legitimate. Approved.';

  if (fraud_score >= 0.3 && fraud_score <= 0.7) {
    decision = 'REQUIRE_BIOMETRIC';
    status = 'PENDING_VERIFICATION';
    message = 'Suspicious activity detected. Biometric verification required to proceed.';
  }

  if (fraud_score > 0.7) {
    decision = 'REQUIRE_BIOMETRIC';
    status = 'PENDING_VERIFICATION';
    message = 'High risk detected. Biometric verification required before transaction can proceed.';
  }

  const transaction_id = `SIM_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;

  return {
    transaction_id,
    fraud_score,
    decision,
    status,
    message,
    reasons: fraud_score > 0.7
      ? ['↑ amount', '↑ new_device', '↑ unusual_timing']
      : fraud_score >= 0.3
      ? ['↑ new_device', '↑ amount_deviation']
      : ['↓ typical_amount', '↓ known_pattern'],
    models_used: ['simulated'],
    model_version: 'demo',
    timestamp: new Date().toISOString(),
  };
}

export function simulateVerifyFallback(txn) {
  const pass = Math.random() < (txn.fraud_score < 0.6 ? 0.8 : 0.45);
  return {
    transaction_id: txn.transaction_id,
    verification_status: pass ? 'VERIFIED' : 'FAILED',
    final_decision: pass ? 'ALLOW' : 'BLOCK',
    message: pass
      ? 'Fingerprint verification successful. Transaction approved.'
      : 'Fingerprint verification failed. Transaction blocked for security.',
    method: 'fingerprint',
    fraud_score: txn.fraud_score,
    confidence: Math.round((pass ? 85 : 70)),
  };
}
