import React, { useState } from 'react';
import SecurityReasonCard from '../components/user/SecurityReasonCard';
import FraudPatternCard from '../components/user/FraudPatternCard';

export default function PaymentBlockedScreen({ result, onHome, onAppeal, onReport }) {
  const [showAppeal, setShowAppeal] = useState(false);
  const [reason, setReason] = useState('');
  const [phone, setPhone] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const topReasons = (result?.reasons || result?.user_warning?.reasons_display || []).slice(0, 3);
  const receiverUpi = result?.receiver_upi || result?.raw?.receiver_upi || 'unknown@upi';
  const receiverFlagCount = Number(result?.receiver_fraud_flag_count || result?.raw?.receiver_fraud_flag_count || 0);

  async function submitAppeal() {
    await onAppeal?.({ reason, phone, transactionId: result?.transaction_id });
    setSubmitted(true);
    setReason('');
    setPhone('');
  }

  return (
    <div className="result-screen blocked-screen shake-on-mount">
      <div className="blocked-icon high-risk" aria-hidden="true">🛡✕</div>
      <h2>Payment Stopped</h2>
      <p className="safe-line">Your money is safe</p>

      <SecurityReasonCard
        decision="BLOCK"
        title="Why we stopped this payment"
        reason={result?.user_reason || result?.user_message || 'This payment matched known fraud signals.'}
      />

      <FraudPatternCard pattern={result?.fraud_pattern} description={result?.user_reason} />

      {topReasons.length ? (
        <section className="user-card">
          <div className="field-label">Top Risk Reasons</div>
          <div className="txn-list">
            {topReasons.map((item, idx) => (
              <article key={`${idx}-${item}`} className="txn-item" style={{ cursor: 'default' }}>
                <div className="txn-left">
                  <span className="txn-avatar" style={{ background: idx === 0 ? '#fee2e2' : '#fef3c7', color: idx === 0 ? '#b91c1c' : '#92400e' }}>
                    {idx === 0 ? '!' : 'i'}
                  </span>
                  <div className="txn-identities">
                    <strong>{item}</strong>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <section className="user-card">
        <div className="field-label">Receiver Details</div>
        <div className="txn-meta">
          <span><strong>UPI ID:</strong> {receiverUpi}</span>
          <span><strong>Fraud Flag Count:</strong> {receiverFlagCount}</span>
        </div>
      </section>

      <section className="user-card guidance-card">
        <div className="field-label">What to do now</div>
        <ul>
          <li>If you initiated this payment, call your bank to verify the recipient.</li>
          <li>If you did not initiate this payment, change your UPI PIN immediately.</li>
          <li>Report this to National Cyber Crime Helpline: 1930.</li>
        </ul>
      </section>

      <div className="result-actions">
        <button type="button" className="primary-btn" onClick={onHome}>I understand — Go Home</button>
        <button type="button" className="ghost-btn" onClick={() => setShowAppeal((v) => !v)}>
          This was me — Appeal
        </button>
        <button type="button" className="ghost-btn" onClick={onReport}>Report this UPI ID</button>
      </div>

      {showAppeal ? (
        <section className="user-card appeal-card">
          <div className="field-label">Appeal this decision</div>
          <textarea
            className="text-input"
            rows={3}
            maxLength={200}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why do you believe this payment is legitimate?"
          />
          <input
            className="text-input"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="Phone number for callback"
            maxLength={15}
          />
          <button
            type="button"
            className="primary-btn"
            disabled={!reason.trim() || !phone.trim()}
            onClick={submitAppeal}
          >
            Submit Appeal
          </button>
          {submitted ? <p className="tiny-muted">Appeal submitted. Support will contact you.</p> : null}
        </section>
      ) : null}
    </div>
  );
}
