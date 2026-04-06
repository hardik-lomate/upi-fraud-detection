import React from 'react';
import { formatIndianCurrency } from '../../utils/format';

const PAD_KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '.', '0', '⌫'];
const QUICK_AMOUNTS = [100, 500, 1000, 5000];

function nextValue(current, key) {
  if (key === '⌫') {
    return current.slice(0, -1);
  }
  if (key === '.') {
    if (!current) return '0.';
    if (current.includes('.')) return current;
    return `${current}.`;
  }
  if (current === '0') return key;
  if (current.length >= 9) return current;
  return `${current}${key}`;
}

export default function Numpad({ value, onChange }) {
  const amount = Number(value || 0);

  return (
    <section className="user-card amount-card">
      <div className="field-label">Amount</div>
      <div key={value} className="amount-display amount-in">
        {amount > 0 ? formatIndianCurrency(amount) : '₹0'}
      </div>

      <div className="quick-amounts">
        {QUICK_AMOUNTS.map((amt) => (
          <button
            key={amt}
            type="button"
            className="quick-amount-chip"
            onClick={() => onChange(String(amt))}
          >
            {formatIndianCurrency(amt)}
          </button>
        ))}
      </div>

      <div className="numpad-grid">
        {PAD_KEYS.map((key) => (
          <button
            key={key}
            type="button"
            className="numpad-key"
            onClick={() => onChange(nextValue(value, key))}
          >
            {key}
          </button>
        ))}
      </div>
    </section>
  );
}
