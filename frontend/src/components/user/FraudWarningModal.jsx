import React from 'react';
import FraudScoreGauge from '../../components/FraudScoreGauge';

function computedTier(riskScore, riskTier) {
  if (riskTier) return String(riskTier).toUpperCase();
  if (riskScore >= 0.75) return 'HIGH';
  if (riskScore >= 0.4) return 'MEDIUM';
  return 'LOW';
}

export default function FraudWarningModal({
  visible,
  riskScore = 0,
  riskTier,
  reasons = [],
  receiverUpi,
  amount,
  transactionType,
  isNewReceiver = false,
  onProceed,
  onCancel,
}) {
  if (!visible) return null;

  const tier = computedTier(riskScore, riskTier);
  const isHigh = tier === 'HIGH';
  const headerIcon = isHigh ? '🔴' : '⚠️';
  const headerTitle = isHigh ? 'High Risk - Payment Blocked' : 'Suspicious Transaction';
  const scorePct = Math.round(Math.max(0, Math.min(1, Number(riskScore) || 0)) * 100);

  return (
    <div className="fraud-warning-overlay" role="dialog" aria-modal="true">
      <div className={`fraud-warning-sheet tier-${tier.toLowerCase()}`}>
        <div className="fraud-warning-header">
          <span className="fraud-warning-icon">{headerIcon}</span>
          <div>
            <h3>{headerTitle}</h3>
            <p>
              {isHigh
                ? 'This payment is blocked for your protection.'
                : 'This payment has unusual risk signals. Review before continuing.'}
            </p>
          </div>
        </div>

        <div className="fraud-warning-gauge">
          <FraudScoreGauge score={riskScore} size={170} animated />
          <div className="fraud-warning-score-label">Risk Score: {scorePct}%</div>
        </div>

        <section className="fraud-warning-reasons">
          {(reasons || []).slice(0, 5).map((reason, idx) => (
            <div key={`${idx}-${reason}`} className="fraud-reason-item">
              <span>{idx < 2 ? '🔴' : '🟡'}</span>
              <span>{reason}</span>
            </div>
          ))}
        </section>

        <section className="fraud-warning-receiver">
          <div>
            <small>Receiver</small>
            <strong>{receiverUpi || 'unknown@upi'}</strong>
          </div>
          <div>
            <small>Amount</small>
            <strong>Rs.{Number(amount || 0).toLocaleString()}</strong>
          </div>
          <div>
            <small>Type</small>
            <strong>{transactionType || 'transfer'}</strong>
          </div>
          {isNewReceiver ? <span className="new-receiver-badge">NEW RECEIVER</span> : null}
        </section>

        <div className="fraud-warning-actions">
          {isHigh ? (
            <>
              <button type="button" className="primary-btn" onClick={onCancel}>
                Cancel Payment (Recommended)
              </button>
              <button type="button" className="ghost-btn danger-text" onClick={onProceed}>
                Proceed at my own risk
              </button>
            </>
          ) : (
            <>
              <button type="button" className="ghost-btn warn-outline" onClick={onProceed}>
                Proceed Anyway
              </button>
              <button type="button" className="primary-btn" onClick={onCancel}>
                Cancel Payment
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
