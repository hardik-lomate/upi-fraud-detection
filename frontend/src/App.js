import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import TransactionTable from './components/TransactionTable';
import TransactionDetailsPanel from './components/TransactionDetailsPanel';
import BiometricModal from './components/BiometricModal';
import RiskMonitorPanel from './components/RiskMonitorPanel';

import { fetchTransactions, predictTransaction, verifyBiometric } from './api/fraudApi';
import { generateTransactionInput, simulatePredictFallback, simulateVerifyFallback } from './utils/simulate';

function normalizePredictResponse(resp, input) {
  return {
    transaction_id: resp.transaction_id,
    sender_upi: input?.sender_upi,
    receiver_upi: input?.receiver_upi,
    amount: input?.amount ?? resp.amount,
    fraud_score: resp.fraud_score,
    decision: resp.decision,
    status: resp.status,
    message: resp.message,
    risk_level: resp.risk_level,
    reasons: Array.isArray(resp.reasons) ? resp.reasons : [],
    timestamp: resp.timestamp || input?.timestamp || new Date().toISOString(),
    raw: resp,
  };
}

export default function App() {
  const [activeView, setActiveView] = useState('dashboard');
  const [apiOnline, setApiOnline] = useState(true);

  const [feed, setFeed] = useState([]);
  const [history, setHistory] = useState([]);

  const [selectedId, setSelectedId] = useState(null);
  const [loadingFeed, setLoadingFeed] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const [biometricOpen, setBiometricOpen] = useState(false);
  const [errorBanner, setErrorBanner] = useState(null);

  const simTimerRef = useRef(null);
  const historyTimerRef = useRef(null);

  const selectedTxn = useMemo(() => feed.find((t) => t.transaction_id === selectedId) || null, [feed, selectedId]);
  const selectedHistoryTxn = useMemo(
    () => history.find((t) => t.transaction_id === selectedId) || null,
    [history, selectedId]
  );

  const visibleSelectedTxn = activeView === 'transactions' ? selectedHistoryTxn : selectedTxn;

  const upsertFeedTxn = useCallback((txn) => {
    setFeed((prev) => {
      const next = [txn, ...prev.filter((p) => p.transaction_id !== txn.transaction_id)];
      return next.slice(0, 25);
    });
    setSelectedId((prev) => prev || txn.transaction_id);
  }, []);

  const refreshHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const rows = await fetchTransactions(80);
      setHistory(Array.isArray(rows) ? rows : []);
      setApiOnline(true);
    } catch {
      setApiOnline(false);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  const runOneSimulationTick = useCallback(async () => {
    setLoadingFeed(true);
    setErrorBanner(null);

    const input = generateTransactionInput();

    try {
      const resp = await predictTransaction(input);
      const txn = normalizePredictResponse(resp, input);
      upsertFeedTxn(txn);
      setApiOnline(true);
    } catch {
      // Fallback keeps the demo interactive even if the API is down.
      const fallback = simulatePredictFallback(input);
      const txn = normalizePredictResponse(fallback, input);
      upsertFeedTxn(txn);
      setApiOnline(false);
      setErrorBanner('API unreachable — using simulated demo data.');
    } finally {
      setLoadingFeed(false);
    }
  }, [upsertFeedTxn]);

  useEffect(() => {
    // initial load
    refreshHistory();
    runOneSimulationTick();

    // live simulation
    simTimerRef.current = setInterval(runOneSimulationTick, 4000);
    // keep history page fresh
    historyTimerRef.current = setInterval(refreshHistory, 12000);

    return () => {
      if (simTimerRef.current) clearInterval(simTimerRef.current);
      if (historyTimerRef.current) clearInterval(historyTimerRef.current);
    };
  }, [refreshHistory, runOneSimulationTick]);

  const handleVerify = useCallback(
    async (txn) => {
      try {
        const res = await verifyBiometric(txn.transaction_id);
        const next = {
          ...txn,
          decision: res.final_decision,
          status: res.verification_status === 'VERIFIED' ? 'VERIFIED' : 'BLOCKED',
          message: res.message,
        };
        upsertFeedTxn(next);
        setHistory((prev) => prev.map((p) => (p.transaction_id === next.transaction_id ? { ...p, ...next } : p)));
        // refresh persisted history after the state changes
        refreshHistory();
        return res;
      } catch (err) {
        // If server responded with an error (auth, not-found, validation), don't
        // pretend verification succeeded.
        if (err?.response) {
          const status = err.response.status;
          const detail = err.response.data?.detail;
          setErrorBanner(`Verification failed (${status}). ${detail || ''}`.trim());
          return {
            verification_status: 'ERROR',
            message: detail || 'Verification failed.',
          };
        }

        // Network failure: keep demo interactive.
        const res = simulateVerifyFallback(txn);
        const next = {
          ...txn,
          decision: res.final_decision,
          status: res.verification_status === 'VERIFIED' ? 'VERIFIED' : 'BLOCKED',
          message: res.message,
        };
        upsertFeedTxn(next);
        setHistory((prev) => prev.map((p) => (p.transaction_id === next.transaction_id ? { ...p, ...next } : p)));
        setApiOnline(false);
        setErrorBanner('API unreachable — biometric result simulated.');
        return res;
      }
    },
    [refreshHistory, upsertFeedTxn]
  );

  const title = useMemo(() => {
    if (activeView === 'dashboard') return 'Dashboard';
    if (activeView === 'transactions') return 'Transactions';
    if (activeView === 'risk') return 'Risk Monitor';
    if (activeView === 'settings') return 'Settings';
    return 'Dashboard';
  }, [activeView]);

  return (
    <div className="min-h-screen bg-bg">
      <Sidebar active={activeView} onChange={setActiveView} />

      <div className="pl-[220px]">
        <Topbar title={title} apiOnline={apiOnline} />

        {errorBanner ? (
          <div className="px-6 pt-4">
            <div className="rounded-md border border-warning/20 bg-warning/10 px-4 py-3 text-sm text-warning">
              {errorBanner}
            </div>
          </div>
        ) : null}

        {activeView === 'dashboard' && (
          <main className="px-6 py-6">
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_420px]">
              <TransactionTable
                title="Live Transactions"
                rows={feed}
                selectedId={selectedId}
                onSelect={setSelectedId}
                loading={loadingFeed}
              />
              <TransactionDetailsPanel txn={selectedTxn} onVerifyClick={() => setBiometricOpen(true)} />
            </div>
          </main>
        )}

        {activeView === 'transactions' && (
          <main className="px-6 py-6">
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_420px]">
              <TransactionTable
                title="Stored Transactions"
                rows={history}
                selectedId={selectedId}
                onSelect={setSelectedId}
                loading={loadingHistory}
              />
              <TransactionDetailsPanel txn={selectedHistoryTxn} onVerifyClick={() => setBiometricOpen(true)} />
            </div>
          </main>
        )}

        {activeView === 'risk' && (
          <main className="px-6 py-6">
            <RiskMonitorPanel apiOnline={apiOnline} />
          </main>
        )}

        {activeView === 'settings' && (
          <main className="px-6 py-6">
            <div className="rounded-xl border border-border bg-surface px-4 py-4">
              <div className="text-sm font-semibold text-textPrimary">Settings</div>
              <div className="mt-2 text-sm text-textSecondary">
                Configure API access using REACT_APP_API_URL. Authentication can be enabled in the backend via AUTH_REQUIRED.
              </div>
            </div>
          </main>
        )}
      </div>

      <BiometricModal
        open={biometricOpen}
        txn={visibleSelectedTxn}
        onClose={() => setBiometricOpen(false)}
        onVerify={handleVerify}
      />
    </div>
  );
}
