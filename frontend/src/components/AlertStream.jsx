import React, { useState, useEffect, useRef } from 'react';

export default function AlertStream({ feed = [], maxItems = 20 }) {
  const [paused, setPaused] = useState(false);
  const listRef = useRef(null);

  // Filter to only BLOCK and VERIFY decisions
  const alerts = feed
    .filter((t) => {
      const d = String(t.decision || '').toUpperCase();
      return d === 'BLOCK' || d === 'VERIFY';
    })
    .slice(0, maxItems);

  // Auto-scroll
  useEffect(() => {
    if (!paused && listRef.current) {
      listRef.current.scrollTop = 0;
    }
  }, [alerts.length, paused]);

  const getIcon = (decision) => {
    if (decision === 'BLOCK') return '🛑';
    if (decision === 'VERIFY') return '⚠️';
    return '📋';
  };

  const getColor = (decision) => {
    if (decision === 'BLOCK') return 'border-danger/30 bg-danger/5';
    if (decision === 'VERIFY') return 'border-warn/30 bg-warn/5';
    return 'border-border/30 bg-bg-card/30';
  };

  const getTextColor = (decision) => {
    if (decision === 'BLOCK') return 'text-danger';
    if (decision === 'VERIFY') return 'text-warn';
    return 'text-textSecondary';
  };

  return (
    <div className="panel fade-in">
      <div className="flex items-center justify-between px-5 py-3 border-b border-border/60">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-danger animate-pulse" />
          <span className="panel-title text-xs">Alert Stream</span>
          <span className="text-[10px] text-textMuted font-mono">{alerts.length}</span>
        </div>
        <button
          type="button"
          onClick={() => setPaused((v) => !v)}
          className="text-[10px] text-textSecondary hover:text-accent transition"
        >
          {paused ? '▶ Resume' : '⏸ Pause'}
        </button>
      </div>

      <div
        ref={listRef}
        className="overflow-auto px-3 py-2 space-y-1.5"
        style={{ maxHeight: '280px' }}
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
      >
        {alerts.length === 0 ? (
          <div className="text-xs text-textMuted text-center py-6">No alerts yet — all clear</div>
        ) : (
          alerts.map((txn, i) => {
            const d = String(txn.decision || '').toUpperCase();
            const time = txn.timestamp ? new Date(txn.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';
            const amount = Number(txn.amount);

            return (
              <div
                key={txn.transaction_id || i}
                className={`rounded-lg border ${getColor(d)} px-3 py-2 transition-all duration-300 ${i === 0 ? 'animate-[slideInRight_0.3s_ease-out]' : ''}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm">{getIcon(d)}</span>
                    <span className={`text-xs font-semibold ${getTextColor(d)}`}>{d}</span>
                  </div>
                  <span className="font-mono text-[10px] text-textMuted">{time}</span>
                </div>
                <div className="mt-1 flex items-center justify-between text-[11px]">
                  <span className="text-textSecondary truncate max-w-[120px]">{txn.sender_upi}</span>
                  <span className="text-textSecondary">→</span>
                  <span className="text-textSecondary truncate max-w-[120px]">{txn.receiver_upi}</span>
                  <span className="font-mono font-semibold text-textPrimary">
                    ₹{Number.isFinite(amount) ? amount.toLocaleString() : '—'}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
