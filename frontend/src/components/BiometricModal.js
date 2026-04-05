import React, { useEffect, useMemo, useState } from 'react';
import { isVerify } from './StatusBadge';

export default function BiometricModal({ open, txn, onClose, onVerify }) {
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const needsVerification = useMemo(() => (txn ? isVerify(txn) : false), [txn]);

  useEffect(() => {
    if (!open) return;
    setSubmitting(false);
    setResult(null);
    setError(null);
  }, [open, txn?.transaction_id]);

  if (!open) return null;

  const handleVerify = async () => {
    if (!txn || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await onVerify(txn);
      setResult(res);
      if (res?.verification_status === 'ERROR') {
        setError(res?.message || 'Verification failed.');
      }
    } catch (e) {
      setError(e?.message || 'Verification failed.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 px-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-border/80 bg-surface shadow-2xl">
        <div className="px-5 py-4">
          <div className="text-[11px] uppercase tracking-[0.14em] text-textSecondary">Step-up Authentication</div>
          <div className="mt-1 font-display text-base font-semibold text-textPrimary">Identity Verification Required</div>
          <div className="mt-1 text-sm text-textSecondary">
            {txn?.message || 'This transaction requires biometric verification before it can proceed.'}
          </div>
        </div>

        <div className="border-t border-border/80 px-5 py-4">
          <div className="text-xs text-textSecondary">Transaction</div>
          <div className="mt-1 font-mono text-xs text-textPrimary">{txn?.transaction_id || '—'}</div>

          <div className="mt-3 text-sm text-textSecondary">
            Method: <span className="font-medium text-textPrimary">Fingerprint</span>
          </div>

          {result?.message ? (
            <div className="mt-3 rounded-lg border border-border/80 bg-bg/35 px-3 py-2 text-sm text-textPrimary">
              {result.message}
            </div>
          ) : null}

          {error ? (
            <div className="mt-3 rounded-lg border border-danger/20 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </div>
          ) : null}

          {!needsVerification ? (
            <div className="mt-3 text-sm text-textSecondary">This transaction is not pending verification.</div>
          ) : null}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border/80 px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-2 text-sm font-medium text-textSecondary transition hover:bg-bg/30 hover:text-textPrimary"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleVerify}
            disabled={!needsVerification || submitting}
            className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? 'Verifying…' : 'Verify'}
          </button>
        </div>
      </div>
    </div>
  );

}
