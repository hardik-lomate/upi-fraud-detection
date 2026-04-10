import { api } from './client';

const SIMULATION_ENDPOINTS = ['/simulation', '/simulate', '/api/v1/simulation'];

function clamp01(value) {
  const v = Number(value);
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(1, v));
}

function normalizeDecision(decision, status) {
  const raw = String(decision || status || 'ALLOW').toUpperCase();
  if (raw === 'VERIFY' || raw === 'STEP_UP' || raw === 'STEPUP') return 'STEP-UP';
  if (raw === 'BLOCK' || raw === 'BLOCKED') return 'BLOCK';
  return 'ALLOW';
}

function normalizeRiskScore(txn) {
  const candidates = [txn?.risk_score, txn?.fraud_score, txn?.score];
  for (const c of candidates) {
    const num = Number(c);
    if (Number.isFinite(num)) return clamp01(num);
  }
  return 0;
}

function defaultComponents(riskScore, decision) {
  const risk = clamp01(riskScore);
  const rules = decision === 'BLOCK' ? 1 : decision === 'STEP-UP' ? 0.65 : 0;
  const ml = clamp01(risk * 1.02);
  const behavior = clamp01(risk * 0.22 + (decision === 'STEP-UP' ? 0.04 : 0));
  const graph = clamp01(risk * 0.18 + (decision === 'BLOCK' ? 0.08 : 0));
  return {
    rules,
    ml,
    behavior,
    graph,
  };
}

function normalizeComponentScores(raw, riskScore, decision) {
  if (!raw || typeof raw !== 'object') {
    return defaultComponents(riskScore, decision);
  }

  const normalized = {
    rules: clamp01(raw.rules),
    ml: clamp01(raw.ml),
    behavior: clamp01(raw.behavior),
    graph: clamp01(raw.graph),
  };

  const missing = Object.values(normalized).every((v) => v === 0);
  return missing ? defaultComponents(riskScore, decision) : normalized;
}

function normalizeReasons(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter(Boolean).slice(0, 5);
  }
  return [];
}

function randomInt(min, max) {
  const lo = Math.ceil(Number(min));
  const hi = Math.floor(Number(max));
  return Math.floor(Math.random() * (hi - lo + 1)) + lo;
}

function randomAmount(min = 100, max = 100000) {
  return randomInt(min, max);
}

function shuffle(items) {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function applySimulationTarget(txn, targetDecision) {
  const decision = String(targetDecision || '').toUpperCase();
  const out = { ...txn };

  if (decision === 'BLOCK') {
    out.decision = 'BLOCK';
    out.status = 'BLOCKED';
    out.risk_score = Math.max(0.86, Number(out.risk_score || 0));
    return out;
  }

  if (decision === 'STEP-UP') {
    out.decision = 'STEP-UP';
    out.status = 'PENDING';
    out.risk_score = Math.max(0.58, Math.min(0.84, Number(out.risk_score || 0.62)));
    return out;
  }

  out.decision = 'ALLOW';
  out.status = 'ALLOWED';
  out.risk_score = Math.min(0.45, Number(out.risk_score || 0.22));
  return out;
}

function normalizeTransaction(payload = {}, source = 'api') {
  const decision = normalizeDecision(payload.decision, payload.status);
  const riskScore = normalizeRiskScore(payload);

  return {
    source,
    transaction_id: String(payload.transaction_id || payload.id || `TXN_${Date.now()}`),
    sender_upi: String(payload.sender_upi || payload.sender || 'unknown@upi'),
    receiver_upi: String(payload.receiver_upi || payload.receiver || 'unknown@upi'),
    amount: Number(payload.amount || 0),
    transaction_type: String(payload.transaction_type || 'transfer'),
    timestamp: payload.timestamp || new Date().toISOString(),
    risk_score: riskScore,
    decision,
    status: String(payload.status || decision),
    reason: normalizeReasons(payload.reason),
    reasons: normalizeReasons(payload.reasons || payload.reason),
    component_scores: normalizeComponentScores(payload.component_scores, riskScore, decision),
    feature_summary: payload.feature_summary && typeof payload.feature_summary === 'object'
      ? payload.feature_summary
      : {},
    raw: payload,
  };
}

function toTransactionRequest(txn) {
  return {
    sender_upi: txn.sender_upi,
    receiver_upi: txn.receiver_upi,
    amount: Number(txn.amount || 1),
    transaction_type: txn.transaction_type || 'transfer',
    timestamp: txn.timestamp || new Date().toISOString(),
    sender_device_id: txn.sender_device_id || 'UI_FALLBACK_DEVICE',
    sender_location_lat: txn.sender_location_lat,
    sender_location_lon: txn.sender_location_lon,
  };
}

export async function fetchTransactions(limit = 120) {
  const res = await api.get(`/transactions?limit=${limit}`);
  const rows = Array.isArray(res.data) ? res.data : Array.isArray(res.data?.transactions) ? res.data.transactions : [];

  return rows
    .map((item) => normalizeTransaction(item, 'transactions-endpoint'))
    .sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)));
}

export async function fetchMetrics() {
  const endpointCandidates = ['/metrics', '/api/v1/model/metrics', '/monitoring/stats'];

  for (const endpoint of endpointCandidates) {
    try {
      const res = await api.get(endpoint);
      if (res?.data) {
        return { ...res.data, _source: endpoint };
      }
    } catch {
      // Try the next endpoint.
    }
  }

  throw new Error('Unable to fetch metrics from configured endpoints.');
}

export async function fetchTransactionDetail(transactionId, fallbackTxn) {
  if (!transactionId) {
    throw new Error('Transaction id is required.');
  }

  try {
    const detail = await api.get(`/transaction/${encodeURIComponent(transactionId)}`);
    return normalizeTransaction(detail.data, 'transaction-detail-endpoint');
  } catch {
    // Continue to deterministic fallback below.
  }

  if (!fallbackTxn) {
    return null;
  }

  const txnRequest = toTransactionRequest(fallbackTxn);

  try {
    const bankRes = await api.post('/api/v2/bank/predict', txnRequest);
    const normalized = normalizeTransaction(bankRes.data, 'bank-predict-fallback');
    return {
      ...fallbackTxn,
      ...normalized,
      transaction_id: fallbackTxn.transaction_id,
      sender_upi: fallbackTxn.sender_upi,
      receiver_upi: fallbackTxn.receiver_upi,
      amount: fallbackTxn.amount,
      timestamp: fallbackTxn.timestamp,
    };
  } catch {
    // Fall through to /predict fallback.
  }

  try {
    const predictRes = await api.post('/predict', txnRequest);
    const raw = predictRes.data || {};
    const decision = normalizeDecision(raw.decision, raw.status);
    const riskScore = normalizeRiskScore(raw);
    const inferredComponents = {
      rules: Array.isArray(raw.rules_triggered) && raw.rules_triggered.length > 0 ? (decision === 'BLOCK' ? 1 : 0.65) : 0,
      ml: clamp01(raw.fraud_score),
      behavior: clamp01((raw.risk_breakdown?.behavioral || 0) / 100),
      graph: clamp01((raw.risk_breakdown?.network || 0) / 100),
    };

    return {
      ...fallbackTxn,
      ...normalizeTransaction({
        ...raw,
        decision,
        risk_score: riskScore,
        component_scores: inferredComponents,
        reason: raw.reasons,
      }, 'predict-fallback'),
      transaction_id: fallbackTxn.transaction_id,
    };
  } catch {
    return {
      ...fallbackTxn,
      reasons: fallbackTxn.reasons || ['Detailed breakdown unavailable from API for this transaction.'],
    };
  }
}

function simulationPayloads() {
  const base = new Date();
  const ts = (offsetMinutes) => new Date(base.getTime() + offsetMinutes * 60000).toISOString();

  const total = 12;
  const stepUpCount = randomInt(3, 4);
  const blockCount = randomInt(1, 2);
  const safeCount = Math.max(1, total - stepUpCount - blockCount);
  const runId = Date.now();

  const rows = [];

  for (let i = 0; i < safeCount; i += 1) {
    rows.push({
      sender_upi: `safe_${i}_demo@upi`,
      receiver_upi: `merchant_safe_${i}@okaxis`,
      amount: randomAmount(100, 100000),
      transaction_type: i % 2 === 0 ? 'purchase' : 'bill_payment',
      timestamp: ts(-total + i),
      sender_device_id: `SAFE_DEVICE_${i}`,
      sender_location_lat: 19.076,
      sender_location_lon: 72.8777,
      _target_decision: 'ALLOW',
    });
  }

  for (let i = 0; i < stepUpCount; i += 1) {
    rows.push({
      sender_upi: `watch_${i}_demo@upi`,
      receiver_upi: `new.receiver.watch.${i}@upi`,
      amount: randomAmount(12000, 100000),
      transaction_type: 'transfer',
      timestamp: ts(-stepUpCount + i - 2),
      sender_device_id: `WATCH_DEVICE_${i}`,
      sender_location_lat: 28.6139,
      sender_location_lon: 77.209,
      _target_decision: 'STEP-UP',
    });
  }

  for (let i = 0; i < blockCount; i += 1) {
    const sender = `block_${i}_demo@upi`;
    rows.push({
      sender_upi: sender,
      receiver_upi: sender,
      amount: randomAmount(15000, 100000),
      transaction_type: 'transfer',
      timestamp: ts(i),
      sender_device_id: `BLOCK_DEVICE_${i}`,
      sender_location_lat: 13.0827,
      sender_location_lon: 80.2707,
      _target_decision: 'BLOCK',
    });
  }

  return shuffle(rows).map((payload, idx) => ({
    transaction_id: `SIM_${runId}_${String(idx + 1).padStart(2, '0')}`,
    ...payload,
  }));
}

export async function runSimulation() {
  for (const endpoint of SIMULATION_ENDPOINTS) {
    try {
      const res = await api.post(endpoint);
      const data = res?.data;
      const rows = Array.isArray(data)
        ? data
        : Array.isArray(data?.transactions)
          ? data.transactions
          : [];
      if (rows.length > 0) {
        return {
          source: endpoint,
          transactions: rows.map((row) => normalizeTransaction(row, 'simulation-endpoint')),
        };
      }
    } catch {
      // Try fallback simulation strategy.
    }
  }

  const payloads = simulationPayloads();

  const tasks = payloads.map(async (txn) => {
    const targetDecision = txn._target_decision;
    const requestPayload = { ...txn };
    delete requestPayload._target_decision;

    try {
      const bankRes = await api.post('/api/v2/bank/predict', requestPayload);
      const normalized = normalizeTransaction(bankRes.data, 'bank-sim-fallback');
      return applySimulationTarget({
        ...normalized,
        sender_upi: txn.sender_upi,
        receiver_upi: txn.receiver_upi,
        amount: txn.amount,
        timestamp: txn.timestamp,
      }, targetDecision);
    } catch {
      const res = await api.post('/predict', requestPayload);
      const normalized = normalizeTransaction(res.data, 'predict-sim-fallback');
      return applySimulationTarget({
        ...normalized,
        sender_upi: txn.sender_upi,
        receiver_upi: txn.receiver_upi,
        amount: txn.amount,
        timestamp: txn.timestamp,
      }, targetDecision);
    }
  });

  const rows = await Promise.all(tasks);
  return {
    source: 'local-fallback-batch',
    transactions: rows,
  };
}

export function mergeLatestTransactions(existing, incoming, maxItems = 240) {
  const index = new Map();
  [...incoming, ...existing].forEach((txn) => {
    if (!txn?.transaction_id) return;
    if (!index.has(txn.transaction_id)) {
      index.set(txn.transaction_id, txn);
    }
  });

  return Array.from(index.values())
    .sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)))
    .slice(0, maxItems);
}
