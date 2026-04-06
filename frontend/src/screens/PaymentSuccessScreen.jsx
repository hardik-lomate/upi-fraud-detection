import React, { useMemo } from 'react';
import { formatIndianCurrency, formatTime } from '../utils/format';

export default function PaymentSuccessScreen({ result, onDone, onShare, onPayAgain }) {
  const confetti = useMemo(
    () =>
      Array.from({ length: 30 }, (_, index) => ({
        id: index,
        left: `${(index * 17) % 100}%`,
        delay: `${(index % 7) * 0.1}s`,
      })),
    []
  );

  return (
    <div className="result-screen success-screen">
      <div className="confetti-layer" aria-hidden="true">
        {confetti.map((piece) => (
          <span key={piece.id} className="confetti-piece" style={{ left: piece.left, animationDelay: piece.delay }} />
        ))}
      </div>

      <div className="draw-check" aria-hidden="true">
        <svg viewBox="0 0 72 72">
          <circle className="check-circle" cx="36" cy="36" r="32" />
          <path className="check-path" d="M21 37l10 10 20-22" />
        </svg>
      </div>

      <h2>Payment Sent</h2>
      <div className="result-amount">{formatIndianCurrency(result?.amount || 0)}</div>
      <p className="result-sub">Sent to {result?.receiver_name || result?.receiver_upi || 'recipient'}</p>

      <div className="txn-meta">
        <code>TXN {result?.transaction_id || '--'}</code>
        <small>Today, {formatTime(result?.timestamp)}</small>
      </div>

      <section className="security-note-card">
        ✓ Verified by ShieldPay — {result?.security_note || 'Known recipient and normal amount.'}
      </section>

      <div className="result-actions">
        <button type="button" className="primary-btn" onClick={onDone}>Done</button>
        <button type="button" className="ghost-btn" onClick={onShare}>Share Receipt</button>
        <button type="button" className="ghost-btn" onClick={onPayAgain}>Pay Again</button>
      </div>
    </div>
  );
}
