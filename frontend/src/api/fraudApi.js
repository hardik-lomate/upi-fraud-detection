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

export async function verifyBiometricWithMethod(transactionId, method = 'fingerprint') {
  const res = await api.post('/verify-biometric', {
    transaction_id: transactionId,
    method,
  });
  return res.data;
}

export async function payTransaction(payload) {
  const res = await api.post('/pay', payload);
  return res.data;
}

export async function preCheck(payload) {
  const res = await api.post('/api/v1/pre-check', payload);
  return res.data;
}

export async function confirmPayment(preCheckId, userOverride = true) {
  const res = await api.post(`/api/v1/pre-check/${preCheckId}/confirm`, {
    user_override: Boolean(userOverride),
  });
  return res.data;
}

export async function cancelPayment(preCheckId, reason = 'User cancelled payment') {
  const res = await api.post(`/api/v1/pre-check/${preCheckId}/cancel`, {
    reason,
  });
  return res.data;
}

export async function fetchMyTransactions(senderUpi, limit = 50, status = '') {
  const params = new URLSearchParams({
    sender_upi: senderUpi,
    limit: String(limit),
  });
  if (status) {
    params.set('status', status);
  }
  const res = await api.get(`/my/transactions?${params.toString()}`);
  return res.data;
}

export async function fetchMySecurityScore(upiId) {
  const params = new URLSearchParams({ upi_id: upiId });
  const res = await api.get(`/my/security-score?${params.toString()}`);
  return res.data;
}

export async function fetchReceiverInfo(upiId) {
  const params = new URLSearchParams({ upi_id: upiId });
  const res = await api.get(`/receiver/info?${params.toString()}`);
  return res.data;
}

export async function reportFraud(txnId, reporterUpi, description) {
  const res = await api.post('/my/report-fraud', {
    transaction_id: txnId,
    reporter_upi: reporterUpi,
    description,
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

export async function fetchModelMetrics() {
  const res = await api.get('/api/v1/model/metrics');
  return res.data;
}

export async function fetchConfusionMatrix() {
  const res = await api.get('/api/v1/model/confusion-matrix');
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

export async function fetchGraphSubgraph(upiId, depth = 2) {
  const params = new URLSearchParams({
    upi_id: upiId,
    depth: String(depth),
  });
  const res = await api.get(`/graph/subgraph?${params.toString()}`);
  return res.data;
}

export async function fetchGraphCommunities() {
  const res = await api.get('/graph/communities');
  return res.data;
}

export async function markMule(upiId, reason = '') {
  const res = await api.post('/graph/mark-mule', {
    upi_id: upiId,
    reason,
  });
  return res.data;
}
