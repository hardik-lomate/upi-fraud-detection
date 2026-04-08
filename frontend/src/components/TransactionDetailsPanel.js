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
      <div className="shrink-0 text-xs text-textSecondary">{label}</div>
      <div className="min-w-0 truncate text-right text-sm font-medium text-textPrimary tabular-nums">{value}</div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="border-t border-border/80 px-5 py-4">
      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-textSecondary">{title}</div>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function getModelConsensus(txn) {
  const source = txn?.raw?.individual_scores || txn?.individual_scores || {};
  const values = Object.values(source)
    .map((v) => Number(v))
    .filter((v) => Number.isFinite(v));

  if (values.length < 2) {
    return { label: 'Limited', spread: null };
  }

  const spread = Math.max(...values) - Math.min(...values);
  if (spread <= 0.15) return { label: 'Strong', spread };
  if (spread <= 0.32) return { label: 'Moderate', spread };
  return { label: 'Weak', spread };
}

export default function TransactionDetailsPanel({ txn, onVerifyClick, onFeedback, feedbackBusy }) {
  const consensus = getModelConsensus(txn);

  return (
    <aside className="panel fade-in stagger-1">
      <div className="flex items-center justify-between gap-4 px-5 py-4">
        <div>
          <div className="panel-title">Transaction Intelligence</div>
          <div className="mt-1 font-mono text-[11px] text-textSecondary">{txn?.transaction_id || 'Select a transaction'}</div>
        </div>

        {txn && isVerify(txn) ? (
          <button
            type="button"
            onClick={onVerifyClick}
            className="rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-white transition hover:bg-primary/90"
          >
            Verify
          </button>
        ) : null}
      </div>

      {!txn ? (
        <div className="border-t border-border/80 px-5 py-8 text-sm text-textSecondary">
          Click a row in the table to load details.
        </div>
      ) : (
        <>
          <Section title="Basic Info">
            <div className="divide-y divide-border/80">
              <Row label="Time" value={formatTime(txn.timestamp)} />
              <Row label="Amount" value={formatAmount(txn.amount)} />
              <Row label="Receiver" value={txn.receiver_upi || '—'} />
              <Row label="Sender" value={txn.sender_upi || '—'} />
            </div>
          </Section>

          <Section title="Risk Analysis">
            <div className="divide-y divide-border/80">
              <Row label="Risk Score" value={formatRisk(txn.fraud_score)} />
              <Row label="Risk Level" value={txn.risk_level || '—'} />
              <Row
                label="Model Consensus"
                value={consensus.spread == null ? consensus.label : `${consensus.label} (${(consensus.spread * 100).toFixed(1)}%)`}
              />
            </div>
            <div className="mt-3 text-xs text-textSecondary">Risk factors</div>
            <ul className="mt-2 space-y-1 text-sm text-textPrimary">
              {(Array.isArray(txn.reasons) ? txn.reasons : []).slice(0, 5).map((r, idx) => (
                <li key={idx} className="rounded-md border border-border/70 bg-bg/40 px-2 py-1 text-sm">
                  {r}
                </li>
              ))}
              {(!txn.reasons || txn.reasons.length === 0) && (
                <li className="text-textSecondary">No explanations available.</li>
              )}
            </ul>
          </Section>

          <Section title="Decision">
            <div className="divide-y divide-border/80">
              <Row label="Decision" value={txn.decision || '—'} />
              <Row label="Status" value={<StatusBadge txn={txn} />} />
            </div>
            <div className="mt-3 text-sm text-textPrimary">{txn.message || '—'}</div>

            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <button
                type="button"
                disabled={feedbackBusy}
                onClick={() => onFeedback?.(txn, 'confirmed_fraud')}
                className="rounded-lg border border-danger/30 bg-danger/15 px-3 py-2 text-xs font-semibold text-danger transition hover:bg-danger/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Mark Confirmed Fraud
              </button>
              <button
                type="button"
                disabled={feedbackBusy}
                onClick={() => onFeedback?.(txn, 'false_positive')}
                className="rounded-lg border border-success/30 bg-success/15 px-3 py-2 text-xs font-semibold text-success transition hover:bg-success/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Mark False Positive
              </button>
            </div>
          </Section>
        </>
      )}
    </aside>
  );
}
