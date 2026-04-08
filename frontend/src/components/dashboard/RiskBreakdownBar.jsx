import React, { useMemo } from 'react';
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { clamp01 } from '../../utils/formatters';

function RiskBreakdownBar({ scores }) {
  const chartData = useMemo(() => {
    const source = scores || {};
    return [
      {
        name: 'components',
        rules: clamp01(source.rules) * 100,
        ml: clamp01(source.ml) * 100,
        behavior: clamp01(source.behavior) * 100,
        graph: clamp01(source.graph) * 100,
      },
    ];
  }, [scores]);

  return (
    <div className="space-y-3">
      <div className="h-20 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart layout="vertical" data={chartData} margin={{ top: 4, right: 6, bottom: 4, left: 0 }}>
            <XAxis hide type="number" domain={[0, 100]} />
            <YAxis hide type="category" dataKey="name" />
            <Tooltip
              cursor={false}
              contentStyle={{
                background: '#09131F',
                border: '1px solid rgba(84, 106, 132, 0.8)',
                borderRadius: '10px',
                color: '#E5EEF9',
              }}
              formatter={(val) => `${Number(val).toFixed(1)}%`}
            />
            <Bar dataKey="rules" stackId="risk" fill="#38BDF8" radius={[10, 0, 0, 10]} />
            <Bar dataKey="ml" stackId="risk" fill="#F97316" />
            <Bar dataKey="behavior" stackId="risk" fill="#EAB308" />
            <Bar dataKey="graph" stackId="risk" fill="#A855F7" radius={[0, 10, 10, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs text-slate-300 sm:grid-cols-4">
        <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 px-2 py-1.5">Rules: {(clamp01(scores?.rules) * 100).toFixed(1)}%</div>
        <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 px-2 py-1.5">ML: {(clamp01(scores?.ml) * 100).toFixed(1)}%</div>
        <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 px-2 py-1.5">Behavior: {(clamp01(scores?.behavior) * 100).toFixed(1)}%</div>
        <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 px-2 py-1.5">Graph: {(clamp01(scores?.graph) * 100).toFixed(1)}%</div>
      </div>
    </div>
  );
}

export default React.memo(RiskBreakdownBar);
