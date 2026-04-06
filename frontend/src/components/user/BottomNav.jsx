import React from 'react';

const ITEMS = [
  { id: 'home', label: 'Home', icon: '⌂' },
  { id: 'pay', label: 'Pay', icon: '⇧' },
  { id: 'history', label: 'History', icon: '◷' },
  { id: 'security', label: 'Security', icon: '🛡' },
  { id: 'console', label: 'Console', icon: '◐' },
];

export default function BottomNav({ active, onNavigate, onConsole }) {
  return (
    <nav className="bottom-nav" aria-label="Bottom navigation">
      {ITEMS.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`bottom-nav-item ${active === item.id ? 'active' : ''}`}
          onClick={() => {
            if (item.id === 'console') {
              onConsole?.();
            } else {
              onNavigate?.(item.id);
            }
          }}
        >
          <span>{item.icon}</span>
          <small>{item.label}</small>
        </button>
      ))}
    </nav>
  );
}
