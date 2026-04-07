import React from 'react';

function asPercent(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '--';
  return `${(n * 100).toFixed(2)}%`;
}

function asDecimal(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '--';
  return n.toFixed(2);
}

export default function ModelMetricsPanel({ metrics, loading }) {
  const matrix = metrics?.confusion_matrix;

  return (
    <section className="panel fade-in px-5 py-4">
      <div className="panel-title">Model Metrics</div>
      {loading ? <div className="tiny-muted" style={{ marginTop: 8 }}>Loading metrics...</div> : null}

      {!loading && metrics ? (
        <>
          <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3">
            <MetricItem label="Accuracy" value={asPercent(metrics.accuracy)} />
            <MetricItem label="Precision" value={asPercent(metrics.precision)} />
            <MetricItem label="Recall" value={asPercent(metrics.recall)} />
            <MetricItem label="F1 Score" value={asPercent(metrics.f1)} />
            <MetricItem label="ROC AUC" value={asDecimal(metrics.roc_auc)} />
            <MetricItem label="PR AUC" value={asDecimal(metrics.pr_auc)} />
          </div>

          {Array.isArray(matrix) && matrix.length === 2 ? (
            <div className="mt-4">
              <div className="text-xs uppercase tracking-[0.1em] text-textSecondary">Confusion Matrix</div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                <Cell label="True Negative" value={matrix[0]?.[0]} tone="safe" />
                <Cell label="False Positive" value={matrix[0]?.[1]} tone="warn" />
                <Cell label="False Negative" value={matrix[1]?.[0]} tone="warn" />
                <Cell label="True Positive" value={matrix[1]?.[1]} tone="danger" />
              </div>
            </div>
          ) : null}
        </>
      ) : null}

      {!loading && !metrics ? <div className="tiny-muted" style={{ marginTop: 8 }}>No metrics available yet.</div> : null}
    </section>
  );
}

function MetricItem({ label, value }) {
  return (
    <div className="rounded-xl border border-border/60 bg-bg-card/30 px-3 py-2">
      <div className="text-xs uppercase tracking-[0.1em] text-textSecondary">{label}</div>
      <div className="mt-1 font-mono text-sm text-textPrimary">{value}</div>
    </div>
  );
}

function Cell({ label, value, tone }) {
  const toneClass =
    tone === 'safe' ? 'border-accent/25' : tone === 'danger' ? 'border-danger/35' : 'border-warn/35';
  return (
    <div className={`rounded-xl border ${toneClass} bg-bg-card/30 px-3 py-3`}>
      <div className="text-xs text-textSecondary">{label}</div>
      <div className="mt-1 text-lg font-semibold text-textPrimary">{Number(value || 0)}</div>
    </div>
  );
}
