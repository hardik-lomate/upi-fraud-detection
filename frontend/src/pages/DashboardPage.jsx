import React, { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { AlertTriangle, CheckCircle2, ShieldAlert } from 'lucide-react';
import StatCard from '../components/dashboard/StatCard';
import DecisionBadge from '../components/dashboard/DecisionBadge';
import RiskBadge from '../components/dashboard/RiskBadge';
import { formatCompactNumber, formatCurrency, formatDateTime } from '../utils/formatters';

const PIE_COLORS = ['#22C55E', '#F59E0B', '#F43F5E'];

function buildRiskBins(transactions) {
  const bins = [
    { label: '0.0-0.2', min: 0.0, max: 0.2, count: 0 },
    { label: '0.2-0.4', min: 0.2, max: 0.4, count: 0 },
    { label: '0.4-0.6', min: 0.4, max: 0.6, count: 0 },
    { label: '0.6-0.8', min: 0.6, max: 0.8, count: 0 },
    { label: '0.8-1.0', min: 0.8, max: 1.0001, count: 0 },
  ];

  transactions.forEach((txn) => {
    const score = Number(txn.risk_score || 0);
    const bucket = bins.find((bin) => score >= bin.min && score < bin.max);
    if (bucket) bucket.count += 1;
  });

  return bins.map((bin) => ({ range: bin.label, count: bin.count }));
}

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

function DashboardPage({ transactions, metrics, loading, error, onSelectTransaction, onRefresh, highlightedTransactionId }) {
  const summary = useMemo(() => {
    const total = transactions.length;
    const blocked = transactions.filter((txn) => txn.decision === 'BLOCK').length;
    const stepUp = transactions.filter((txn) => txn.decision === 'STEP-UP').length;
    const allowed = transactions.filter((txn) => txn.decision === 'ALLOW').length;
    const avgRisk = total > 0 ? transactions.reduce((acc, item) => acc + Number(item.risk_score || 0), 0) / total : 0;

    return {
      total,
      blocked,
      stepUp,
      allowed,
      avgRisk,
      fraudDetected: blocked + stepUp,
    };
  }, [transactions]);

  const riskBins = useMemo(() => buildRiskBins(transactions), [transactions]);

  const pieData = useMemo(
    () => [
      { name: 'Normal', value: summary.allowed },
      { name: 'Step-up', value: summary.stepUp },
      { name: 'Fraud Blocked', value: summary.blocked },
    ],
    [summary]
  );

  const recentRows = useMemo(() => {
    const base = transactions.slice(0, 8);
    if (!highlightedTransactionId) return base;

    const highlighted = transactions.find((txn) => txn.transaction_id === highlightedTransactionId);
    if (!highlighted) return base;

    return [highlighted, ...base.filter((txn) => txn.transaction_id !== highlightedTransactionId)].slice(0, 8);
  }, [transactions, highlightedTransactionId]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Fraud Intelligence Dashboard</h1>
          <p className="mt-1 text-sm text-slate-400">
            Real-time monitoring of transaction risk scoring and decision intelligence.
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-400"
        >
          Refresh Data
        </button>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{error}</div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard title="Total Transactions" value={formatCompactNumber(summary.total)} caption="Last synced window" tone="default" />
        <StatCard title="Fraud Detected" value={formatCompactNumber(summary.fraudDetected)} caption="BLOCK + STEP-UP" tone="danger" />
        <StatCard title="Normal Transactions" value={formatCompactNumber(summary.allowed)} caption="Directly approved" tone="success" />
        <StatCard
          title="Average Risk"
          value={`${(summary.avgRisk * 100).toFixed(1)}%`}
          caption={metrics?.f1_score ? `Model F1: ${(Number(metrics.f1_score) * 100).toFixed(1)}%` : 'Live risk average'}
          tone="warning"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/70 bg-slate-900/75 p-4 xl:col-span-2">
          <div className="mb-4 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-300" />
            <h2 className="text-sm font-semibold tracking-wide text-slate-100">Risk Distribution Chart</h2>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={riskBins}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="range" stroke="#94A3B8" tick={{ fill: '#CBD5E1', fontSize: 12 }} />
                <YAxis stroke="#94A3B8" tick={{ fill: '#CBD5E1', fontSize: 12 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: '#0B1623', border: '1px solid rgba(84,106,132,0.8)', borderRadius: 10 }}
                />
                <Bar dataKey="count" radius={[8, 8, 0, 0]} fill="#38BDF8" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-700/70 bg-slate-900/75 p-4">
          <div className="mb-4 flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-rose-300" />
            <h2 className="text-sm font-semibold tracking-wide text-slate-100">Fraud vs Normal Summary</h2>
          </div>
          <div className="h-52 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={56} outerRadius={80} paddingAngle={2}>
                  {pieData.map((entry, index) => (
                    <Cell key={entry.name} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#0B1623', border: '1px solid rgba(84,106,132,0.8)', borderRadius: 10 }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 space-y-2 text-xs text-slate-300">
            {pieData.map((entry, index) => (
              <div key={entry.name} className="flex items-center justify-between">
                <span className="inline-flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: PIE_COLORS[index % PIE_COLORS.length] }} />
                  {entry.name}
                </span>
                <span>{entry.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-700/70 bg-slate-900/75 p-4">
        <div className="mb-4 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-300" />
          <h2 className="text-sm font-semibold tracking-wide text-slate-100">Recent Transactions</h2>
        </div>

        {loading ? (
          <p className="text-sm text-slate-400">Loading transactions...</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-700/70 text-xs uppercase tracking-[0.14em] text-slate-400">
                  <th className="px-3 py-2">Transaction</th>
                  <th className="px-3 py-2">Amount</th>
                  <th className="px-3 py-2">Risk</th>
                  <th className="px-3 py-2">Decision</th>
                  <th className="px-3 py-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {recentRows.map((txn) => {
                  const isHighlighted = txn.transaction_id === highlightedTransactionId;
                  const riskPct = Math.max(4, Math.min(100, Number(txn.risk_score || 0) * 100));
                  return (
                  <tr
                    key={txn.transaction_id}
                    className={`cursor-pointer border-b border-slate-800/80 text-slate-200 transition ${decisionRowTone(txn.decision, isHighlighted)}`}
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

export default React.memo(DashboardPage);
