import React from 'react';
import { clamp01, riskBand } from '../../utils/formatters';

function RiskGauge({ risk }) {
  const score = clamp01(risk);
  const band = riskBand(score);

  const colorClass =
    band === 'low'
      ? 'from-emerald-400 to-emerald-600'
      : band === 'medium'
        ? 'from-amber-300 to-amber-500'
        : 'from-rose-400 to-rose-600';

  const caption =
    band === 'low' ? 'Low Risk' : band === 'medium' ? 'Step-up Zone' : 'High Risk';

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm text-slate-300">
        <span>{caption}</span>
        <span className="font-semibold text-slate-100">{(score * 100).toFixed(1)}%</span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${colorClass}`}
          style={{ width: `${Math.max(4, score * 100)}%` }}
        />
      </div>
    </div>
  );
}

export default React.memo(RiskGauge);
