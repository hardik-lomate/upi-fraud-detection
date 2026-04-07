import React from 'react';
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

export default function TransactionTable({ title, rows, selectedId, onSelect, loading }) {
  const list = Array.isArray(rows) ? rows : [];

  return (
    <section className="panel fade-in">
      <div className="flex items-center justify-between px-5 py-4">
        <div>
          <div className="panel-title">{title}</div>
          <div className="mt-1 text-xs text-textSecondary">Click any transaction to inspect model and rules evidence</div>
        </div>
        {loading ? <div className="font-mono text-xs text-textSecondary">SYNCING</div> : null}
      </div>

      <div className="overflow-auto border-t border-border/80">
        <table className="w-full table-fixed text-left">
          <thead className="bg-bg/35 text-xs font-medium uppercase tracking-[0.1em] text-textSecondary">
            <tr className="border-b border-border/80">
              <th className="w-[88px] px-4 py-2.5">Time</th>
              <th className="w-[160px] px-4 py-2.5">Sender</th>
              <th className="w-[160px] px-4 py-2.5">Receiver</th>
              <th className="w-[110px] px-4 py-2.5">Amount</th>
              <th className="w-[105px] px-4 py-2.5">Risk</th>
              <th className="w-[120px] px-4 py-2.5">Decision</th>
            </tr>
          </thead>
          <tbody className="text-sm">
            {list.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm text-textSecondary">
                  No transactions yet.
                </td>
              </tr>
            ) : (
              list.map((txn) => {
                const isSelected = txn.transaction_id === selectedId;
                return (
                  <tr
                    key={txn.transaction_id}
                    onClick={() => onSelect?.(txn.transaction_id)}
                    className={
                      isSelected
                        ? 'cursor-pointer border-l-2 border-primary bg-primary/10'
                        : 'cursor-pointer border-l-2 border-transparent hover:bg-bg/20'
                    }
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
