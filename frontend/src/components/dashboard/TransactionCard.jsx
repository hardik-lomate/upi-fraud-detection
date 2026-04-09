import React from 'react';
import { ChevronRight } from 'lucide-react';
import DecisionBadge from './DecisionBadge';
import RiskBadge from './RiskBadge';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

function borderClass(decision) {
  const d = String(decision || '').toUpperCase();
  if (d === 'BLOCK') return 'border-rose-500/70';
  if (d === 'STEP-UP' || d === 'VERIFY') return 'border-amber-400/70';
  return 'border-emerald-500/60';
}

function riskFillClass(riskScore) {
  const score = Number(riskScore || 0);
  if (score > 0.6) return 'bg-rose-400';
  if (score >= 0.3) return 'bg-amber-400';
  return 'bg-emerald-400';
}

function TransactionCard({ transaction, onClick, highlighted = false }) {
  if (!transaction) return null;

  const riskPct = Math.max(4, Math.min(100, Number(transaction.risk_score || 0) * 100));

  return (
    <button
      type="button"
      onClick={() => onClick?.(transaction)}
      className={`group w-full rounded-2xl border ${borderClass(transaction.decision)} ${highlighted ? 'ring-1 ring-cyan-300/60 bg-cyan-500/10' : 'bg-slate-900/70'} p-4 text-left transition hover:-translate-y-0.5 hover:bg-slate-900/90`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Transaction</p>
          <p className="font-mono text-sm text-slate-100">{transaction.transaction_id}</p>
          <p className="text-xs text-slate-400">{formatDateTime(transaction.timestamp)}</p>
          {highlighted ? (
            <span className="inline-flex items-center rounded-full border border-cyan-300/50 bg-cyan-500/15 px-2 py-0.5 text-[10px] font-semibold tracking-[0.12em] text-cyan-100">
              HIGHLIGHTED
            </span>
          ) : null}
        </div>
        <ChevronRight className="mt-1 h-4 w-4 text-slate-500 transition group-hover:text-slate-300" />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Amount</p>
          <p className="mt-1 text-lg font-semibold text-slate-100">{formatCurrency(transaction.amount)}</p>
        </div>
        <div className="flex items-end">
          <div className="space-y-1.5">
            <RiskBadge risk={transaction.risk_score} />
            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-800">
              <div className={`h-full ${riskFillClass(transaction.risk_score)}`} style={{ width: `${riskPct}%` }} />
            </div>
          </div>
        </div>
        <div className="flex items-end justify-start sm:justify-end">
          <DecisionBadge decision={transaction.decision} />
        </div>
      </div>
    </button>
  );
}

export default React.memo(TransactionCard);
