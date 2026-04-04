import React, { useEffect, useMemo, useState } from 'react';
import { isVerify } from './StatusBadge';

export default function BiometricModal({ open, txn, onClose, onVerify }) {
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  const needsVerification = useMemo(() => (txn ? isVerify(txn) : false), [txn]);

  useEffect(() => {
    if (!open) {
      setSubmitting(false);
      setResult(null);
    }
  }, [open]);

  if (!open) return null;

  const handleVerify = async () => {
    if (!txn || submitting) return;
    setSubmitting(true);
    try {
      const res = await onVerify(txn);
      setResult(res);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-md rounded-xl border border-border bg-surface shadow-2xl">
        <div className="px-5 py-4">
          <div className="text-sm font-semibold text-textPrimary">Identity Verification Required</div>
          <div className="mt-1 text-sm text-textSecondary">
            {txn?.message || 'This transaction requires biometric verification before it can proceed.'}
          </div>
        </div>

        <div className="border-t border-border px-5 py-4">
          <div className="text-xs text-textSecondary">Transaction</div>
          <div className="mt-1 text-sm font-medium text-textPrimary">{txn?.transaction_id || '—'}</div>

          {result?.message ? (
            <div className="mt-3 rounded-md border border-border bg-bg/30 px-3 py-2 text-sm text-textPrimary">
              {result.message}
            </div>
          ) : null}

          {!needsVerification ? (
            <div className="mt-3 text-sm text-textSecondary">This transaction is not pending verification.</div>
          ) : null}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-3 py-2 text-sm font-medium text-textSecondary hover:bg-bg/20 hover:text-textPrimary"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleVerify}
            disabled={!needsVerification || submitting}
            className="rounded-md bg-primary px-3 py-2 text-sm font-semibold text-white hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? 'Verifying…' : 'Verify'}
          </button>
        </div>
      </div>
    </div>
  );

}
