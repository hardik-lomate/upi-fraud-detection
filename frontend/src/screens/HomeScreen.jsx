import React, { useMemo, useState } from 'react';
import BalanceCard from '../components/user/BalanceCard';
import TransactionItem from '../components/user/TransactionItem';
import { firstName, greetingByTime } from '../utils/format';

const RISK_SCENARIOS = [
  {
    id: 'normal_payment',
    label: 'Normal Payment',
    emoji: '✅',
    description: 'Pay Rs.349 to Swiggy',
    payload: { receiver_upi: 'swiggy@icici', amount: 349, transaction_type: 'purchase' },
  },
  {
    id: 'high_value_verify',
    label: 'Large Transfer',
    emoji: '🔐',
    description: 'Send Rs.45,000 to new recipient',
    payload: { receiver_upi: 'friend.new@ybl', amount: 45000, transaction_type: 'transfer' },
  },
  {
    id: 'mule_block',
    label: 'Mule Account',
    emoji: '🛡',
    description: 'Blocked money mule account',
    payload: { receiver_upi: 'mule_a_collect@ybl', amount: 85000, transaction_type: 'transfer' },
  },
  {
    id: 'kyc_scam',
    label: 'Fake KYC Scam',
    emoji: '🚨',
    description: 'Critical govt impersonation block',
    payload: { receiver_upi: 'npci.helpdesk.kyc@paytm', amount: 2999, transaction_type: 'transfer' },
  },
  {
    id: 'sim_swap',
    label: 'SIM Swap Attack',
    emoji: '📱',
    description: 'New-device takeover attempt',
    payload: { receiver_upi: 'offshore_xk9f2@ybl', amount: 120000, transaction_type: 'transfer', sender_device_id: 'SIM_SWAP_NEW_001' },
  },
  {
    id: 'night_transfer',
    label: 'Midnight Transfer',
    emoji: '🌙',
    description: 'Large late-night transfer',
    payload: { receiver_upi: 'landlord@ybl', amount: 22000, transaction_type: 'transfer' },
  },
];

function securityBannerVariant(transactions) {
  const hasBlocked = transactions.some((txn) => txn.status === 'BLOCKED');
  if (hasBlocked) {
    return {
      tone: 'blocked',
      text: 'We blocked a suspicious transaction today. Your money is safe.',
    };
  }
  const hasAlert = transactions.some(
    (txn) => txn.status === 'PENDING_VERIFICATION' || txn.status === 'VERIFIED'
  );
  if (hasAlert) {
    return {
      tone: 'alert',
      text: 'Unusual activity detected in the last 24 hours. Review your recent transactions.',
    };
  }
  return {
    tone: 'safe',
    text: 'All your recent transactions look normal. Stay alert to OTP sharing requests.',
  };
}

export default function HomeScreen({
  profile,
  profiles,
  transactions,
  securitySummary,
  onOpenPay,
  onOpenHistory,
  onOpenSecurity,
  onRunDemo,
  onSelectProfile,
}) {
  const [profileOpen, setProfileOpen] = useState(false);

  const lastDecision = transactions[0]?.decision || 'ALLOW';
  const banner = useMemo(() => securityBannerVariant(transactions), [transactions]);
  const securityStatus = banner.tone === 'blocked' ? 'AT_RISK' : 'PROTECTED';
  const alertCount = Number(securitySummary?.recent_alerts?.length || 0);
  const blockedToday = transactions.filter((txn) => txn.status === 'BLOCKED').length;
  const safetyScore = Number(securitySummary?.score || 0);

  return (
    <div className="screen-stack">
      <header className="wallet-header">
        <button type="button" className="avatar-button" onClick={() => setProfileOpen((v) => !v)}>
          <span className="avatar-dot" style={{ backgroundColor: profile.avatarColor }}>{profile.initials}</span>
        </button>

        <div className="greeting-text">
          <small>{greetingByTime()}</small>
          <strong>{firstName(profile.name)}</strong>
        </div>

        <button type="button" className="bell-button" aria-label="Security alerts">
          🔔
          {alertCount > 0 ? <span className="badge-dot">{alertCount}</span> : null}
        </button>
      </header>

      {profileOpen ? (
        <section className="user-card profile-switcher">
          <div className="field-label">Switch profile</div>
          <div className="profile-list">
            {profiles.map((item) => (
              <button
                type="button"
                key={item.upi}
                className={`profile-row ${item.upi === profile.upi ? 'active' : ''}`}
                onClick={() => {
                  onSelectProfile(item.upi);
                  setProfileOpen(false);
                }}
              >
                <span className="avatar-dot" style={{ backgroundColor: item.avatarColor }}>{item.initials}</span>
                <span>
                  <strong>{item.name}</strong>
                  <small>{item.upi}</small>
                </span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <BalanceCard
        balance={profile.balance}
        securityStatus={securityStatus}
        lastDecision={lastDecision}
        transactionsAnalyzedToday={transactions.length}
        blockedToday={blockedToday}
        userSafetyRating={safetyScore}
      />

      <section className="quick-actions">
        <button type="button" onClick={() => onOpenPay({ transaction_type: 'transfer' })}>
          <span>↗</span>
          <small>Send Money</small>
        </button>
        <button type="button" onClick={() => onOpenPay({ transaction_type: 'transfer' })}>
          <span>⌁</span>
          <small>Receive</small>
        </button>
        <button type="button" onClick={() => onOpenPay({ transaction_type: 'bill_payment' })}>
          <span>▦</span>
          <small>Pay Bills</small>
        </button>
        <button type="button" onClick={onOpenHistory}>
          <span>◷</span>
          <small>History</small>
        </button>
      </section>

      <section className={`security-banner tone-${banner.tone}`}>
        <p>{banner.text}</p>
        <button type="button" onClick={onOpenSecurity}>View Security Profile</button>
      </section>

      <section className="home-section">
        <div className="section-title-row">
          <h3>Recent Transactions</h3>
          <button type="button" onClick={onOpenHistory}>See all</button>
        </div>
        <div className="txn-list">
          {transactions.slice(0, 5).map((txn) => (
            <TransactionItem key={txn.transaction_id} txn={txn} />
          ))}
          {transactions.length === 0 ? <p className="empty-copy">No transactions yet. Start with a payment.</p> : null}
        </div>
      </section>

      <section className="home-section demo-section">
        <div className="section-title-row">
          <h3>Try Risk Scenarios</h3>
        </div>
        <div className="demo-grid">
          {RISK_SCENARIOS.map((scenario) => (
            <button
              type="button"
              key={scenario.id}
              className="demo-card"
              onClick={() => onRunDemo(scenario)}
            >
              <div>
                <strong>{scenario.emoji} {scenario.label}</strong>
                <small>{scenario.description}</small>
              </div>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
