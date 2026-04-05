import React from 'react';
import StatusBadge, { isVerify } from './StatusBadge';
import FraudScoreGauge from './FraudScoreGauge';
import ModelConsensus from './ModelConsensus';

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

function Row({ label, value, mono = false }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <div className="shrink-0 text-xs text-textSecondary">{label}</div>
      <div className={`min-w-0 truncate text-right text-sm font-medium text-textPrimary tabular-nums ${mono ? 'font-mono' : ''}`}>{value}</div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="border-t border-border/60 px-5 py-4">
      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-textSecondary">{title}</div>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function RiskBreakdownBars({ breakdown }) {
  if (!breakdown) return null;
  const bars = [
    { label: 'Behavioral', value: breakdown.behavioral, color: '#6C47FF' },
    { label: 'Temporal', value: breakdown.temporal, color: '#378ADD' },
    { label: 'Network', value: breakdown.network, color: '#EF9F27' },
    { label: 'Device', value: breakdown.device, color: '#E24B4A' },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 mt-3">
      {bars.map((bar) => (
        <div key={bar.label}>
          <div className="flex items-center justify-between text-[11px] mb-1">
            <span className="text-textSecondary">{bar.label}</span>
            <span className="font-mono text-textPrimary">{(bar.value || 0).toFixed(0)}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-bg-elevated/60 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${Math.min(bar.value || 0, 100)}%`, backgroundColor: bar.color }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function TransactionDetailsPanel({ txn, onVerifyClick, onFeedback, feedbackBusy, onEscalate }) {
  const scores = txn?.raw?.individual_scores || txn?.individual_scores || {};
  const breakdown = txn?.raw?.risk_breakdown || txn?.risk_breakdown || null;
  const npciCategory = txn?.raw?.npci_category || txn?.npci_category || null;

  return (
    <aside className="panel fade-in stagger-1">
      <div className="flex items-center justify-between gap-4 px-5 py-4">
        <div>
          <div className="panel-title">Transaction Intelligence</div>
          <div className="flex items-center gap-2 mt-1">
            <span className="font-mono text-[11px] text-textSecondary">{txn?.transaction_id || 'Select a transaction'}</span>
            {txn?.transaction_id && (
              <button
                type="button"
                onClick={() => navigator.clipboard?.writeText(txn.transaction_id)}
                className="text-textMuted hover:text-accent transition"
                title="Copy ID"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                </svg>
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {txn && isVerify(txn) ? (
            <button
              type="button"
              onClick={onVerifyClick}
              className="rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-white transition hover:bg-accent-light"
            >
              Verify
            </button>
          ) : null}
        </div>
      </div>

      {!txn ? (
        <div className="border-t border-border/60 px-5 py-8 text-sm text-textSecondary">
          Click a row in the table to load details.
        </div>
      ) : (
        <>
          {/* Fraud Score Gauge */}
          <div className="border-t border-border/60 px-5 py-4 flex justify-center">
            <FraudScoreGauge score={Number(txn.fraud_score) || 0} size={150} />
          </div>

          {/* Model Consensus */}
          <Section title="Model Scores">
            <ModelConsensus
              individualScores={scores}
              ensembleScore={Number(txn.fraud_score) || 0}
            />
          </Section>

          {/* Risk Breakdown */}
          <Section title="Risk Analysis">
            <RiskBreakdownBars breakdown={breakdown} />
            {npciCategory && (
              <div className="mt-3 flex items-center gap-2">
                <span className="text-[10px] font-semibold tracking-wider text-textMuted uppercase">NPCI</span>
                <span className="text-xs text-accent font-medium">{npciCategory}</span>
              </div>
            )}
            <div className="mt-3 text-xs text-textSecondary">Risk factors</div>
            <ul className="mt-2 space-y-1.5">
              {(Array.isArray(txn.reasons) ? txn.reasons : []).slice(0, 5).map((r, idx) => (
                <li key={idx} className="rounded-lg border border-border/50 bg-bg-card/50 px-3 py-1.5 text-xs text-textPrimary flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-warn shrink-0" />
                  {r}
                </li>
              ))}
              {(!txn.reasons || txn.reasons.length === 0) && (
                <li className="text-textSecondary text-xs">No explanations available.</li>
              )}
            </ul>
          </Section>

          {/* Basic Info */}
          <Section title="Transaction Info">
            <div className="divide-y divide-border/40">
              <Row label="Time" value={formatTime(txn.timestamp)} />
              <Row label="Amount" value={formatAmount(txn.amount)} mono />
              <Row label="Sender" value={txn.sender_upi || '—'} />
              <Row label="Receiver" value={txn.receiver_upi || '—'} />
            </div>
          </Section>

          {/* Decision + Actions */}
          <Section title="Decision">
            <div className="divide-y divide-border/40">
              <Row label="Decision" value={txn.decision || '—'} />
              <Row label="Status" value={<StatusBadge txn={txn} />} />
            </div>
            <div className="mt-3 text-sm text-textPrimary">{txn.message || '—'}</div>

            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <button
                type="button"
                disabled={feedbackBusy}
                onClick={() => onFeedback?.(txn, 'confirmed_fraud')}
                className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs font-semibold text-danger transition hover:bg-danger/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Confirm Fraud
              </button>
              <button
                type="button"
                disabled={feedbackBusy}
                onClick={() => onFeedback?.(txn, 'false_positive')}
                className="rounded-lg border border-safe/30 bg-safe/10 px-3 py-2 text-xs font-semibold text-safe transition hover:bg-safe/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                False Positive
              </button>
            </div>

            {/* Escalate to Case */}
            <button
              type="button"
              onClick={() => onEscalate?.(txn)}
              className="mt-2 w-full rounded-lg border border-accent/30 bg-accent/10 px-3 py-2 text-xs font-semibold text-accent transition hover:bg-accent/20"
            >
              Escalate to Case
            </button>
          </Section>
        </>
      )}
    </aside>
  );
}
