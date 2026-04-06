import React, { useState } from 'react';
import SecurityReasonCard from '../components/user/SecurityReasonCard';
import FraudPatternCard from '../components/user/FraudPatternCard';

export default function PaymentBlockedScreen({ result, onHome, onAppeal, onReport }) {
  const [showAppeal, setShowAppeal] = useState(false);
  const [reason, setReason] = useState('');
  const [phone, setPhone] = useState('');
  const [submitted, setSubmitted] = useState(false);

  async function submitAppeal() {
    await onAppeal?.({ reason, phone, transactionId: result?.transaction_id });
    setSubmitted(true);
    setReason('');
    setPhone('');
  }

  return (
    <div className="result-screen blocked-screen shake-on-mount">
      <div className="blocked-icon" aria-hidden="true">🛡✕</div>
      <h2>Payment Stopped</h2>
      <p className="safe-line">Your money is safe</p>

      <SecurityReasonCard
        decision="BLOCK"
        title="Why we stopped this payment"
        reason={result?.user_reason || result?.user_message || 'This payment matched known fraud signals.'}
      />

      <FraudPatternCard pattern={result?.fraud_pattern} description={result?.user_reason} />

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
        <button type="button" className="ghost-btn" onClick={onReport}>Report to Bank (1930)</button>
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
