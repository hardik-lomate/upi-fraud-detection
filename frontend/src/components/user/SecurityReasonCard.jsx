import React from 'react';

export default function SecurityReasonCard({ decision = 'VERIFY', title = 'Security check', reason }) {
  const tone = String(decision || 'VERIFY').toLowerCase();
  return (
    <div className={`security-reason-card tone-${tone}`}>
      <div className="reason-title">{title}</div>
      <p>{reason}</p>
    </div>
  );
}
