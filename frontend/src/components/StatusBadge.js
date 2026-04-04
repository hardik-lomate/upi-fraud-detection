import React from 'react';

function normalizeStatus(txn) {
  const decision = String(txn?.decision || '').toUpperCase();
  const status = String(txn?.status || '').toUpperCase();

  if (decision === 'BLOCK' || status === 'BLOCKED') return 'BLOCK';
  if (decision === 'REQUIRE_BIOMETRIC' || status === 'PENDING_VERIFICATION') return 'VERIFY';
  if (decision === 'ALLOW' || status === 'ALLOWED' || status === 'VERIFIED') return 'ALLOW';
  return status || decision || 'UNKNOWN';
}

function stylesFor(label) {
  if (label === 'ALLOW') return 'border-success/20 bg-success/10 text-success';
  if (label === 'VERIFY') return 'border-warning/20 bg-warning/10 text-warning';
  if (label === 'BLOCK') return 'border-danger/20 bg-danger/10 text-danger';
  return 'border-border bg-bg/40 text-textSecondary';
}

export default function StatusBadge({ txn }) {
  const label = normalizeStatus(txn);
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${stylesFor(label)}`}>
      {label}
    </span>
  );
}

export function isVerify(txn) {
  const s = normalizeStatus(txn);
  return s === 'VERIFY';
}
