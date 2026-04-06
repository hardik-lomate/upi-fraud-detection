import React, { useEffect, useMemo, useState } from 'react';
import ShieldAnimation from '../components/user/ShieldAnimation';

const CHECK_ITEMS = [
  'Verifying receiver identity',
  'Checking transaction patterns',
  'Analyzing network signals',
];

function wait(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

export default function SecurityCheckScreen({ paymentPayload, onRunCheck, onComplete }) {
  const [step, setStep] = useState(1);
  const [visibleChecks, setVisibleChecks] = useState(0);
  const [decision, setDecision] = useState('ALLOW');

  const shieldState = useMemo(() => {
    if (step < 3) return 'scanning';
    if (decision === 'BLOCK') return 'blocked';
    if (decision === 'VERIFY') return 'warn';
    return 'safe';
  }, [step, decision]);

  useEffect(() => {
    let mounted = true;

    async function run() {
      const startedAt = Date.now();
      setStep(1);
      setVisibleChecks(0);

      await wait(400);
      if (!mounted) return;

      setStep(2);
      for (let i = 1; i <= CHECK_ITEMS.length; i += 1) {
        await wait(150);
        if (!mounted) return;
        setVisibleChecks(i);
      }

      let response;
      try {
        response = await Promise.race([
          onRunCheck(paymentPayload),
          new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Security check timeout')), 8000);
          }),
        ]);
      } catch {
        response = {
          decision: 'BLOCK',
          status: 'BLOCKED',
          user_message: 'Your money is safe. Payment stopped for your protection.',
          user_reason: 'We could not complete the security checks in time. Please try again.',
          amount: paymentPayload?.amount || 0,
          receiver_upi: paymentPayload?.receiver_upi || '',
          receiver_name: paymentPayload?.receiver_name || 'recipient',
          timestamp: new Date().toISOString(),
          receipt_id: 'SP-TIMEOUT',
        };
      }

      if (!mounted) return;

      const elapsed = Date.now() - startedAt;
      const minDisplayMs = 1200;
      if (elapsed < minDisplayMs) {
        await wait(minDisplayMs - elapsed);
      }

      if (!mounted) return;
      setDecision(response.decision || 'ALLOW');
      setStep(3);

      await wait(420);
      if (!mounted) return;
      onComplete(response);
    }

    run();
    return () => {
      mounted = false;
    };
  }, [onComplete, onRunCheck, paymentPayload]);

  return (
    <div className="checking-screen">
      <ShieldAnimation state={shieldState} size={120} className="checking-shield" />
      <h2>Checking security...</h2>
      <p>ShieldPay is verifying this payment before money leaves your account.</p>

      <ul className="checklist">
        {CHECK_ITEMS.map((item, idx) => (
          <li key={item} className={idx < visibleChecks ? 'visible' : ''}>
            <span>{idx < visibleChecks ? '✓' : '•'}</span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
