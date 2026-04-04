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
