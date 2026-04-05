import { api } from './client';

export async function fetchTransactions(limit = 50) {
  const res = await api.get(`/transactions?limit=${limit}`);
  return res.data;
}

export async function predictTransaction(txn) {
  const res = await api.post('/predict', txn);
  return res.data;
}

export async function verifyBiometric(transactionId) {
  const res = await api.post('/verify-biometric', {
    transaction_id: transactionId,
    method: 'fingerprint',
  });
  return res.data;
}

export async function fetchFlaggedUsers(limit = 50) {
  const res = await api.get(`/fraud-history/flagged?limit=${limit}`);
  return res.data;
}

export async function fetchMonitoringStats() {
  const res = await api.get('/monitoring/stats');
  return res.data;
}

export async function submitFeedback(transactionId, analystVerdict, analystNotes = '') {
  const res = await api.post('/feedback', {
    transaction_id: transactionId,
    analyst_verdict: analystVerdict,
    analyst_notes: analystNotes,
  });
  return res.data;
}

export async function fetchFeedbackStats() {
  const res = await api.get('/feedback/stats');
  return res.data;
}

// ─── Cases CRUD ────────────────────────────────

export async function fetchCases(status = null, limit = 50) {
  const q = status ? `?status=${status}&limit=${limit}` : `?limit=${limit}`;
  const res = await api.get(`/cases${q}`);
  return res.data;
}

export async function createCase(txnId, assignedTo, notes) {
  const res = await api.post('/cases', {
    txn_id: txnId,
    assigned_to: assignedTo,
    notes,
  });
  return res.data;
}

export async function updateCase(caseId, updates) {
  const res = await api.patch(`/cases/${caseId}`, updates);
  return res.data;
}

// ─── Graph Investigation ───────────────────────

export async function fetchGraphSubgraph(upiId, depth = 2) {
  const res = await api.get(`/graph/subgraph?upi_id=${encodeURIComponent(upiId)}&depth=${depth}`);
  return res.data;
}

export async function fetchGraphCommunities() {
  const res = await api.get('/graph/communities');
  return res.data;
}

export async function markMule(upiId, reason) {
  const res = await api.post('/graph/mark-mule', { upi_id: upiId, reason });
  return res.data;
}

export async function fetchSuspiciousPaths(source, target) {
  const res = await api.get(`/graph/suspicious-paths?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}`);
  return res.data;
}

// ─── NLG / Explain ─────────────────────────────

export async function fetchNlgSummary(txnId) {
  const res = await api.post('/explain/summary', { transaction_id: txnId });
  return res.data;
}

// ─── Reports ───────────────────────────────────

export async function fetchRbiReport() {
  const res = await api.get('/reports/rbi');
  return res.data;
}

export async function fetchReportSummary() {
  const res = await api.get('/reports/summary');
  return res.data;
}

// ─── Monitoring ────────────────────────────────

export async function fetchDriftReport() {
  const res = await api.get('/monitoring/drift');
  return res.data;
}

export async function fetchLatencyStats() {
  const res = await api.get('/monitoring/latency');
  return res.data;
}

export async function fetchGraphStats() {
  const res = await api.get('/monitoring/graph');
  return res.data;
}

// ─── Model Info ────────────────────────────────

export async function fetchModelInfo() {
  const res = await api.get('/model/info');
  return res.data;
}
