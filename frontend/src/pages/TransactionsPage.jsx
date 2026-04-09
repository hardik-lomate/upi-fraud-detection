import React, { useMemo, useState } from 'react';
import { Filter, Search } from 'lucide-react';
import TransactionCard from '../components/dashboard/TransactionCard';
import DecisionBadge from '../components/dashboard/DecisionBadge';
import RiskBadge from '../components/dashboard/RiskBadge';
import { formatCurrency, formatDateTime } from '../utils/formatters';

function decisionRowTone(decision, highlighted) {
  const normalized = String(decision || '').toUpperCase();
  const isStepUp = normalized === 'STEP-UP' || normalized === 'VERIFY';

  if (highlighted) {
    return 'ring-1 ring-cyan-300/60 bg-cyan-500/10 hover:bg-cyan-500/15';
  }
  if (normalized === 'BLOCK') {
    return 'bg-rose-500/10 hover:bg-rose-500/15';
  }
  if (isStepUp) {
    return 'bg-amber-500/10 hover:bg-amber-500/15';
  }
  return 'hover:bg-emerald-500/10';
}

function riskFillClass(riskScore) {
  const score = Number(riskScore || 0);
  if (score > 0.6) return 'bg-rose-400';
  if (score >= 0.3) return 'bg-amber-400';
  return 'bg-emerald-400';
}

function TransactionsPage({ transactions, loading, error, filter, onFilterChange, onSelectTransaction, highlightedTransactionId }) {
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();

    return transactions.filter((txn) => {
      const decisionOk = filter === 'ALL' ? true : txn.decision === filter;
      if (!decisionOk) return false;

      if (!needle) return true;

      return [txn.transaction_id, txn.sender_upi, txn.receiver_upi]
        .map((v) => String(v || '').toLowerCase())
        .some((v) => v.includes(needle));
    });
  }, [transactions, filter, search]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">Transaction Monitor</h1>
        <p className="mt-1 text-sm text-slate-400">
          Filter by decision, inspect risk, and open detailed intelligence for each transaction.
        </p>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{error}</div>
      ) : null}

      <div className="rounded-2xl border border-slate-700/70 bg-slate-900/75 p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <label className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-300">
            <Filter className="h-4 w-4 text-slate-400" />
            <select
              value={filter}
              onChange={(e) => onFilterChange(e.target.value)}
              className="w-full bg-transparent text-sm text-slate-100 focus:outline-none"
            >
              <option value="ALL">All Decisions</option>
              <option value="ALLOW">ALLOW</option>
              <option value="STEP-UP">STEP-UP</option>
              <option value="BLOCK">BLOCK</option>
            </select>
          </label>

          <label className="md:col-span-2 flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-300">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-transparent text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
              placeholder="Search by transaction id, sender, or receiver"
            />
          </label>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {filtered.slice(0, 24).map((txn) => (
          <TransactionCard
            key={txn.transaction_id}
            transaction={txn}
            highlighted={txn.transaction_id === highlightedTransactionId}
            onClick={onSelectTransaction}
          />
        ))}
      </div>

      <div className="rounded-2xl border border-slate-700/70 bg-slate-900/75 p-4">
        <h2 className="mb-4 text-sm font-semibold tracking-wide text-slate-100">Transaction List</h2>
        {loading ? (
          <p className="text-sm text-slate-400">Loading transactions...</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-700/70 text-xs uppercase tracking-[0.14em] text-slate-400">
                  <th className="px-3 py-2">Transaction</th>
                  <th className="px-3 py-2">Sender</th>
                  <th className="px-3 py-2">Amount</th>
                  <th className="px-3 py-2">Risk</th>
                  <th className="px-3 py-2">Decision</th>
                  <th className="px-3 py-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((txn) => {
                  const isHighlighted = txn.transaction_id === highlightedTransactionId;
                  const riskPct = Math.max(4, Math.min(100, Number(txn.risk_score || 0) * 100));
                  return (
                  <tr
                    key={txn.transaction_id}
                    className={`cursor-pointer border-b border-slate-800/70 text-slate-200 transition ${decisionRowTone(txn.decision, isHighlighted)}`}
                    onClick={() => onSelectTransaction(txn)}
                  >
                    <td className="px-3 py-3 font-mono text-xs text-slate-300">
                      <div className="space-y-1">
                        <div>{txn.transaction_id}</div>
                        {isHighlighted ? (
                          <span className="inline-flex items-center rounded-full border border-cyan-300/50 bg-cyan-500/15 px-2 py-0.5 text-[10px] font-semibold tracking-[0.12em] text-cyan-100">
                            HIGHLIGHTED
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-300">{txn.sender_upi}</td>
                    <td className="px-3 py-3">{formatCurrency(txn.amount)}</td>
                    <td className="px-3 py-3">
                      <div className="space-y-1.5">
                        <RiskBadge risk={txn.risk_score} />
                        <div className="h-1.5 w-28 overflow-hidden rounded-full bg-slate-800">
                          <div className={`h-full ${riskFillClass(txn.risk_score)}`} style={{ width: `${riskPct}%` }} />
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3"><DecisionBadge decision={txn.decision} /></td>
                    <td className="px-3 py-3 text-xs text-slate-400">{formatDateTime(txn.timestamp)}</td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default React.memo(TransactionsPage);
