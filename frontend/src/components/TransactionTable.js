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
    <section className="rounded-xl border border-border bg-surface">
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <div className="text-sm font-semibold text-textPrimary">{title}</div>
          <div className="mt-0.5 text-xs text-textSecondary">Click a row to view details</div>
        </div>
        {loading ? <div className="text-xs text-textSecondary">Updating…</div> : null}
      </div>

      <div className="overflow-auto border-t border-border">
        <table className="w-full table-fixed text-left">
          <thead className="bg-bg/30 text-xs font-medium text-textSecondary">
            <tr className="border-b border-border">
              <th className="w-[92px] px-4 py-2">Time</th>
              <th className="w-[110px] px-4 py-2">Amount</th>
              <th className="px-4 py-2">Receiver</th>
              <th className="w-[110px] px-4 py-2">Risk Score</th>
              <th className="w-[110px] px-4 py-2">Status</th>
            </tr>
          </thead>
          <tbody className="text-sm">
            {list.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-sm text-textSecondary">
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
                        ? 'cursor-pointer bg-bg/35'
                        : 'cursor-pointer hover:bg-bg/25'
                    }
                  >
                    <td className="whitespace-nowrap px-4 py-2 text-xs text-textSecondary">
                      {formatTime(txn.timestamp)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 font-medium text-textPrimary tabular-nums">
                      {formatAmount(txn.amount)}
                    </td>
                    <td className="truncate px-4 py-2 text-textPrimary">
                      {txn.receiver_upi || '—'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-textSecondary tabular-nums">
                      {formatRisk(txn.fraud_score)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2">
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
