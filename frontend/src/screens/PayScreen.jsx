import React, { useCallback, useEffect, useMemo, useState } from 'react';
import ReceiverInput from '../components/user/ReceiverInput';
import Numpad from '../components/user/Numpad';
import FraudWarningModal from '../components/user/FraudWarningModal';
import {
  fetchReceiverInfo,
  preCheck,
  confirmPayment,
  cancelPayment,
} from '../api/fraudApi';
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
  const [preCheckResult, setPreCheckResult] = useState(null);
  const [showFraudWarning, setShowFraudWarning] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [pendingPayload, setPendingPayload] = useState(null);

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

  const buildPayload = useCallback(() => ({
    receiver_upi: receiverUpi.trim().toLowerCase(),
    amount,
    transaction_type: transactionType,
    note: note.trim(),
    sender_device_id: draft?.sender_device_id || undefined,
    receiver_name: receiverInfo?.display_name,
  }), [amount, draft?.sender_device_id, note, receiverInfo?.display_name, receiverUpi, transactionType]);

  const handlePayPress = useCallback(async () => {
    if (!canPay || isChecking) return;

    const payload = buildPayload();
    setPendingPayload(payload);
    setIsChecking(true);

    try {
      const senderUpi = (draft?.sender_upi || draft?.upi || 'demo.user@okicici').trim().toLowerCase();
      const preCheckPayload = {
        sender_upi: senderUpi,
        receiver_upi: payload.receiver_upi,
        amount: payload.amount,
        transaction_type: payload.transaction_type,
        sender_device_id: payload.sender_device_id || 'WEB_DEVICE',
        timestamp: new Date().toISOString(),
      };

      const result = await preCheck(preCheckPayload);
      setPreCheckResult(result);

      if (result?.user_warning?.show_warning) {
        setShowFraudWarning(true);
      } else {
        onSubmit?.({ ...payload, pre_check_id: result?.pre_check_id, pre_check_result: result });
      }
    } catch {
      // Fallback: keep old flow if pre-check API is not reachable.
      onSubmit?.(payload);
    } finally {
      setIsChecking(false);
    }
  }, [buildPayload, canPay, draft?.sender_upi, draft?.upi, isChecking, onSubmit]);

  const handleProceed = useCallback(async () => {
    if (!preCheckResult?.pre_check_id) {
      onSubmit?.(pendingPayload || buildPayload());
      return;
    }

    try {
      const confirmResult = await confirmPayment(preCheckResult.pre_check_id, true);
      onSubmit?.({
        ...(pendingPayload || buildPayload()),
        pre_check_id: preCheckResult.pre_check_id,
        pre_check_result: preCheckResult,
        confirm_result: confirmResult,
      });
    } catch {
      onSubmit?.({ ...(pendingPayload || buildPayload()), pre_check_id: preCheckResult.pre_check_id });
    } finally {
      setShowFraudWarning(false);
    }
  }, [buildPayload, onSubmit, pendingPayload, preCheckResult]);

  const handleCancel = useCallback(async () => {
    try {
      if (preCheckResult?.pre_check_id) {
        await cancelPayment(preCheckResult.pre_check_id, 'User cancelled from FraudWarningModal');
      }
    } catch {
      // keep UX responsive even if cancel API fails
    } finally {
      setShowFraudWarning(false);
    }
  }, [preCheckResult?.pre_check_id]);

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
        disabled={!canPay || isChecking}
        onClick={handlePayPress}
      >
        <strong>{isChecking ? 'Checking Risk...' : `Pay ${canPay ? formatIndianCurrency(amount) : ''}`}</strong>
        <small>{isChecking ? 'Running AI pre-check' : 'Protected by ShieldPay'}</small>
      </button>

      <FraudWarningModal
        visible={showFraudWarning}
        riskScore={Number(preCheckResult?.risk_score || preCheckResult?.fraud_score || 0)}
        riskTier={preCheckResult?.risk_tier || preCheckResult?.user_warning?.risk_tier}
        reasons={preCheckResult?.user_warning?.reasons_display || preCheckResult?.reasons || []}
        receiverUpi={receiverUpi.trim().toLowerCase()}
        amount={amount}
        transactionType={transactionType}
        isNewReceiver={Boolean(Number(preCheckResult?.raw?.is_new_receiver || 0))}
        onProceed={handleProceed}
        onCancel={handleCancel}
      />
    </div>
  );
}
