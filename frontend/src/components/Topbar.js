import React from 'react';

export default function Topbar({ title, apiOnline }) {
  return (
    <header className="sticky top-0 z-10 border-b border-border bg-bg/90 backdrop-blur">
      <div className="flex h-14 items-center justify-between px-6">
        <div className="text-sm font-semibold text-textPrimary">{title}</div>

        <div className="flex items-center gap-3">
          <div
            className={
              apiOnline
                ? 'rounded-full border border-success/20 bg-success/10 px-2.5 py-1 text-xs font-medium text-success'
                : 'rounded-full border border-warning/20 bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning'
            }
          >
            {apiOnline ? 'API Online' : 'API Offline'}
          </div>

          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-border" />
            <div className="text-xs text-textSecondary">Demo Analyst</div>
          </div>
        </div>
      </div>
    </header>
  );
}
