import React from 'react';

const STYLE_MAP = {
  ALLOW: 'bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-400/40',
  'STEP-UP': 'bg-amber-500/15 text-amber-200 ring-1 ring-amber-300/40',
  BLOCK: 'bg-rose-500/15 text-rose-200 ring-1 ring-rose-400/40',
};

function DecisionBadge({ decision }) {
  const key = String(decision || 'ALLOW').toUpperCase();
  const normalized = key === 'VERIFY' ? 'STEP-UP' : key;
  const tone = STYLE_MAP[normalized] || STYLE_MAP.ALLOW;

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold tracking-wide ${tone}`}>
      {normalized}
    </span>
  );
}

export default React.memo(DecisionBadge);
