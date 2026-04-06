import React from 'react';

export default function FraudPatternCard({ pattern, description }) {
  if (!pattern) return null;

  return (
    <section className="fraud-pattern-card">
      <div className="pattern-title">Known scam pattern detected</div>
      <div className="pattern-name">{pattern}</div>
      {description ? <p className="pattern-desc">{description}</p> : null}
      <small>Source: NPCI and RBI reported UPI scam patterns</small>
    </section>
  );
}
