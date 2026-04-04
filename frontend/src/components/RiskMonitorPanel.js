import React, { useEffect, useState } from 'react';
import { fetchFlaggedUsers } from '../api/fraudApi';

function formatTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

export default function RiskMonitorPanel({ apiOnline }) {
  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState([]);
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
        const res = await fetchFlaggedUsers(50);
        if (!alive) return;
        setRows(Array.isArray(res?.flagged_users) ? res.flagged_users : []);
      } catch {
        if (!alive) return;
        setError('Unable to load flagged users.');
        setRows([]);
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

  return (
    <section className="rounded-xl border border-border bg-surface">
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <div className="text-sm font-semibold text-textPrimary">Flagged Users</div>
          <div className="mt-0.5 text-xs text-textSecondary">Accounts with fraud history</div>
        </div>
        {loading ? <div className="text-xs text-textSecondary">Refreshing…</div> : null}
      </div>

      {error ? (
        <div className="border-t border-border px-4 py-4 text-sm text-textSecondary">{error}</div>
      ) : (
        <div className="overflow-auto border-t border-border">
          <table className="w-full text-left">
            <thead className="bg-bg/30 text-xs font-medium text-textSecondary">
              <tr className="border-b border-border">
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
                    <td className="px-4 py-2 text-textSecondary tabular-nums">{u.fraud_count ?? 0}</td>
                    <td className="px-4 py-2 text-textSecondary tabular-nums">{u.block_count ?? 0}</td>
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
