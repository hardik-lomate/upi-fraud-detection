import React from 'react';
import { clamp01 } from '../../utils/formatters';

function RiskBadge({ risk }) {
  const score = clamp01(risk);

  let tone = 'bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-400/40';
  let label = 'SAFE';

  if (score >= 0.3 && score <= 0.6) {
    tone = 'bg-amber-500/15 text-amber-200 ring-1 ring-amber-300/40';
    label = 'WATCH';
  } else if (score > 0.6) {
    tone = 'bg-rose-500/15 text-rose-200 ring-1 ring-rose-400/40';
    label = 'RISK';
  }

  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>
      <span>{label}</span>
      <span>{(score * 100).toFixed(1)}%</span>
    </span>
  );
}

export default React.memo(RiskBadge);
