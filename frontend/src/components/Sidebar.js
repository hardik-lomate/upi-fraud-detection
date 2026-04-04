import React from 'react';

const navItems = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'transactions', label: 'Transactions' },
  { id: 'risk', label: 'Risk Monitor' },
  { id: 'settings', label: 'Settings' },
];

export default function Sidebar({ active, onChange }) {
  return (
    <aside className="fixed inset-y-0 left-0 w-[220px] border-r border-border bg-surface">
      <div className="flex h-full flex-col">
        <div className="px-4 py-4">
          <div className="text-sm font-semibold tracking-tight text-textPrimary">UPI Fraud</div>
          <div className="mt-0.5 text-xs text-textSecondary">Decision console</div>
        </div>

        <nav className="px-2 py-2">
          {navItems.map((item) => {
            const isActive = active === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onChange(item.id)}
                className={
                  isActive
                    ? 'group flex w-full items-center rounded-md border-l-2 border-primary bg-bg/20 px-3 py-2 text-left text-sm font-medium text-textPrimary'
                    : 'group flex w-full items-center rounded-md border-l-2 border-transparent px-3 py-2 text-left text-sm font-medium text-textSecondary hover:bg-bg/20 hover:text-textPrimary'
                }
              >
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="mt-auto px-4 py-4">
          <div className="text-xs text-textSecondary">API access required for live data.</div>
        </div>
      </div>
    </aside>
  );
}
