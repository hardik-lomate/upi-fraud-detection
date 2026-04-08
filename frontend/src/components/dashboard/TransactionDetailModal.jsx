import React from 'react';
import { AlertTriangle, CheckCircle2, ShieldAlert, X } from 'lucide-react';
import DecisionBadge from './DecisionBadge';
import RiskBadge from './RiskBadge';
import RiskGauge from './RiskGauge';
import RiskBreakdownBar from './RiskBreakdownBar';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

function signalIcon(decision) {
  const d = String(decision || '').toUpperCase();
  if (d === 'BLOCK') return <ShieldAlert className="h-4 w-4 text-rose-300" />;
  if (d === 'STEP-UP' || d === 'VERIFY') return <AlertTriangle className="h-4 w-4 text-amber-200" />;
  return <CheckCircle2 className="h-4 w-4 text-emerald-300" />;
}

function FeatureRow({ label, value }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-700/70 bg-slate-950/60 px-3 py-2">
      <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{label}</span>
      <span className="text-sm text-slate-100">{String(value ?? 'N/A')}</span>
    </div>
  );
}

function TransactionDetailModal({ open, transaction, loading, error, onClose }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <div className="max-h-[92vh] w-full max-w-4xl overflow-hidden rounded-3xl border border-slate-700/70 bg-slate-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-700/60 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Transaction Detail</p>
            <p className="font-mono text-sm text-slate-100">{transaction?.transaction_id || 'Loading...'}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-slate-600 p-2 text-slate-300 transition hover:border-slate-400 hover:text-slate-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-[calc(92vh-72px)] overflow-y-auto p-5">
          {loading && (
            <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 text-sm text-slate-300">
              Loading transaction intelligence...
            </div>
          )}

          {!loading && error && (
            <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">
              {error}
            </div>
          )}

          {!loading && !error && transaction && (
            <div className="space-y-5">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl border border-slate-700/70 bg-slate-950/60 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Amount</p>
                  <p className="mt-1 text-lg font-semibold text-slate-100">{formatCurrency(transaction.amount)}</p>
                </div>
                <div className="rounded-xl border border-slate-700/70 bg-slate-950/60 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Risk Score</p>
                  <p className="mt-1 text-lg font-semibold text-slate-100">{(Number(transaction.risk_score || 0) * 100).toFixed(1)}%</p>
                </div>
                <div className="rounded-xl border border-slate-700/70 bg-slate-950/60 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Decision</p>
                  <div className="mt-1"><DecisionBadge decision={transaction.decision} /></div>
                </div>
                <div className="rounded-xl border border-slate-700/70 bg-slate-950/60 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Timestamp</p>
                  <p className="mt-1 text-sm text-slate-200">{formatDateTime(transaction.timestamp)}</p>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-700/70 bg-slate-950/60 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-sm font-semibold tracking-wide text-slate-100">Risk Score Gauge</h3>
                  <RiskBadge risk={transaction.risk_score} />
                </div>
                <RiskGauge risk={transaction.risk_score} />
              </div>

              <div className="rounded-2xl border border-slate-700/70 bg-slate-950/60 p-4">
                <h3 className="mb-3 text-sm font-semibold tracking-wide text-slate-100">Component Breakdown</h3>
                <RiskBreakdownBar scores={transaction.component_scores} />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-2xl border border-slate-700/70 bg-slate-950/60 p-4">
                  <h3 className="mb-3 text-sm font-semibold tracking-wide text-slate-100">Reason List</h3>
                  <div className="space-y-2">
                    {(transaction.reasons || []).length === 0 && (
                      <p className="text-sm text-slate-400">No explicit reasons were returned for this transaction.</p>
                    )}
                    {(transaction.reasons || []).map((reason) => (
                      <div key={reason} className="flex items-start gap-2 rounded-lg border border-slate-700/70 bg-slate-900/70 p-2.5">
                        {signalIcon(transaction.decision)}
                        <p className="text-sm text-slate-200">{reason}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-700/70 bg-slate-950/60 p-4">
                  <h3 className="mb-3 text-sm font-semibold tracking-wide text-slate-100">Feature Summary</h3>
                  <div className="space-y-2">
                    <FeatureRow label="Sender" value={transaction.sender_upi} />
                    <FeatureRow label="Receiver" value={transaction.receiver_upi} />
                    <FeatureRow label="Txn Type" value={transaction.transaction_type} />
                    <FeatureRow
                      label="Is New Device"
                      value={transaction.feature_summary?.key_features?.is_new_device ?? 'N/A'}
                    />
                    <FeatureRow
                      label="Is New Receiver"
                      value={transaction.feature_summary?.key_features?.is_new_receiver ?? 'N/A'}
                    />
                    <FeatureRow
                      label="Txn Count / 1min"
                      value={transaction.feature_summary?.key_features?.sender_txn_count_1min ?? 'N/A'}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default React.memo(TransactionDetailModal);
