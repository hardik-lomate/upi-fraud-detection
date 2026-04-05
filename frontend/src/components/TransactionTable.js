import React, { useState, useMemo } from 'react';
import StatusBadge from './StatusBadge';

function formatTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatAmount(amount) {
  const n = Number(amount);
  if (!Number.isFinite(n)) return '—';
  return `₹${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatRisk(score) {
  const n = Number(score);
  if (!Number.isFinite(n)) return '—';
  return `${(n * 100).toFixed(1)}%`;
}

function riskBandClass(score) {
  const n = Number(score);
  if (!Number.isFinite(n)) return '';
  if (n >= 0.7) return 'risk-band-high';
  if (n >= 0.3) return 'risk-band-medium';
  return 'risk-band-low';
}

export default function TransactionTable({ title, rows, selectedId, onSelect, loading }) {
  const list = Array.isArray(rows) ? rows : [];
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState('desc');
  const [filter, setFilter] = useState('');

  const filtered = useMemo(() => {
    if (!filter) return list;
    const q = filter.toLowerCase();
    return list.filter((t) =>
      (t.sender_upi || '').toLowerCase().includes(q) ||
      (t.receiver_upi || '').toLowerCase().includes(q) ||
      (t.transaction_id || '').toLowerCase().includes(q) ||
      (t.decision || '').toLowerCase().includes(q)
    );
  }, [list, filter]);

  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    return [...filtered].sort((a, b) => {
      let va = a[sortKey], vb = b[sortKey];
      if (sortKey === 'amount' || sortKey === 'fraud_score') {
        va = Number(va) || 0;
        vb = Number(vb) || 0;
      }
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [filtered, sortKey, sortDir]);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return <span className="text-textMuted ml-1 opacity-0 group-hover:opacity-50">↕</span>;
    return <span className="text-accent ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <section className="panel fade-in">
      <div className="flex items-center justify-between px-5 py-4">
        <div>
          <div className="panel-title">{title}</div>
          <div className="mt-1 text-xs text-textSecondary">Click any row to inspect · {sorted.length} transactions</div>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-textMuted" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              type="text"
              placeholder="Filter..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="w-40 rounded-lg border border-border/60 bg-bg/40 pl-8 pr-3 py-1.5 text-xs text-textPrimary outline-none placeholder:text-textMuted focus:border-accent/40"
            />
          </div>
          {loading ? <div className="font-mono text-xs text-accent animate-pulse">SYNCING</div> : null}
        </div>
      </div>

      <div className="overflow-auto border-t border-border/60" style={{ maxHeight: '520px' }}>
        <table className="w-full table-fixed text-left">
          <thead className="bg-bg-card/50 text-xs font-medium uppercase tracking-[0.1em] text-textSecondary sticky top-0">
            <tr className="border-b border-border/60">
              <th className="w-[88px] px-4 py-2.5 cursor-pointer group" onClick={() => handleSort('timestamp')}>
                Time <SortIcon col="timestamp" />
              </th>
              <th className="w-[150px] px-4 py-2.5">Sender</th>
              <th className="w-[150px] px-4 py-2.5">Receiver</th>
              <th className="w-[105px] px-4 py-2.5 cursor-pointer group" onClick={() => handleSort('amount')}>
                Amount <SortIcon col="amount" />
              </th>
              <th className="w-[90px] px-4 py-2.5 cursor-pointer group" onClick={() => handleSort('fraud_score')}>
                Risk <SortIcon col="fraud_score" />
              </th>
              <th className="w-[110px] px-4 py-2.5">Decision</th>
            </tr>
          </thead>
          <tbody className="text-sm">
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm text-textSecondary">
                  {filter ? 'No matching transactions.' : 'No transactions yet.'}
                </td>
              </tr>
            ) : (
              sorted.map((txn) => {
                const isSelected = txn.transaction_id === selectedId;
                return (
                  <tr
                    key={txn.transaction_id}
                    onClick={() => onSelect?.(txn.transaction_id)}
                    className={`cursor-pointer transition-colors duration-150 ${riskBandClass(txn.fraud_score)} ${
                      isSelected
                        ? 'bg-accent/10 border-l-accent'
                        : 'hover:bg-bg-hover/40'
                    }`}
                  >
                    <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-textSecondary">
                      {formatTime(txn.timestamp)}
                    </td>
                    <td className="truncate px-4 py-2.5 text-xs text-textSecondary">{txn.sender_upi || '—'}</td>
                    <td className="truncate px-4 py-2.5 text-xs text-textSecondary">{txn.receiver_upi || '—'}</td>
                    <td className="whitespace-nowrap px-4 py-2.5 font-mono text-sm font-semibold text-textPrimary">
                      {formatAmount(txn.amount)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-textSecondary">
                      {formatRisk(txn.fraud_score)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5">
                      <StatusBadge txn={txn} />
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
