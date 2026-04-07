import React from 'react';

const navItems = [
  { id: 'dashboard', label: 'Operations', hint: 'Live decision stream' },
  { id: 'transactions', label: 'Ledger', hint: 'Stored transactions' },
  { id: 'risk', label: 'Risk Intelligence', hint: 'Fraud and drift watch' },
  { id: 'settings', label: 'Configuration', hint: 'Runtime settings' },
];

function transportLabel(transport) {
  if (transport === 'websocket') return 'LIVE SOCKET';
  if (transport === 'api-fallback') return 'API POLLING';
  if (transport === 'simulated') return 'SIM FALLBACK';
  return 'CONNECTING';
}

export default function Sidebar({ active, onChange, streamProfile, streamSpeed, streamTps, streamPaused, streamTransport }) {
  return (
    <aside className="fixed inset-y-0 left-0 z-20 w-[252px] border-r border-border/80 bg-[#08131d]/95 backdrop-blur">
      <div className="flex h-full flex-col">
        <div className="border-b border-border/70 px-5 py-5">
          <div className="inline-flex rounded-full border border-primary/40 bg-primary/15 px-2 py-1 text-[10px] font-semibold tracking-[0.16em] text-primary">
            NFSOC
          </div>
          <div className="mt-3 font-display text-xl font-semibold tracking-tight text-textPrimary">UPI Fraud Grid</div>
          <div className="mt-1 text-xs text-textSecondary">Institutional Fraud Decisioning Console</div>
        </div>

        <nav className="px-3 py-3">
          {navItems.map((item) => {
            const isActive = active === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onChange(item.id)}
                className={
                  isActive
                    ? 'group mb-2 flex w-full items-start rounded-xl border border-primary/45 bg-primary/15 px-3 py-2.5 text-left'
                    : 'group mb-2 flex w-full items-start rounded-xl border border-transparent px-3 py-2.5 text-left hover:border-border/80 hover:bg-bg/30'
                }
              >
                <span>
                  <span className={isActive ? 'block text-sm font-semibold text-textPrimary' : 'block text-sm font-semibold text-textSecondary group-hover:text-textPrimary'}>
                    {item.label}
                  </span>
                  <span className="mt-0.5 block text-xs text-textSecondary">{item.hint}</span>
                </span>
              </button>
            );
          })}
        </nav>

        <div className="mt-auto border-t border-border/70 px-5 py-5">
          <div className="text-[10px] font-semibold tracking-[0.14em] text-textSecondary">STREAM CONTEXT</div>
          <div className="mt-2 rounded-lg border border-border/80 bg-bg/45 p-3">
            <div className="flex items-center justify-between text-xs text-textSecondary">
              <span>State</span>
              <span className="font-mono text-textPrimary">{streamPaused ? 'PAUSED' : transportLabel(streamTransport)}</span>
            </div>
            <div className="mt-1 flex items-center justify-between text-xs text-textSecondary">
              <span>Profile</span>
              <span className="font-mono uppercase text-textPrimary">{streamProfile}</span>
            </div>
            <div className="mt-1 flex items-center justify-between text-xs text-textSecondary">
              <span>Speed</span>
              <span className="font-mono text-textPrimary">x{Number(streamSpeed || 1).toFixed(2)}</span>
            </div>
            <div className="mt-1 flex items-center justify-between text-xs text-textSecondary">
              <span>Target TPS</span>
              <span className="font-mono text-textPrimary">{Number(streamTps || 2).toFixed(1)}</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
