import React from 'react';

const MODEL_COLORS = {
  xgboost: '#6C47FF',
  lightgbm: '#00C9A7',
  catboost: '#378ADD',
  isolation_forest: '#EF9F27',
  online_recency: '#B47CFF',
};

const MODEL_LABELS = {
  xgboost: 'XGBoost',
  lightgbm: 'LightGBM',
  catboost: 'CatBoost',
  isolation_forest: 'IsoForest',
  online_recency: 'Online',
};

export default function ModelConsensus({ individualScores = {}, ensembleScore = 0 }) {
  const entries = Object.entries(individualScores).filter(
    ([, v]) => typeof v === 'number' && Number.isFinite(v)
  );

  if (entries.length === 0) {
    return (
      <div className="text-xs text-textSecondary">No model scores available</div>
    );
  }

  const values = entries.map(([, v]) => v);
  const spread = Math.max(...values) - Math.min(...values);
  const consensusLabel = spread <= 0.15 ? 'Strong' : spread <= 0.32 ? 'Moderate' : 'Weak';
  const consensusColor = spread <= 0.15 ? '#00C9A7' : spread <= 0.32 ? '#EF9F27' : '#E24B4A';

  return (
    <div className="space-y-3">
      {/* Consensus badge */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-textSecondary">Model Consensus</span>
        <span
          className="text-[11px] font-semibold px-2 py-0.5 rounded-full"
          style={{
            color: consensusColor,
            backgroundColor: `${consensusColor}15`,
            border: `1px solid ${consensusColor}30`,
          }}
        >
          {consensusLabel} ({(spread * 100).toFixed(0)}% spread)
        </span>
      </div>

      {/* Per-model bars */}
      <div className="space-y-2">
        {entries.map(([model, score]) => {
          const color = MODEL_COLORS[model] || '#8B8FAD';
          const label = MODEL_LABELS[model] || model;
          const pct = Math.min(score * 100, 100);

          return (
            <div key={model} className="group">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-textSecondary font-medium">{label}</span>
                <span className="font-mono text-textPrimary">{(score * 100).toFixed(1)}%</span>
              </div>
              <div className="h-2 rounded-full bg-bg-elevated/60 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700 ease-out"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: color,
                    boxShadow: `0 0 8px ${color}40`,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Ensemble line */}
      <div className="flex items-center justify-between pt-2 border-t border-border/40">
        <span className="text-xs font-semibold text-textPrimary">Ensemble Score</span>
        <span className="font-mono text-sm font-bold text-accent">{(ensembleScore * 100).toFixed(1)}%</span>
      </div>
    </div>
  );
}
