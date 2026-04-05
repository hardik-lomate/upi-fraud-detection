import React, { useEffect, useState } from 'react';
import { fetchFeedbackStats, fetchFlaggedUsers, fetchMonitoringStats } from '../api/fraudApi';

function formatTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

export default function RiskMonitorPanel({ apiOnline }) {
  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState([]);
  const [monitor, setMonitor] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;

    async function load() {
      if (!apiOnline) {
        setRows([]);
        setError('API offline.');
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const [flaggedRes, monitorRes, feedbackRes] = await Promise.all([
          fetchFlaggedUsers(50),
          fetchMonitoringStats(),
          fetchFeedbackStats(),
        ]);
        if (!alive) return;
        setRows(Array.isArray(flaggedRes?.flagged_users) ? flaggedRes.flagged_users : []);
        setMonitor(monitorRes || null);
        setFeedback(feedbackRes || null);
      } catch {
        if (!alive) return;
        setError('Unable to load flagged users.');
        setRows([]);
        setMonitor(null);
        setFeedback(null);
      } finally {
        if (alive) setLoading(false);
      }
    }

    load();
    const id = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [apiOnline]);

  const summaryCards = [
    {
      title: 'Predictions Seen',
      value: monitor?.total ?? 0,
    },
    {
      title: 'Fraud Rate',
      value: `${monitor?.fraud_rate_pct ?? 0}%`,
    },
    {
      title: 'Mean Risk Score',
      value: monitor?.mean_score != null ? `${(Number(monitor.mean_score) * 100).toFixed(1)}%` : '0.0%',
    },
    {
      title: 'Feedback Records',
      value: feedback?.total_feedback ?? 0,
    },
  ];

  return (
    <section className="panel fade-in">
      <div className="flex items-center justify-between px-5 py-4">
        <div>
          <div className="panel-title">Risk Intelligence</div>
          <div className="mt-1 text-xs text-textSecondary">Live model health, analyst feedback loop, and flagged entities</div>
        </div>
        {loading ? <div className="font-mono text-xs text-textSecondary">REFRESHING</div> : null}
      </div>

      <div className="grid grid-cols-2 gap-3 border-t border-border/80 px-5 py-4 md:grid-cols-4">
        {summaryCards.map((card) => (
          <div key={card.title} className="rounded-xl border border-border/80 bg-bg/35 px-3 py-3">
            <div className="text-[11px] uppercase tracking-[0.12em] text-textSecondary">{card.title}</div>
            <div className="mt-1 font-mono text-xl font-semibold text-textPrimary">{card.value}</div>
          </div>
        ))}
      </div>

      {error ? (
        <div className="border-t border-border/80 px-5 py-4 text-sm text-textSecondary">{error}</div>
      ) : (
        <div className="overflow-auto border-t border-border/80">
          <table className="w-full text-left">
            <thead className="bg-bg/30 text-xs font-medium uppercase tracking-[0.1em] text-textSecondary">
              <tr className="border-b border-border/80">
                <th className="px-4 py-2">UPI</th>
                <th className="w-[120px] px-4 py-2">Fraud Count</th>
                <th className="w-[120px] px-4 py-2">Blocked</th>
                <th className="w-[220px] px-4 py-2">Last Seen</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-sm text-textSecondary">
                    No flagged users.
                  </td>
                </tr>
              ) : (
                rows.map((u) => (
                  <tr key={u.upi_id} className="hover:bg-bg/25">
                    <td className="px-4 py-2 font-medium text-textPrimary">{u.upi_id}</td>
                    <td className="px-4 py-2 font-mono text-textSecondary">{u.fraud_count ?? 0}</td>
                    <td className="px-4 py-2 font-mono text-textSecondary">{u.block_count ?? 0}</td>
                    <td className="px-4 py-2 text-xs text-textSecondary">{formatTime(u.last_fraud_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
