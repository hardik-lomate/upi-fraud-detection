import React from 'react';
import { formatIndianCurrency, formatTime } from '../../utils/format';

const STATUS_MAP = {
  COMPLETED: { label: 'Sent', className: 'neutral', icon: '✓' },
  VERIFIED: { label: 'Verified', className: 'safe', icon: '🛡' },
  BLOCKED: { label: 'Blocked', className: 'danger', icon: '✕' },
  PENDING_VERIFICATION: { label: 'Pending', className: 'warn', icon: '⏳' },
};

function initials(name = 'R') {
  const parts = String(name).split(' ').filter(Boolean);
  if (parts.length === 0) return 'R';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

export default function TransactionItem({ txn, onClick, selected = false }) {
  const status = STATUS_MAP[txn.status] || STATUS_MAP.COMPLETED;

  return (
    <button
      type="button"
      className={`txn-item ${selected ? 'selected' : ''}`}
      onClick={() => onClick?.(txn)}
    >
      <div className="txn-left">
        <span className="txn-avatar">{initials(txn.receiver_name || txn.receiver_upi)}</span>
        <div className="txn-identities">
          <strong>{txn.receiver_name || 'Recipient'}</strong>
          <small>{txn.receiver_upi}</small>
        </div>
      </div>
      <div className="txn-right">
        <strong className={`txn-amount ${txn.status === 'BLOCKED' ? 'blocked' : 'sent'}`}>
          {txn.status === 'BLOCKED' ? formatIndianCurrency(txn.amount) : `-${formatIndianCurrency(txn.amount)}`}
        </strong>
        <span className={`txn-status ${status.className}`}>
          {status.icon} {status.label}
        </span>
        <small>{formatTime(txn.timestamp)}</small>
      </div>
    </button>
  );
}
