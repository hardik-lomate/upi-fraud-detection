import React from 'react';
import FraudScoreGauge from './FraudScoreGauge';

export default function VerdictCard({ transaction, onExport }) {
  if (!transaction) return null;

  const score = Number(transaction.fraud_score) || 0;
  const decision = transaction.decision || 'ALLOW';
  const reasons = Array.isArray(transaction.reasons) ? transaction.reasons.slice(0, 3) : [];
  const npci = transaction.raw?.npci_category || transaction.npci_category || '';

  const decisionColor = decision === 'BLOCK' ? '#E24B4A' : decision === 'VERIFY' ? '#EF9F27' : '#00C9A7';

  const handleExport = () => {
    // Export as image via Canvas
    const el = document.getElementById('verdict-card-content');
    if (!el) return;
    // Simplified: copy text summary
    const text = [
      `UPI Fraud Verdict: ${transaction.transaction_id}`,
      `Score: ${(score * 100).toFixed(1)}%`,
      `Decision: ${decision}`,
      `Amount: ₹${Number(transaction.amount || 0).toLocaleString()}`,
      `Sender: ${transaction.sender_upi}`,
      `Receiver: ${transaction.receiver_upi}`,
      ...reasons.map((r, i) => `Risk ${i + 1}: ${r}`),
    ].join('\n');
    navigator.clipboard?.writeText(text);
    onExport?.('copied');
  };

  return (
    <div id="verdict-card-content" className="panel fade-in overflow-hidden">
      {/* Header gradient */}
      <div
        className="px-5 py-4"
        style={{
          background: `linear-gradient(135deg, ${decisionColor}15 0%, transparent 60%)`,
          borderBottom: `1px solid ${decisionColor}25`,
        }}
      >
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[10px] font-bold tracking-[0.2em] uppercase" style={{ color: decisionColor }}>
              Fraud Assessment Verdict
            </div>
            <div className="font-mono text-[11px] text-textSecondary mt-1">{transaction.transaction_id}</div>
          </div>
          <button
            type="button"
            onClick={handleExport}
            className="rounded-lg border border-border/50 bg-bg-card/50 px-3 py-1.5 text-[10px] text-textSecondary hover:text-accent hover:border-accent/30 transition flex items-center gap-1.5"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            Export
          </button>
        </div>
      </div>

      {/* Score + Decision */}
      <div className="px-5 py-4 flex items-center gap-6">
        <FraudScoreGauge score={score} size={100} />
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2">
            <span
              className="px-2.5 py-1 rounded-full text-xs font-bold"
              style={{ color: decisionColor, backgroundColor: `${decisionColor}15`, border: `1px solid ${decisionColor}30` }}
            >
              {decision}
            </span>
            {npci && <span className="text-[10px] text-textMuted">{npci}</span>}
          </div>
          <div className="text-xs text-textSecondary">
            <span className="font-mono text-textPrimary">₹{Number(transaction.amount || 0).toLocaleString()}</span>
            {' · '}
            {transaction.sender_upi} → {transaction.receiver_upi}
          </div>
        </div>
      </div>

      {/* Risk Reasons */}
      {reasons.length > 0 && (
        <div className="px-5 pb-4 space-y-1.5">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-textMuted">Top Risk Factors</div>
          {reasons.map((r, i) => {
            const impact = 1 - i * 0.25;
            return (
              <div key={i} className="flex items-center gap-3">
                <div className="flex-1">
                  <div className="text-xs text-textPrimary">{r}</div>
                  <div className="mt-1 h-1 rounded-full bg-bg-elevated/60 overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${impact * 100}%`, backgroundColor: decisionColor, opacity: 0.7 }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Timestamp */}
      <div className="px-5 py-2 border-t border-border/40 flex items-center justify-between">
        <span className="text-[10px] text-textMuted font-mono">
          {transaction.timestamp ? new Date(transaction.timestamp).toLocaleString() : '—'}
        </span>
        <span className="text-[10px] text-textMuted">v4.0.0 Dual-model Ensemble</span>
      </div>
    </div>
  );
}
