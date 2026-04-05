/**
 * simulate.js v3.0 — Realistic fraud distribution for offline demo.
 * Target: normal=78% ALLOW / 17% VERIFY / 5% BLOCK
 */

function randInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function pick(arr) {
  return arr[randInt(0, arr.length - 1)];
}

function stableHash(value) {
  const str = String(value || '');
  let hash = 0;
  for (let i = 0; i < str.length; i += 1) {
    hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

const PROFILE_CONFIG = {
  normal:  { fraudInjectChance: 0.22, highAmountChance: 0.20 },
  peak:    { fraudInjectChance: 0.32, highAmountChance: 0.28 },
  stress:  { fraudInjectChance: 0.45, highAmountChance: 0.38 },
  attack:  { fraudInjectChance: 0.55, highAmountChance: 0.45 },
};

const STABLE_SENDERS = ['alice@upi', 'bob@upi', 'charlie@upi', 'repeat@upi', 'salary_user@upi'];
const RECEIVERS = ['merchant@upi', 'shop@upi', 'wallet@upi', 'billpay@upi', 'tax@upi', 'insurance@upi', 'fuel@upi', 'hospital@upi'];

const FRAUD_SENDERS = ['attacker_001@ybl', 'sim_swap_victim@upi', 'mule_driver@paytm', 'velocity_bot@oksbi', 'account_takeover@upi'];
const FRAUD_RECEIVERS = ['mule_a@ybl', 'offshore_xk9f2@ybl', 'drop_account@okicici', 'mule_b@paytm', 'cash_out_001@upi'];

function amountForProfile(profile, isFraud) {
  const roll = Math.random();

  // Fraud transactions have higher amounts
  if (isFraud) {
    if (roll < 0.3) return randInt(5000, 25000);
    if (roll < 0.7) return randInt(25000, 100000);
    return randInt(100000, 300000);
  }

  // Normal transactions — recalibrated: fewer micro-payments
  if (profile === 'stress') {
    if (roll < 0.35) return randInt(500, 5000);
    if (roll < 0.70) return randInt(5000, 25000);
    if (roll < 0.90) return randInt(25000, 100000);
    return randInt(100000, 200000);
  }
  if (profile === 'peak') {
    if (roll < 0.40) return randInt(500, 5000);
    if (roll < 0.75) return randInt(5000, 25000);
    if (roll < 0.92) return randInt(25000, 80000);
    return randInt(80000, 150000);
  }
  // normal
  if (roll < 0.45) return randInt(500, 5000);
  if (roll < 0.80) return randInt(5000, 25000);
  if (roll < 0.95) return randInt(25000, 80000);
  return randInt(80000, 120000);
}

export function generateTransactionInput(options = {}) {
  const profile = PROFILE_CONFIG[options.profile] ? options.profile : 'normal';
  const cfg = PROFILE_CONFIG[profile];

  // Determine if this should be a fraud transaction
  const isFraud = Math.random() < cfg.fraudInjectChance;

  let sender_upi, receiver_upi;
  if (isFraud) {
    sender_upi = pick(FRAUD_SENDERS);
    receiver_upi = pick(FRAUD_RECEIVERS);
  } else {
    const dynamicSender = `user${randInt(100, 999)}@upi`;
    sender_upi = Math.random() < 0.35 ? pick(STABLE_SENDERS) : dynamicSender;
    receiver_upi = pick(RECEIVERS);
  }

  const amount = amountForProfile(profile, isFraud);

  // Device — fraud transactions get new devices
  const stableDevice = `WEB_${sender_upi.replace(/[^a-z0-9]/gi, '_')}_KNOWN`;
  const newDevice = `WEB_${sender_upi.replace(/[^a-z0-9]/gi, '_')}_NEW_${randInt(100, 999)}`;

  let sender_device_id = stableDevice;
  if (isFraud) {
    sender_device_id = newDevice;
  } else if (amount >= 15000 && Math.random() < 0.35) {
    sender_device_id = newDevice;
  }

  const transaction_type = isFraud
    ? 'transfer'
    : pick(['purchase', 'purchase', 'transfer', 'bill_payment', 'recharge']);

  const txn = {
    sender_upi,
    receiver_upi,
    amount,
    transaction_type,
    sender_device_id,
  };

  // Inject additional fraud signals
  if (isFraud && Math.random() < 0.3) {
    // Night time override
    const nightTime = new Date();
    nightTime.setHours(2 + randInt(0, 3), randInt(0, 59));
    txn.timestamp = nightTime.toISOString();
  }

  if (isFraud && Math.random() < 0.2) {
    // Impossible travel — inject location far from previous
    txn.sender_location_lat = pick([28.614, 12.972, 23.963]);  // Delhi/Bangalore/Jamtara
    txn.sender_location_lon = pick([77.209, 77.595, 86.814]);
  }

  return txn;
}

export function simulatePredictFallback(input) {
  const key = [input.sender_upi, input.receiver_upi, input.amount, input.transaction_type, input.sender_device_id].join('|');
  const h = stableHash(key);

  // Multi-signal scoring (not just amount-based)
  let score = 0.06;
  const reasons = [];

  // Fraud sender/receiver detection
  const isFraudSender = FRAUD_SENDERS.some(s => input.sender_upi?.includes(s.split('@')[0]));
  const isFraudReceiver = FRAUD_RECEIVERS.some(r => input.receiver_upi?.includes(r.split('@')[0]));

  if (isFraudSender || isFraudReceiver) {
    score += 0.35;
    reasons.push('Known fraud actor detected');
  }

  // New device signal
  if ((input.sender_device_id || '').includes('_NEW_')) {
    score += 0.18;
    reasons.push('Transaction from unrecognized device');
  }

  // Amount risk
  if (input.amount >= 100000) {
    score += 0.22;
    reasons.push(`Very high amount: Rs.${input.amount.toLocaleString()}`);
  } else if (input.amount >= 25000) {
    score += 0.15;
    reasons.push(`High amount: Rs.${input.amount.toLocaleString()}`);
  } else if (input.amount >= 10000) {
    score += 0.08;
    reasons.push(`Elevated amount: Rs.${input.amount.toLocaleString()}`);
  }

  // Night time
  const hour = input.timestamp ? new Date(input.timestamp).getHours() : new Date().getHours();
  if (hour >= 0 && hour < 5) {
    score += 0.12;
    reasons.push('Late night transaction (high-risk window)');
  }

  // Transfer to unknown
  if (input.transaction_type === 'transfer' && isFraudReceiver) {
    score += 0.10;
    reasons.push('Transfer to suspicious recipient');
  }

  // Compound: new device + high amount
  if ((input.sender_device_id || '').includes('_NEW_') && input.amount >= 15000) {
    score += 0.12;
    reasons.push('New device with high-value transfer');
  }

  // Add small deterministic noise
  const noise = ((h % 150) - 75) / 1000;  // ±0.075
  const fraud_score = Math.max(0, Math.min(1, score + noise));

  // Recalibrated thresholds matching backend
  let decision = 'ALLOW';
  let status = 'ALLOWED';
  let message = `Rs.${input.amount?.toLocaleString() || 0} transaction approved. Low risk.`;

  if (fraud_score >= 0.18 && fraud_score < 0.60) {
    decision = 'VERIFY';
    status = 'PENDING';
    message = `Verification required: ${reasons[0] || 'elevated risk score'}. Confirm your identity.`;
  }

  if (fraud_score >= 0.60) {
    decision = 'BLOCK';
    status = 'BLOCKED';
    message = `Transaction blocked: ${reasons[0] || 'multiple risk signals detected'}. Contact your bank if legitimate.`;
  }

  if (reasons.length === 0) reasons.push('No strong anomaly detected');

  const transaction_id = `SIM_${h.toString(16).slice(0, 12)}`;

  return {
    transaction_id,
    fraud_score,
    risk_score: fraud_score,
    decision,
    status,
    message,
    reasons,
    individual_scores: {
      xgboost: Math.min(1, fraud_score * 1.1),
      lightgbm: Math.min(1, fraud_score * 0.95),
      isolation_forest: Math.min(1, fraud_score * 0.8),
    },
    models_used: ['simulated'],
    model_version: 'demo-3.0',
    timestamp: input.timestamp || new Date().toISOString(),
  };
}

export function simulateVerifyFallback(txn) {
  const h = stableHash(txn?.transaction_id || '');
  const threshold = txn.fraud_score < 0.45 ? 80 : 40;
  const pass = (h % 100) < threshold;
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
