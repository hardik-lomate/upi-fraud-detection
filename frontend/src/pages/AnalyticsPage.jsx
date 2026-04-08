import React, { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const PIE_COLORS = ['#22C55E', '#F59E0B', '#F43F5E'];

function AnalyticsPage({ transactions, metrics }) {
  const riskHistogram = useMemo(() => {
    const bins = Array.from({ length: 10 }, (_, index) => ({
      range: `${(index * 0.1).toFixed(1)}-${((index + 1) * 0.1).toFixed(1)}`,
      count: 0,
    }));

    transactions.forEach((txn) => {
      const score = Math.max(0, Math.min(0.9999, Number(txn.risk_score || 0)));
      const bucket = Math.floor(score * 10);
      bins[bucket].count += 1;
    });

    return bins;
  }, [transactions]);

  const fraudPie = useMemo(() => {
    const allow = transactions.filter((txn) => txn.decision === 'ALLOW').length;
    const step = transactions.filter((txn) => txn.decision === 'STEP-UP').length;
    const block = transactions.filter((txn) => txn.decision === 'BLOCK').length;
    return [
      { name: 'Normal', value: allow },
      { name: 'Step-up', value: step },
      { name: 'Fraud Blocked', value: block },
    ];
  }, [transactions]);

  const timeline = useMemo(() => {
    const map = new Map();

    transactions.forEach((txn) => {
      const dt = new Date(txn.timestamp);
      if (Number.isNaN(dt.getTime())) return;
      const key = `${dt.getMonth() + 1}/${dt.getDate()} ${String(dt.getHours()).padStart(2, '0')}:00`;
      const entry = map.get(key) || { time: key, total: 0, fraud: 0, stepUp: 0 };
      entry.total += 1;
      if (txn.decision === 'BLOCK') entry.fraud += 1;
      if (txn.decision === 'STEP-UP') entry.stepUp += 1;
      map.set(key, entry);
    });

    return Array.from(map.values()).slice(-14);
  }, [transactions]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">Analytics</h1>
        <p className="mt-1 text-sm text-slate-400">
          Distribution, ratio, and timeline analytics for fraud detection quality and operational behavior.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-slate-700/70 bg-slate-900/75 p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Accuracy</p>
          <p className="mt-2 text-2xl font-semibold text-slate-100">
            {metrics?.accuracy ? `${(Number(metrics.accuracy) * 100).toFixed(1)}%` : 'N/A'}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/70 bg-slate-900/75 p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Precision</p>
          <p className="mt-2 text-2xl font-semibold text-slate-100">
            {metrics?.precision ? `${(Number(metrics.precision) * 100).toFixed(1)}%` : 'N/A'}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/70 bg-slate-900/75 p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Recall</p>
          <p className="mt-2 text-2xl font-semibold text-slate-100">
            {metrics?.recall ? `${(Number(metrics.recall) * 100).toFixed(1)}%` : 'N/A'}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/70 bg-slate-900/75 p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">F1 Score</p>
          <p className="mt-2 text-2xl font-semibold text-slate-100">
            {metrics?.f1_score ? `${(Number(metrics.f1_score) * 100).toFixed(1)}%` : 'N/A'}
          </p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/70 bg-slate-900/75 p-4">
          <h2 className="mb-3 text-sm font-semibold tracking-wide text-slate-100">Risk Score Histogram</h2>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={riskHistogram}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="range" tick={{ fill: '#CBD5E1', fontSize: 11 }} stroke="#94A3B8" />
                <YAxis allowDecimals={false} tick={{ fill: '#CBD5E1', fontSize: 11 }} stroke="#94A3B8" />
                <Tooltip contentStyle={{ background: '#0B1623', border: '1px solid rgba(84,106,132,0.8)', borderRadius: 10 }} />
                <Bar dataKey="count" fill="#22D3EE" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-700/70 bg-slate-900/75 p-4">
          <h2 className="mb-3 text-sm font-semibold tracking-wide text-slate-100">Fraud vs Normal Pie Chart</h2>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={fraudPie} dataKey="value" nameKey="name" outerRadius={95} innerRadius={56}>
                  {fraudPie.map((entry, index) => (
                    <Cell key={entry.name} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Legend />
                <Tooltip contentStyle={{ background: '#0B1623', border: '1px solid rgba(84,106,132,0.8)', borderRadius: 10 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-700/70 bg-slate-900/75 p-4">
        <h2 className="mb-3 text-sm font-semibold tracking-wide text-slate-100">Time-based Transaction Graph</h2>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={timeline}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
              <XAxis dataKey="time" tick={{ fill: '#CBD5E1', fontSize: 11 }} stroke="#94A3B8" />
              <YAxis allowDecimals={false} tick={{ fill: '#CBD5E1', fontSize: 11 }} stroke="#94A3B8" />
              <Tooltip contentStyle={{ background: '#0B1623', border: '1px solid rgba(84,106,132,0.8)', borderRadius: 10 }} />
              <Legend />
              <Line type="monotone" dataKey="total" stroke="#38BDF8" strokeWidth={2} dot={false} name="Total" />
              <Line type="monotone" dataKey="stepUp" stroke="#F59E0B" strokeWidth={2} dot={false} name="Step-up" />
              <Line type="monotone" dataKey="fraud" stroke="#F43F5E" strokeWidth={2} dot={false} name="Blocked Fraud" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export default React.memo(AnalyticsPage);
