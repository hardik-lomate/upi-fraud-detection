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
  normal: { highRiskChance: 0.09, knownSenderChance: 0.35 },
  peak: { highRiskChance: 0.14, knownSenderChance: 0.45 },
  stress: { highRiskChance: 0.21, knownSenderChance: 0.5 },
};

const STABLE_SENDERS = ['alice@upi', 'bob@upi', 'charlie@upi', 'repeat@upi', 'salary_user@upi'];
const RECEIVERS = [
  'merchant@upi',
  'shop@upi',
  'wallet@upi',
  'billpay@upi',
  'tax@upi',
  'insurance@upi',
  'fuel@upi',
  'hospital@upi',
];

function amountForProfile(profile) {
  const roll = Math.random();
  if (profile === 'stress') {
    if (roll < 0.5) return randInt(80, 4500);
    if (roll < 0.82) return randInt(4500, 25000);
    return randInt(25000, 180000);
  }
  if (profile === 'peak') {
    if (roll < 0.6) return randInt(80, 6500);
    if (roll < 0.87) return randInt(6500, 28000);
    return randInt(28000, 125000);
  }
  if (roll < 0.72) return randInt(60, 5000);
  if (roll < 0.93) return randInt(5000, 22000);
  return randInt(22000, 80000);
}

export function generateTransactionInput(options = {}) {
  const profile = PROFILE_CONFIG[options.profile] ? options.profile : 'normal';
  const cfg = PROFILE_CONFIG[profile];

  const dynamicSender = `user${randInt(100, 999)}@upi`;
  const sender_upi = Math.random() < cfg.knownSenderChance ? pick(STABLE_SENDERS) : dynamicSender;
  const receiver_upi = pick(RECEIVERS);
  const amount = amountForProfile(profile);

  const stableDevice = `WEB_${sender_upi.replace(/[^a-z0-9]/gi, '_')}_KNOWN`;
  const newDevice = `WEB_${sender_upi.replace(/[^a-z0-9]/gi, '_')}_NEW_${randInt(100, 999)}`;

  let sender_device_id = stableDevice;
  if (amount >= 25000 && Math.random() < 0.55) {
    sender_device_id = newDevice;
  }
  if (profile === 'stress' && Math.random() < cfg.highRiskChance) {
    sender_device_id = newDevice;
  }

  const transaction_type = pick(['purchase', 'purchase', 'transfer', 'bill_payment', 'recharge']);

  return {
    sender_upi,
    receiver_upi,
    amount,
    transaction_type,
    sender_device_id,
  };
}

export function simulatePredictFallback(input) {
  const key = [input.sender_upi, input.receiver_upi, input.amount, input.transaction_type, input.sender_device_id].join('|');
  const h = stableHash(key);
  const base = input.amount >= 25000 ? 0.34 : input.amount >= 9000 ? 0.22 : 0.08;
  const noise = ((h % 281) / 1000); // deterministic 0.000 - 0.280
  const fraud_score = Math.max(0, Math.min(1, base + noise));

  let decision = 'ALLOW';
  let status = 'ALLOWED';
  let message = 'Approved.';

  if (fraud_score >= 0.3 && fraud_score <= 0.7) {
    decision = 'VERIFY';
    status = 'PENDING';
    message = 'Verification required.';
  }

  if (fraud_score > 0.7) {
    decision = 'BLOCK';
    status = 'BLOCKED';
    message = 'Blocked for safety.';
  }

  const transaction_id = `SIM_${h.toString(16).slice(0, 12)}`;

  const reasons = [];
  if (input.amount >= 25000) reasons.push('High transaction amount');
  if ((input.sender_device_id || '').includes('_NEW_')) reasons.push('New device');
  if (reasons.length === 0) reasons.push('No strong anomaly detected');

  return {
    transaction_id,
    fraud_score,
    risk_score: fraud_score,
    decision,
    status,
    message,
    reasons,
    models_used: ['simulated'],
    model_version: 'demo',
    timestamp: new Date().toISOString(),
  };
}

export function simulateVerifyFallback(txn) {
  const h = stableHash(txn?.transaction_id || '');
  const threshold = txn.fraud_score < 0.6 ? 80 : 45;
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
