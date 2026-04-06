import React from 'react';
import ShieldAnimation from './ShieldAnimation';
import { formatIndianCurrency } from '../../utils/format';

function mapShieldState(status) {
  if (status === 'BLOCKED') return 'blocked';
  if (status === 'VERIFY' || status === 'PENDING_VERIFICATION') return 'warn';
  return 'safe';
}

export default function BalanceCard({ balance = 0, securityStatus = 'PROTECTED', lastDecision = 'ALLOW' }) {
  const shieldState = mapShieldState(lastDecision);

  return (
    <section className="balance-card elevated-card">
      <div>
        <div className="balance-label">Available Balance</div>
        <div className="balance-value">{formatIndianCurrency(balance)}</div>
        <div className={`balance-status ${securityStatus === 'AT_RISK' ? 'risk' : 'safe'}`}>
          {securityStatus === 'AT_RISK' ? 'AT RISK' : 'PROTECTED'}
        </div>
        <div className="balance-sub">ShieldPay protection active</div>
      </div>
      <div className="balance-shield">
        <ShieldAnimation state={shieldState} size={82} />
      </div>
    </section>
  );
}
