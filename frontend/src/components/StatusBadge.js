import React from 'react';

function normalizeStatus(txn) {
  const decision = String(txn?.decision || '').toUpperCase();
  const status = String(txn?.status || '').toUpperCase();

  if (decision === 'BLOCK' || status === 'BLOCKED') return 'BLOCK';
  if (decision === 'VERIFY' || status === 'PENDING_VERIFICATION' || status === 'PENDING') return 'VERIFY';
  if (decision === 'ALLOW' || status === 'ALLOWED' || status === 'VERIFIED') return 'ALLOW';
  return status || decision || 'UNKNOWN';
}

function stylesFor(label) {
  if (label === 'ALLOW') return 'border-success/30 bg-success/15 text-success';
  if (label === 'VERIFY') return 'border-warning/30 bg-warning/15 text-warning';
  if (label === 'BLOCK') return 'border-danger/30 bg-danger/15 text-danger';
  return 'border-border/80 bg-bg/40 text-textSecondary';
}

export default function StatusBadge({ txn }) {
  const label = normalizeStatus(txn);
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wide ${stylesFor(label)}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}

export function isVerify(txn) {
  const s = normalizeStatus(txn);
  return s === 'VERIFY';
}
