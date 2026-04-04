import React from 'react';
import StatusBadge, { isVerify } from './StatusBadge';

function formatAmount(amount) {
  const n = Number(amount);
  if (!Number.isFinite(n)) return '—';
  return `₹${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

function formatRisk(score) {
  const n = Number(score);
  if (!Number.isFinite(n)) return '—';
  return `${(n * 100).toFixed(1)}%`;
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <div className="text-xs text-textSecondary">{label}</div>
      <div className="text-sm font-medium text-textPrimary tabular-nums">{value}</div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="border-t border-border px-4 py-4">
      <div className="text-xs font-semibold text-textPrimary">{title}</div>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export default function TransactionDetailsPanel({ txn, onVerifyClick }) {
  return (
    <aside className="rounded-xl border border-border bg-surface">
      <div className="flex items-start justify-between gap-4 px-4 py-4">
        <div>
          <div className="text-sm font-semibold text-textPrimary">Transaction Details</div>
          <div className="mt-1 text-xs text-textSecondary">{txn?.transaction_id || 'Select a transaction'}</div>
        </div>

        {txn && isVerify(txn) ? (
          <button
            type="button"
            onClick={onVerifyClick}
            className="rounded-md bg-primary px-3 py-2 text-xs font-semibold text-white hover:bg-primary/90"
          >
            Verify
          </button>
        ) : null}
      </div>

      {!txn ? (
        <div className="border-t border-border px-4 py-6 text-sm text-textSecondary">
          Click a row in the table to load details.
        </div>
      ) : (
        <>
          <Section title="Basic Info">
            <div className="divide-y divide-border">
              <Row label="Time" value={formatTime(txn.timestamp)} />
              <Row label="Amount" value={formatAmount(txn.amount)} />
              <Row label="Receiver" value={txn.receiver_upi || '—'} />
              <Row label="Sender" value={txn.sender_upi || '—'} />
            </div>
          </Section>

          <Section title="Risk Analysis">
            <div className="divide-y divide-border">
              <Row label="Risk Score" value={formatRisk(txn.fraud_score)} />
              <Row label="Risk Level" value={txn.risk_level || '—'} />
            </div>
            <div className="mt-3 text-xs text-textSecondary">Top factors</div>
            <ul className="mt-2 space-y-1 text-sm text-textPrimary">
              {(Array.isArray(txn.reasons) ? txn.reasons : []).slice(0, 5).map((r, idx) => (
                <li key={idx}>{r}</li>
              ))}
              {(!txn.reasons || txn.reasons.length === 0) && (
                <li className="text-textSecondary">No explanations available.</li>
              )}
            </ul>
          </Section>

          <Section title="Decision">
            <div className="divide-y divide-border">
              <Row label="Decision" value={txn.decision || '—'} />
              <Row label="Status" value={<StatusBadge txn={txn} />} />
            </div>
            <div className="mt-3 text-sm text-textPrimary">{txn.message || '—'}</div>
          </Section>
        </>
      )}
    </aside>
  );
}
