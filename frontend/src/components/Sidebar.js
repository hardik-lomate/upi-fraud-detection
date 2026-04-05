import React from 'react';

const navItems = [
  {
    id: 'dashboard', label: 'Dashboard', hint: 'Live decision stream',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
    ),
  },
  {
    id: 'transactions', label: 'Transactions', hint: 'Stored transactions',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/>
        <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
      </svg>
    ),
  },
  {
    id: 'risk', label: 'Risk Monitor', hint: 'Fraud and drift watch',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
    ),
  },
  {
    id: 'graph', label: 'Network Graph', hint: 'Investigation network', isNew: true,
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>
        <line x1="8.5" y1="7.5" x2="15.5" y2="16.5"/><line x1="15.5" y1="7.5" x2="8.5" y2="16.5"/>
      </svg>
    ),
  },
  {
    id: 'cases', label: 'Cases', hint: 'Investigation workflow',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5" rx="1"/>
        <line x1="10" y1="12" x2="14" y2="12"/>
      </svg>
    ),
  },
  {
    id: 'settings', label: 'Settings', hint: 'Runtime settings',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
      </svg>
    ),
  },
];

function transportLabel(transport) {
  if (transport === 'websocket') return 'LIVE';
  if (transport === 'api-fallback') return 'POLLING';
  if (transport === 'simulated') return 'SIM';
  return '...';
}

function transportColor(transport) {
  if (transport === 'websocket') return 'rgb(0, 201, 167)';
  if (transport === 'simulated') return 'rgb(239, 159, 39)';
  return 'rgb(139, 143, 173)';
}

export default function Sidebar({ active, onChange, streamProfile, streamSpeed, streamTps, streamPaused, streamTransport, alertCount = 0, openCases = 0 }) {
  return (
    <aside className="sidebar-rail fixed inset-y-0 left-0 z-20 border-r border-border/60 bg-[#0A0B0F]/95 backdrop-blur-xl overflow-hidden">
      <div className="flex h-full flex-col">
        {/* Brand */}
        <div className="border-b border-border/50 px-4 py-4 flex items-center gap-3 min-h-[68px]">
          <div className="shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-accent-light flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
          </div>
          <div className="brand-text">
            <div className="text-[10px] font-bold tracking-[0.2em] text-accent">NFSOC v3</div>
            <div className="text-sm font-semibold text-textPrimary leading-tight">UPI Fraud Grid</div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="px-2 py-3 flex-1 space-y-1">
          {navItems.map((item) => {
            const isActive = active === item.id;
            const badge = item.id === 'dashboard' ? alertCount : item.id === 'cases' ? openCases : 0;
            return (
              <div key={item.id} className="tooltip-container">
                <button
                  type="button"
                  onClick={() => onChange(item.id)}
                  className={`group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 transition-all duration-200 relative ${
                    isActive
                      ? 'bg-accent/15 border border-accent/40 nav-active-glow text-textPrimary'
                      : 'border border-transparent text-textSecondary hover:bg-bg-elevated/50 hover:text-textPrimary'
                  }`}
                >
                  <span className={`shrink-0 w-5 h-5 ${isActive ? 'text-accent-light' : ''}`}>
                    {item.icon}
                  </span>
                  <span className="nav-label flex items-center gap-2">
                    <span className={`text-sm font-medium ${isActive ? 'text-textPrimary' : ''}`}>
                      {item.label}
                    </span>
                    {item.isNew && (
                      <span className="text-[9px] font-bold tracking-wider px-1.5 py-0.5 rounded-full bg-accent/20 text-accent-light">
                        NEW
                      </span>
                    )}
                  </span>
                  {badge > 0 && (
                    <span className="absolute top-1.5 right-1.5 min-w-[18px] h-[18px] rounded-full bg-danger flex items-center justify-center text-[10px] font-bold text-white px-1">
                      {badge > 99 ? '99+' : badge}
                    </span>
                  )}
                </button>
                <span className="tooltip-text">{item.label}</span>
              </div>
            );
          })}
        </nav>

        {/* Stream Status (bottom) */}
        <div className="border-t border-border/50 px-3 py-3">
          <div className="flex items-center gap-2 px-1">
            <div
              className="w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: streamPaused ? 'rgb(239, 159, 39)' : transportColor(streamTransport) }}
            />
            <span className="nav-label text-[10px] font-semibold tracking-[0.14em] text-textSecondary">
              {streamPaused ? 'PAUSED' : transportLabel(streamTransport)}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}
