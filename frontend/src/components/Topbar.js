import React, { useState, useEffect, useCallback } from 'react';

function streamLabel(transport) {
  if (transport === 'websocket') return 'WebSocket Live';
  if (transport === 'api-fallback') return 'API Polling';
  if (transport === 'simulated') return 'Simulated';
  if (transport === 'paused') return 'Paused';
  return 'Connecting';
}

export default function Topbar({ title, apiOnline, streamTransport, onSearch }) {
  const now = new Date();
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Cmd+K shortcut
  const handleKeyDown = useCallback((e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      setSearchOpen((v) => !v);
    }
    if (e.key === 'Escape') {
      setSearchOpen(false);
    }
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <header className="sticky top-0 z-10 border-b border-border/60 glass">
      <div className="flex min-h-16 flex-wrap items-center justify-between gap-3 px-6 py-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.16em] text-textSecondary font-medium">Fraud Decisioning</div>
          <div className="font-display text-lg font-semibold text-textPrimary">{title}</div>
        </div>

        <div className="flex items-center gap-2">
          {/* Search bar */}
          <button
            type="button"
            onClick={() => setSearchOpen(true)}
            className="hidden md:flex items-center gap-2 rounded-lg border border-border/60 bg-bg/40 px-3 py-1.5 text-xs text-textSecondary hover:border-accent/40 transition"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <span>Search...</span>
            <kbd className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-border/50 bg-bg/50 text-textMuted ml-2">⌘K</kbd>
          </button>

          {/* Model Health */}
          <div className="hidden lg:flex items-center gap-1.5 rounded-full border border-border/60 bg-bg/40 px-2.5 py-1 text-xs text-textSecondary">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
            </svg>
            <span>v3.0 Ensemble</span>
          </div>

          {/* API Status */}
          <div
            className={
              apiOnline
                ? 'rounded-full border border-safe/25 bg-safe/10 px-2.5 py-1 text-xs font-medium text-safe'
                : 'rounded-full border border-warn/25 bg-warn/10 px-2.5 py-1 text-xs font-medium text-warn'
            }
          >
            <span className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${apiOnline ? 'bg-safe' : 'bg-warn'}`} />
              {apiOnline ? 'Online' : 'Offline'}
            </span>
          </div>

          {/* Stream Status */}
          <div className="rounded-full border border-border/60 bg-bg/40 px-2.5 py-1 text-xs text-textSecondary">
            {streamLabel(streamTransport)}
          </div>

          {/* Time */}
          <div className="hidden rounded-full border border-border/60 bg-bg/40 px-2.5 py-1 font-mono text-xs text-textSecondary md:block">
            {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </div>

          {/* Avatar */}
          <div className="flex items-center gap-2 rounded-full border border-border/60 bg-bg/40 px-2.5 py-1">
            <div className="h-6 w-6 rounded-full bg-gradient-to-br from-accent/70 to-safe/60" />
            <div className="hidden sm:block text-xs text-textSecondary">Analyst</div>
          </div>
        </div>
      </div>

      {/* Search overlay */}
      {searchOpen && (
        <div className="absolute inset-x-0 top-0 z-50 p-4" onClick={() => setSearchOpen(false)}>
          <div className="max-w-2xl mx-auto" onClick={(e) => e.stopPropagation()}>
            <div className="glass rounded-2xl border border-accent/20 shadow-glow p-1">
              <div className="flex items-center gap-3 px-4 py-3">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="rgb(108,71,255)" strokeWidth="2">
                  <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
                <input
                  autoFocus
                  type="text"
                  placeholder="Search transactions, UPI IDs, or type a natural language query..."
                  className="flex-1 bg-transparent text-sm text-textPrimary outline-none placeholder:text-textMuted"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && onSearch) {
                      onSearch(searchQuery);
                      setSearchOpen(false);
                    }
                  }}
                />
                <kbd className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-border/50 bg-bg/50 text-textMuted">ESC</kbd>
              </div>
              <div className="border-t border-border/40 px-4 py-2 text-[11px] text-textMuted">
                Try: "blocked transactions today" · "high risk from Mumbai" · "amount above 50000"
              </div>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
