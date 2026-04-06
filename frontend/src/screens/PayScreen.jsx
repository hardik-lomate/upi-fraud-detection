import React, { useCallback, useEffect, useMemo, useState } from 'react';
import ReceiverInput from '../components/user/ReceiverInput';
import Numpad from '../components/user/Numpad';
import { fetchReceiverInfo } from '../api/fraudApi';
import { formatIndianCurrency } from '../utils/format';

const TXN_TYPES = [
  { value: 'transfer', label: 'Send to Person' },
  { value: 'purchase', label: 'Pay Merchant' },
  { value: 'bill_payment', label: 'Pay Bill' },
  { value: 'recharge', label: 'Recharge' },
];

function normalizeAmount(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, Math.min(500000, numeric));
}

export default function PayScreen({ draft, onBack, onSubmit }) {
  const [receiverUpi, setReceiverUpi] = useState(draft?.receiver_upi || '');
  const [amountInput, setAmountInput] = useState(draft?.amount ? String(draft.amount) : '');
  const [transactionType, setTransactionType] = useState(draft?.transaction_type || 'transfer');
  const [note, setNote] = useState(draft?.note || '');
  const [receiverInfo, setReceiverInfo] = useState(null);
  const [lookupBusy, setLookupBusy] = useState(false);

  useEffect(() => {
    if (!draft) return;
    setReceiverUpi(draft.receiver_upi || '');
    setAmountInput(draft.amount ? String(draft.amount) : '');
    setTransactionType(draft.transaction_type || 'transfer');
    setNote(draft.note || '');
  }, [draft]);

  const lookupReceiver = useCallback(async (upiId) => {
    if (!upiId || !upiId.includes('@')) {
      setReceiverInfo(null);
      return;
    }
    setLookupBusy(true);
    try {
      const info = await fetchReceiverInfo(upiId.trim().toLowerCase());
      setReceiverInfo(info);
    } catch {
      setReceiverInfo(null);
    } finally {
      setLookupBusy(false);
    }
  }, []);

  const amount = useMemo(() => normalizeAmount(amountInput), [amountInput]);
  const canPay = receiverUpi.trim().length >= 3 && amount >= 1;

  return (
    <div className="screen-stack">
      <header className="screen-header">
        <button type="button" className="ghost-btn" onClick={onBack}>← Back</button>
        <h2>Send Money</h2>
        <span className="tiny-muted">ShieldPay</span>
      </header>

      <ReceiverInput
        value={receiverUpi}
        onChange={setReceiverUpi}
        receiverInfo={receiverInfo}
        onLookup={lookupReceiver}
      />

      {lookupBusy ? <p className="tiny-muted">Checking receiver safety...</p> : null}

      <Numpad value={amountInput} onChange={setAmountInput} />

      <section className="user-card">
        <div className="field-label">Payment Details</div>
        <div className="txn-type-grid">
          {TXN_TYPES.map((type) => (
            <button
              key={type.value}
              type="button"
              className={`txn-type-chip ${transactionType === type.value ? 'active' : ''}`}
              onClick={() => setTransactionType(type.value)}
            >
              {type.label}
            </button>
          ))}
        </div>

        <label className="field-label" htmlFor="note-field">What is this payment for?</label>
        <input
          id="note-field"
          className="text-input"
          value={note}
          maxLength={100}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Optional note"
        />
      </section>

      <button
        type="button"
        className="pay-cta"
        disabled={!canPay}
        onClick={() =>
          onSubmit({
            receiver_upi: receiverUpi.trim().toLowerCase(),
            amount,
            transaction_type: transactionType,
            note: note.trim(),
            sender_device_id: draft?.sender_device_id || undefined,
            receiver_name: receiverInfo?.display_name,
          })
        }
      >
        <strong>Pay {canPay ? formatIndianCurrency(amount) : ''}</strong>
        <small>Protected by ShieldPay</small>
      </button>
    </div>
  );
}
