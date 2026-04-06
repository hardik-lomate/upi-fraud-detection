import React, { useMemo, useState } from 'react';
import TransactionItem from '../components/user/TransactionItem';
import SecurityReasonCard from '../components/user/SecurityReasonCard';
import FraudPatternCard from '../components/user/FraudPatternCard';
import { formatDateLabel, formatIndianCurrency, formatTime } from '../utils/format';

const FILTERS = [
  { id: 'ALL', label: 'All' },
  { id: 'SENT', label: 'Sent' },
  { id: 'RECEIVED', label: 'Received' },
  { id: 'BLOCKED', label: 'Blocked' },
  { id: 'VERIFIED', label: 'Verified' },
];

function applyFilter(rows, filterId) {
  if (filterId === 'BLOCKED') return rows.filter((row) => row.status === 'BLOCKED');
  if (filterId === 'VERIFIED') return rows.filter((row) => row.status === 'VERIFIED');
  if (filterId === 'SENT') return rows.filter((row) => row.status !== 'BLOCKED');
  if (filterId === 'RECEIVED') return [];
  return rows;
}

export default function HistoryScreen({ transactions, summary, onReportFraud }) {
  const [filter, setFilter] = useState('ALL');
  const [selected, setSelected] = useState(null);

  const filtered = useMemo(() => applyFilter(transactions, filter), [transactions, filter]);

  const grouped = useMemo(() => {
    return filtered.reduce((acc, txn) => {
      const key = formatDateLabel(txn.timestamp);
      if (!acc[key]) acc[key] = [];
      acc[key].push(txn);
      return acc;
    }, {});
  }, [filtered]);

  return (
    <div className="screen-stack history-screen">
      <header className="screen-header">
        <h2>Transaction History</h2>
      </header>

      <section className="security-summary-card">
        <strong>{summary?.protectedCount || 0} payments protected this month</strong>
        <small>
          ₹{summary?.protectedAmount || 0} secured · {summary?.blockedCount || 0} attempts blocked
        </small>
      </section>

      <div className="filter-row">
        {FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`filter-chip ${filter === item.id ? 'active' : ''}`}
            onClick={() => setFilter(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="grouped-list">
        {Object.keys(grouped).length === 0 ? (
          <p className="empty-copy">No transactions in this filter.</p>
        ) : null}

        {Object.entries(grouped).map(([group, rows]) => (
          <section key={group} className="history-group">
            <h3>{group}</h3>
            {rows.map((txn) => (
              <TransactionItem
                key={txn.transaction_id}
                txn={txn}
                selected={selected?.transaction_id === txn.transaction_id}
                onClick={setSelected}
              />
            ))}
          </section>
        ))}
      </div>

      {selected ? (
        <section className="detail-sheet">
          <div className="sheet-handle" />
          <div className="section-title-row">
            <h3>Transaction details</h3>
            <button type="button" className="ghost-btn" onClick={() => setSelected(null)}>Close</button>
          </div>

          <div className="detail-grid">
            <div>
              <small>Amount</small>
              <strong>{formatIndianCurrency(selected.amount)}</strong>
            </div>
            <div>
              <small>Receiver</small>
              <strong>{selected.receiver_name || selected.receiver_upi}</strong>
            </div>
            <div>
              <small>Time</small>
              <strong>{formatTime(selected.timestamp)}</strong>
            </div>
            <div>
              <small>Receipt</small>
              <code>{selected.receipt_id}</code>
            </div>
          </div>

          <SecurityReasonCard
            decision={selected.decision}
            title="ShieldPay verdict"
            reason={selected.user_reason || selected.user_message}
          />

          <FraudPatternCard pattern={selected.fraud_pattern} description={selected.user_reason} />

          <div className="detail-actions">
            <button type="button" className="ghost-btn" onClick={() => onReportFraud(selected)}>
              Report fraud
            </button>
            <button type="button" className="ghost-btn">This was not me</button>
            <button type="button" className="ghost-btn">Share receipt</button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
