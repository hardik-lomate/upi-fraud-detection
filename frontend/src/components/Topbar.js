import React from 'react';

function streamLabel(transport) {
  if (transport === 'websocket') return 'WebSocket Live';
  if (transport === 'api-fallback') return 'API Polling';
  if (transport === 'simulated') return 'Simulated';
  if (transport === 'paused') return 'Paused';
  return 'Connecting';
}

export default function Topbar({ title, apiOnline, streamTransport }) {
  const now = new Date();

  return (
    <header className="sticky top-0 z-10 border-b border-border/80 bg-[#08131d]/92 backdrop-blur">
      <div className="flex min-h-16 flex-wrap items-center justify-between gap-3 px-6 py-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.16em] text-textSecondary">Fraud Decisioning</div>
          <div className="font-display text-lg font-semibold text-textPrimary">{title}</div>
        </div>

        <div className="flex items-center gap-2">
          <div
            className={
              apiOnline
                ? 'rounded-full border border-success/25 bg-success/15 px-2.5 py-1 text-xs font-medium text-success'
                : 'rounded-full border border-warning/25 bg-warning/15 px-2.5 py-1 text-xs font-medium text-warning'
            }
          >
            {apiOnline ? 'API Online' : 'API Offline'}
          </div>

          <div className="rounded-full border border-border/80 bg-bg/45 px-2.5 py-1 text-xs text-textSecondary">
            {streamLabel(streamTransport)}
          </div>

          <div className="hidden rounded-full border border-border/80 bg-bg/45 px-2.5 py-1 font-mono text-xs text-textSecondary md:block">
            {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </div>

          <div className="flex items-center gap-2 rounded-full border border-border/80 bg-bg/45 px-2.5 py-1">
            <div className="h-6 w-6 rounded-full bg-gradient-to-br from-primary/70 to-success/60" />
            <div className="text-xs text-textSecondary">Fraud Ops Analyst</div>
          </div>
        </div>
      </div>
    </header>
  );
}
