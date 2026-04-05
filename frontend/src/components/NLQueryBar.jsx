import React, { useState, useRef, useEffect } from 'react';

const SUGGESTIONS = [
  'Show blocked transactions today',
  'Find high risk above 70%',
  'List transactions above Rs.50000',
  'Show VERIFY decisions',
  'Find transactions from user_0001@upi',
];

export default function NLQueryBar({ onQuery, placeholder = 'Ask anything about transactions...' }) {
  const [query, setQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [recent, setRecent] = useState([]);
  const inputRef = useRef(null);

  const parseQuery = (q) => {
    const lower = q.toLowerCase();
    const filters = {};

    // Decision filters
    if (lower.includes('block')) filters.decision = 'BLOCK';
    else if (lower.includes('verify')) filters.decision = 'VERIFY';
    else if (lower.includes('allow')) filters.decision = 'ALLOW';

    // Amount filters
    const amountMatch = lower.match(/(?:above|over|greater than|>)\s*(?:rs\.?\s*)?(\d+)/i);
    if (amountMatch) filters.min_amount = parseInt(amountMatch[1]);

    const amountBelowMatch = lower.match(/(?:below|under|less than|<)\s*(?:rs\.?\s*)?(\d+)/i);
    if (amountBelowMatch) filters.max_amount = parseInt(amountBelowMatch[1]);

    // Risk filters
    const riskMatch = lower.match(/(?:risk|score)\s*(?:above|over|>)\s*(\d+)/);
    if (riskMatch) filters.min_risk = parseInt(riskMatch[1]) / 100;

    if (lower.includes('high risk')) filters.min_risk = 0.7;
    if (lower.includes('medium risk')) { filters.min_risk = 0.3; filters.max_risk = 0.7; }

    // UPI ID search
    const upiMatch = lower.match(/(\w+@\w+)/);
    if (upiMatch) filters.upi_search = upiMatch[1];

    // Time filters
    if (lower.includes('today')) filters.time_range = 'today';
    if (lower.includes('this week')) filters.time_range = 'week';
    if (lower.includes('last hour')) filters.time_range = 'hour';

    return filters;
  };

  const handleSubmit = () => {
    if (!query.trim()) return;
    const filters = parseQuery(query);
    setRecent((prev) => [query, ...prev.filter((r) => r !== query)].slice(0, 5));
    onQuery?.(filters, query);
    setShowSuggestions(false);
  };

  return (
    <div className="relative">
      <div className="flex items-center gap-2 rounded-xl border border-border/60 bg-bg-card/50 px-3 py-2 focus-within:border-accent/40 transition">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="rgb(139, 143, 173)" strokeWidth="2" className="shrink-0">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setShowSuggestions(true)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSubmit();
            if (e.key === 'Escape') setShowSuggestions(false);
          }}
          placeholder={placeholder}
          className="flex-1 bg-transparent text-sm text-textPrimary outline-none placeholder:text-textMuted"
        />
        {query && (
          <button
            type="button"
            onClick={() => { setQuery(''); inputRef.current?.focus(); }}
            className="text-textMuted hover:text-textSecondary transition"
          >
            ✕
          </button>
        )}
      </div>

      {/* Suggestions dropdown */}
      {showSuggestions && (
        <div className="absolute top-full left-0 right-0 mt-1 z-40 glass rounded-xl border border-border/40 shadow-glow overflow-hidden">
          {recent.length > 0 && (
            <div className="px-3 py-2 border-b border-border/30">
              <div className="text-[10px] font-semibold text-textMuted uppercase tracking-wider mb-1">Recent</div>
              {recent.map((r, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => { setQuery(r); handleSubmit(); }}
                  className="block w-full text-left text-xs text-textSecondary hover:text-textPrimary py-1 transition"
                >
                  {r}
                </button>
              ))}
            </div>
          )}
          <div className="px-3 py-2">
            <div className="text-[10px] font-semibold text-textMuted uppercase tracking-wider mb-1">Suggestions</div>
            {SUGGESTIONS.map((s, i) => (
              <button
                key={i}
                type="button"
                onClick={() => { setQuery(s); setShowSuggestions(false); setTimeout(handleSubmit, 50); }}
                className="block w-full text-left text-xs text-textSecondary hover:text-accent py-1 transition"
              >
                💡 {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
