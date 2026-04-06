import React from 'react';
import { formatIndianCurrency, formatTime } from '../utils/format';

const LEVEL_TEXT = {
  EXCELLENT: { color: 'safe', text: 'Your account has excellent security health.' },
  GOOD: { color: 'safe', text: 'Your account is secure with minor alerts.' },
  FAIR: { color: 'warn', text: 'Some unusual patterns were detected recently.' },
  AT_RISK: { color: 'danger', text: 'Your account needs immediate attention.' },
};

const SECURITY_TIPS = [
  {
    title: 'Never share OTP',
    body: 'No bank or NPCI employee will ask for your OTP, UPI PIN, or password.',
  },
  {
    title: 'Verify QR codes',
    body: 'Always check the merchant name before scanning payment QR codes.',
  },
  {
    title: 'Night transfers',
    body: 'Be extra cautious about large transfers after 10 PM.',
  },
  {
    title: 'ShieldPay active',
    body: 'Every transaction is analyzed by our fraud engine in real time.',
  },
];

export default function SecurityProfileScreen({ scoreData }) {
  const score = Number(scoreData?.score || 0);
  const level = scoreData?.level || 'GOOD';
  const levelMeta = LEVEL_TEXT[level] || LEVEL_TEXT.GOOD;

  const radius = 68;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.max(0, Math.min(100, score));
  const dashOffset = circumference - (progress / 100) * circumference;

  return (
    <div className="screen-stack">
      <header className="screen-header">
        <h2>Security Profile</h2>
      </header>

      <section className="user-card security-gauge-card">
        <svg viewBox="0 0 180 180" className="security-gauge">
          <circle cx="90" cy="90" r={radius} className="gauge-bg" />
          <circle
            cx="90"
            cy="90"
            r={radius}
            className={`gauge-progress ${levelMeta.color}`}
            style={{ strokeDasharray: circumference, strokeDashoffset: dashOffset }}
          />
        </svg>
        <div className="gauge-center">
          <strong>{score}</strong>
          <small>{level.replace('_', ' ')}</small>
        </div>
        <p>{levelMeta.text}</p>
      </section>

      <section className="user-card">
        <div className="field-label">Security Summary</div>
        <div className="detail-grid">
          <div>
            <small>Fraud events</small>
            <strong>{scoreData?.fraud_events || 0}</strong>
          </div>
          <div>
            <small>Amount protected</small>
            <strong>{formatIndianCurrency(scoreData?.protected_amount || 0)}</strong>
          </div>
        </div>
      </section>

      <section className="user-card tips-card">
        <div className="field-label">Safety Tips</div>
        {SECURITY_TIPS.map((tip) => (
          <article key={tip.title}>
            <strong>{tip.title}</strong>
            <p>{tip.body}</p>
          </article>
        ))}
      </section>

      <section className="user-card">
        <div className="field-label">Recent Alerts</div>
        {scoreData?.recent_alerts?.length ? (
          <div className="alerts-list">
            {scoreData.recent_alerts.slice(0, 3).map((alert) => (
              <article key={alert.transaction_id}>
                <strong>{alert.status.replace('_', ' ')}</strong>
                <p>{alert.message}</p>
                <small>
                  {alert.receiver_name || alert.receiver_upi} · {formatIndianCurrency(alert.amount)} · {formatTime(alert.timestamp)}
                </small>
              </article>
            ))}
          </div>
        ) : (
          <p className="empty-copy">No security alerts. Your recent transactions look normal.</p>
        )}
      </section>
    </div>
  );
}
