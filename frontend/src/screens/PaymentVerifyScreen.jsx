import React, { useMemo, useState } from 'react';
import SecurityReasonCard from '../components/user/SecurityReasonCard';
import { formatIndianCurrency } from '../utils/format';

const METHODS = [
  { method: 'fingerprint', label: 'Use Fingerprint', primary: true },
  { method: 'face', label: 'Use Face ID', primary: false },
  { method: 'pin', label: 'Enter UPI PIN', primary: false },
];

function wait(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

export default function PaymentVerifyScreen({ result, onVerify, onBack, onResolved }) {
  const [phase, setPhase] = useState('idle');
  const [busyMethod, setBusyMethod] = useState('fingerprint');
  const [errorText, setErrorText] = useState('');

  const headline = useMemo(() => {
    if (phase === 'success') return 'Verification complete';
    if (phase === 'failed') return 'Verification failed';
    return 'Verify to complete payment';
  }, [phase]);

  async function runVerification(method) {
    setBusyMethod(method);
    setErrorText('');
    setPhase('scanning');
    try {
      const verification = await onVerify(method);
      const status = String(verification?.verification_status || '').toUpperCase();
      const passed = status === 'VERIFIED' || verification?.final_decision === 'ALLOW';

      if (passed) {
        setPhase('success');
        await wait(500);
        onResolved?.({
          outcome: 'success',
          verification,
        });
        return;
      }

      setPhase('failed');
      await wait(650);
      onResolved?.({
        outcome: 'blocked',
        verification,
      });
    } catch {
      setPhase('failed');
      setErrorText('Verification did not complete. Please try again.');
    }
  }

  return (
    <div className="verify-screen">
      <button type="button" className="ghost-btn" onClick={onBack}>← Back</button>

      <div className={`verify-hero phase-${phase}`}>
        <div className="verify-icon-wrap">
          <span className={`verify-icon ${phase}`}>{phase === 'success' ? '✓' : phase === 'failed' ? '✕' : '🛡'}</span>
          <svg className={`scan-ring ${phase === 'scanning' ? 'active' : ''}`} viewBox="0 0 84 84" aria-hidden="true">
            <circle cx="42" cy="42" r="36" />
          </svg>
        </div>
        <h2>{headline}</h2>
        <p>
          {formatIndianCurrency(result?.amount || 0)} to {result?.receiver_name || 'recipient'} needs your confirmation.
        </p>
      </div>

      <SecurityReasonCard
        decision="VERIFY"
        title="Why we need this"
        reason={result?.user_reason || 'This payment is larger or more unusual than your normal activity.'}
      />

      <div className="verify-methods">
        {METHODS.map((item) => (
          <button
            key={item.method}
            type="button"
            className={`verify-method ${item.primary ? 'primary' : ''}`}
            disabled={phase === 'scanning'}
            onClick={() => runVerification(item.method)}
          >
            {phase === 'scanning' && busyMethod === item.method ? 'Scanning...' : item.label}
          </button>
        ))}
      </div>

      <p className="tiny-muted">
        ShieldPay detected: {result?.user_reason || 'unusual payment pattern'}. This verification protects your money.
      </p>

      {errorText ? <p className="risk-warning">{errorText}</p> : null}
    </div>
  );
}
