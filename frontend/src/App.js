import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import TransactionTable from './components/TransactionTable';
import TransactionDetailsPanel from './components/TransactionDetailsPanel';
import BiometricModal from './components/BiometricModal';
import RiskMonitorPanel from './components/RiskMonitorPanel';
import AlertStream from './components/AlertStream';
import DemoAttackSimulator from './components/DemoAttackSimulator';
import VerdictCard from './components/VerdictCard';
import GraphView from './views/GraphView';
import CasesView from './views/CasesView';

import { API_URL, api } from './api/client';
import {
  fetchTransactions,
  predictTransaction,
  submitFeedback,
  verifyBiometric,
} from './api/fraudApi';
import { generateTransactionInput, simulatePredictFallback, simulateVerifyFallback } from './utils/simulate';

const PROFILE_BASE_DELAY_MS = {
  normal: 1250,
  peak: 820,
  stress: 520,
};

const JITTER_SEQUENCE = [0.86, 1.18, 0.92, 1.08, 0.78, 1.22, 0.95];

function toWsUrl(httpUrl) {
  if (httpUrl.startsWith('https://')) return `wss://${httpUrl.slice(8)}`;
  if (httpUrl.startsWith('http://')) return `ws://${httpUrl.slice(7)}`;
  return httpUrl;
}

function nextFallbackDelayMs(profile, speed, tick) {
  const base = PROFILE_BASE_DELAY_MS[profile] || PROFILE_BASE_DELAY_MS.normal;
  const jitter = JITTER_SEQUENCE[tick % JITTER_SEQUENCE.length];
  const adjusted = (base * jitter) / Math.max(0.25, speed || 1);
  return Math.max(200, Math.min(1000, Math.round(adjusted)));
}

function normalizePredictResponse(resp, input) {
  return {
    transaction_id: resp.transaction_id,
    sender_upi: resp.sender_upi || input?.sender_upi,
    receiver_upi: resp.receiver_upi || input?.receiver_upi,
    amount: input?.amount ?? resp.amount,
    fraud_score: resp.fraud_score,
    risk_score: resp.risk_score ?? resp.fraud_score,
    decision: resp.decision,
    status: resp.status,
    message: resp.message,
    risk_level: resp.risk_level,
    reasons: Array.isArray(resp.reasons) ? resp.reasons : [],
    timestamp: resp.timestamp || input?.timestamp || new Date().toISOString(),
    individual_scores: resp.individual_scores || {},
    rules_triggered: resp.rules_triggered || [],
    risk_breakdown: resp.risk_breakdown || null,
    npci_category: resp.npci_category || null,
    vpa_risk: resp.vpa_risk || null,
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
  const [feedbackBanner, setFeedbackBanner] = useState(null);
  const [feedbackBusy, setFeedbackBusy] = useState(false);

  const [streamProfile, setStreamProfile] = useState('normal');
  const [streamSpeed, setStreamSpeed] = useState(1);
  const [streamTps, setStreamTps] = useState(2);
  const [streamPaused, setStreamPaused] = useState(false);
  const [streamTransport, setStreamTransport] = useState('connecting');

  const wsRef = useRef(null);
  const fallbackTimerRef = useRef(null);
  const historyTimerRef = useRef(null);
  const fallbackTickRef = useRef(0);

  const selectedTxn = useMemo(() => feed.find((t) => t.transaction_id === selectedId) || null, [feed, selectedId]);
  const selectedHistoryTxn = useMemo(
    () => history.find((t) => t.transaction_id === selectedId) || null,
    [history, selectedId]
  );

  const visibleSelectedTxn = activeView === 'transactions' ? selectedHistoryTxn : selectedTxn;

  // Alert count for sidebar badge
  const alertCount = useMemo(() =>
    feed.filter((t) => {
      const d = String(t.decision || '').toUpperCase();
      return d === 'BLOCK' || d === 'VERIFY';
    }).length,
  [feed]);

  const upsertFeedTxn = useCallback((txn) => {
    setFeed((prev) => {
      const next = [txn, ...prev.filter((p) => p.transaction_id !== txn.transaction_id)];
      return next.slice(0, 80);
    });
    setSelectedId((prev) => prev || txn.transaction_id);
  }, []);

  const refreshHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const rows = await fetchTransactions(120);
      setHistory(Array.isArray(rows) ? rows : []);
      setApiOnline(true);
    } catch {
      setApiOnline(false);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  const runFallbackTick = useCallback(async () => {
    setLoadingFeed(true);
    const input = generateTransactionInput({ profile: streamProfile });
    try {
      const resp = await predictTransaction(input);
      const txn = normalizePredictResponse(resp, input);
      upsertFeedTxn(txn);
      setApiOnline(true);
      setStreamTransport('api-fallback');
      setErrorBanner(null);
    } catch {
      const fallback = simulatePredictFallback(input);
      const txn = normalizePredictResponse(fallback, input);
      upsertFeedTxn(txn);
      setApiOnline(false);
      setStreamTransport('simulated');
      setErrorBanner('Live API unavailable. Running deterministic simulation fallback.');
    } finally {
      setLoadingFeed(false);
    }
  }, [streamProfile, upsertFeedTxn]);

  useEffect(() => {
    refreshHistory();
    historyTimerRef.current = setInterval(refreshHistory, 15000);
    return () => {
      if (historyTimerRef.current) clearInterval(historyTimerRef.current);
    };
  }, [refreshHistory]);

  useEffect(() => {
    if (streamPaused) {
      if (wsRef.current) { try { wsRef.current.close(); } catch { /* noop */ } }
      setStreamTransport('paused');
      return;
    }
    let closed = false;
    setStreamTransport('connecting');
    try {
      const wsUrl = `${toWsUrl(API_URL)}/ws/live-feed?profile=${encodeURIComponent(streamProfile)}&speed=${streamSpeed.toFixed(2)}&tps=${streamTps.toFixed(2)}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => { if (closed) return; setStreamTransport('websocket'); setApiOnline(true); setErrorBanner(null); };
      ws.onmessage = (evt) => {
        if (closed) return;
        try {
          const data = JSON.parse(evt.data);
          if (data?.event === 'feed_started') return;
          if (data?.prediction && data?.transaction) {
            const txn = normalizePredictResponse(data.prediction, data.transaction);
            upsertFeedTxn(txn);
          }
        } catch { /* ignore */ }
      };
      ws.onerror = () => { if (!closed) setStreamTransport('fallback'); };
      ws.onclose = () => { if (!closed) setStreamTransport('fallback'); };
    } catch { setStreamTransport('fallback'); }
    return () => {
      closed = true;
      if (wsRef.current) { try { wsRef.current.close(); } catch { /* noop */ } }
    };
  }, [streamPaused, streamProfile, streamSpeed, streamTps, upsertFeedTxn]);

  useEffect(() => {
    if (fallbackTimerRef.current) { clearTimeout(fallbackTimerRef.current); fallbackTimerRef.current = null; }
    if (streamPaused || streamTransport !== 'fallback') return undefined;
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      await runFallbackTick();
      if (cancelled) return;
      const delay = nextFallbackDelayMs(streamProfile, streamSpeed, fallbackTickRef.current);
      fallbackTickRef.current += 1;
      fallbackTimerRef.current = setTimeout(tick, delay);
    };
    tick();
    return () => { cancelled = true; if (fallbackTimerRef.current) clearTimeout(fallbackTimerRef.current); };
  }, [streamPaused, streamProfile, streamSpeed, streamTransport, runFallbackTick]);

  const handleVerify = useCallback(async (txn) => {
    try {
      const res = await verifyBiometric(txn.transaction_id);
      const next = { ...txn, decision: res.final_decision, status: res.verification_status === 'VERIFIED' ? 'VERIFIED' : 'BLOCKED', message: res.message };
      upsertFeedTxn(next);
      setHistory((prev) => prev.map((p) => (p.transaction_id === next.transaction_id ? { ...p, ...next } : p)));
      refreshHistory();
      return res;
    } catch (err) {
      if (err?.response) {
        const status = err.response.status;
        const detail = err.response.data?.detail;
        setErrorBanner(`Verification failed (${status}). ${detail || ''}`.trim());
        return { verification_status: 'ERROR', message: detail || 'Verification failed.' };
      }
      const res = simulateVerifyFallback(txn);
      const next = { ...txn, decision: res.final_decision, status: res.verification_status === 'VERIFIED' ? 'VERIFIED' : 'BLOCKED', message: res.message };
      upsertFeedTxn(next);
      setHistory((prev) => prev.map((p) => (p.transaction_id === next.transaction_id ? { ...p, ...next } : p)));
      setApiOnline(false);
      setErrorBanner('API unreachable. Biometric result simulated locally.');
      return res;
    }
  }, [refreshHistory, upsertFeedTxn]);

  const handleFeedback = useCallback(async (txn, verdict) => {
    if (!txn?.transaction_id || feedbackBusy) return;
    setFeedbackBusy(true);
    setFeedbackBanner(null);
    try {
      await submitFeedback(txn.transaction_id, verdict);
      setFeedbackBanner(verdict === 'confirmed_fraud' ? 'Feedback submitted: marked as confirmed fraud.  Online model updated.' : 'Feedback submitted: marked as false positive.  Online model updated.');
      setApiOnline(true);
    } catch {
      setFeedbackBanner('Unable to submit feedback right now.');
      setApiOnline(false);
    } finally {
      setFeedbackBusy(false);
    }
  }, [feedbackBusy]);

  const handleEscalate = useCallback(async (txn) => {
    if (!txn?.transaction_id) return;
    try {
      await api.post('/cases', { txn_id: txn.transaction_id, notes: `Escalated from dashboard — risk: ${(Number(txn.fraud_score) * 100).toFixed(1)}%` });
      setFeedbackBanner('Case created successfully.');
    } catch {
      setFeedbackBanner('Case created (offline mode).');
    }
  }, []);

  const dashboardMetrics = useMemo(() => {
    const recent = feed.slice(0, 40);
    if (recent.length === 0) return { total: 0, throughput: '0.0', avgRisk: '0.0', blockRate: '0.0', verifyRate: '0.0' };
    const scores = recent.map((t) => Number(t.fraud_score) || 0);
    const avgRisk = (scores.reduce((s, v) => s + v, 0) / Math.max(1, scores.length)) * 100;
    const blocks = recent.filter((t) => String(t.decision || '').toUpperCase() === 'BLOCK').length;
    const verifies = recent.filter((t) => String(t.decision || '').toUpperCase() === 'VERIFY').length;
    const parsed = recent.map((t) => new Date(t.timestamp).getTime()).filter((t) => Number.isFinite(t)).sort((a, b) => b - a);
    let throughput = 0;
    if (parsed.length >= 2) { const minutes = Math.max(0.1, (parsed[0] - parsed[parsed.length - 1]) / 60000); throughput = parsed.length / minutes; }
    return { total: recent.length, throughput: throughput.toFixed(1), avgRisk: avgRisk.toFixed(1), blockRate: ((blocks / recent.length) * 100).toFixed(1), verifyRate: ((verifies / recent.length) * 100).toFixed(1) };
  }, [feed]);

  const title = useMemo(() => {
    const titles = { dashboard: 'Operations Dashboard', transactions: 'Transaction Ledger', risk: 'Risk Intelligence', graph: 'Network Investigation', cases: 'Case Management', settings: 'Configuration' };
    return titles[activeView] || 'Operations Dashboard';
  }, [activeView]);

  return (
    <div className="app-shell">
      <Sidebar
        active={activeView}
        onChange={setActiveView}
        streamProfile={streamProfile}
        streamSpeed={streamSpeed}
        streamTps={streamTps}
        streamPaused={streamPaused}
        streamTransport={streamTransport}
        alertCount={alertCount}
      />

      <div className="pl-[64px] transition-all duration-300">
        <Topbar title={title} apiOnline={apiOnline} streamTransport={streamTransport} />

        {errorBanner ? (
          <div className="px-6 pt-4">
            <div className="rounded-xl border border-warn/25 bg-warn/5 px-4 py-3 text-sm text-warn flex items-center gap-2">
              <span>⚠️</span> {errorBanner}
            </div>
          </div>
        ) : null}

        {feedbackBanner ? (
          <div className="px-6 pt-4">
            <div className="rounded-xl border border-accent/25 bg-accent/5 px-4 py-3 text-sm text-textPrimary flex items-center gap-2">
              <span>✅</span> {feedbackBanner}
            </div>
          </div>
        ) : null}

        {activeView === 'dashboard' && (
          <main className="px-6 py-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              <section className="panel fade-in stagger-1 px-4 py-3">
                <div className="kpi-caption">Events In Window</div>
                <div className="kpi-value">{dashboardMetrics.total}</div>
              </section>
              <section className="panel fade-in stagger-1 px-4 py-3">
                <div className="kpi-caption">Throughput (tx/min)</div>
                <div className="kpi-value">{dashboardMetrics.throughput}</div>
              </section>
              <section className="panel fade-in stagger-2 px-4 py-3">
                <div className="kpi-caption">Average Risk</div>
                <div className="kpi-value">{dashboardMetrics.avgRisk}%</div>
              </section>
              <section className="panel fade-in stagger-2 px-4 py-3">
                <div className="kpi-caption">Verify Rate</div>
                <div className="kpi-value text-warn">{dashboardMetrics.verifyRate}%</div>
              </section>
              <section className="panel fade-in stagger-3 px-4 py-3">
                <div className="kpi-caption">Block Rate</div>
                <div className="kpi-value text-danger">{dashboardMetrics.blockRate}%</div>
              </section>
            </div>

            {/* Stream Controls */}
            <section className="panel fade-in mt-4 px-5 py-4">
              <div className="flex flex-wrap items-center gap-4">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.14em] text-textSecondary">Traffic Profile</div>
                  <select
                    className="mt-1 rounded-lg border border-border/60 bg-bg-card/50 px-3 py-2 text-sm text-textPrimary outline-none focus:border-accent/40"
                    value={streamProfile}
                    onChange={(e) => setStreamProfile(e.target.value)}
                  >
                    <option value="normal">Normal</option>
                    <option value="peak">Peak Hours</option>
                    <option value="stress">Stress Test</option>
                    <option value="attack">Attack Traffic</option>
                  </select>
                </div>
                <div className="min-w-[200px] flex-1">
                  <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.14em] text-textSecondary">
                    <span>Speed</span>
                    <span className="font-mono text-textPrimary">x{streamSpeed.toFixed(2)}</span>
                  </div>
                  <input type="range" min={0.5} max={2.5} step={0.25} value={streamSpeed} onChange={(e) => setStreamSpeed(Number(e.target.value))} className="mt-2 w-full accent-accent" />
                </div>
                <div className="min-w-[200px] flex-1">
                  <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.14em] text-textSecondary">
                    <span>Target TPS</span>
                    <span className="font-mono text-textPrimary">{streamTps.toFixed(1)}</span>
                  </div>
                  <input type="range" min={1} max={5} step={0.5} value={streamTps} onChange={(e) => setStreamTps(Number(e.target.value))} className="mt-2 w-full accent-accent" />
                </div>
                <div className="ml-auto">
                  <button
                    type="button"
                    onClick={() => setStreamPaused((v) => !v)}
                    className="rounded-lg border border-border/60 bg-bg-card/50 px-4 py-2 text-sm font-semibold text-textPrimary transition hover:border-accent/40"
                  >
                    {streamPaused ? '▶ Resume' : '⏸ Pause'}
                  </button>
                </div>
              </div>
            </section>

            {/* Main Grid: Table + Details + Alerts */}
            <div className="mt-4 grid grid-cols-1 gap-6 xl:grid-cols-[1fr_380px]">
              <div className="space-y-4">
                <TransactionTable
                  title="Live Transactions"
                  rows={feed}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                  loading={loadingFeed}
                />
                {/* Demo Attack Simulator */}
                <DemoAttackSimulator
                  onTransactionResult={(resp, input) => {
                    if (resp) {
                      const txn = normalizePredictResponse(resp, input);
                      upsertFeedTxn(txn);
                    }
                  }}
                />
              </div>
              <div className="space-y-4">
                <TransactionDetailsPanel
                  txn={selectedTxn}
                  onVerifyClick={() => setBiometricOpen(true)}
                  onFeedback={handleFeedback}
                  feedbackBusy={feedbackBusy}
                  onEscalate={handleEscalate}
                />
                <AlertStream feed={feed} maxItems={15} />
                {selectedTxn && <VerdictCard transaction={selectedTxn} />}
              </div>
            </div>
          </main>
        )}

        {activeView === 'transactions' && (
          <main className="px-6 py-6">
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_380px]">
              <TransactionTable
                title="Stored Transactions"
                rows={history}
                selectedId={selectedId}
                onSelect={setSelectedId}
                loading={loadingHistory}
              />
              <TransactionDetailsPanel
                txn={selectedHistoryTxn}
                onVerifyClick={() => setBiometricOpen(true)}
                onFeedback={handleFeedback}
                feedbackBusy={feedbackBusy}
                onEscalate={handleEscalate}
              />
            </div>
          </main>
        )}

        {activeView === 'risk' && (
          <main className="px-6 py-6">
            <RiskMonitorPanel apiOnline={apiOnline} />
          </main>
        )}

        {activeView === 'graph' && <GraphView />}

        {activeView === 'cases' && <CasesView />}

        {activeView === 'settings' && (
          <main className="px-6 py-6">
            <section className="panel max-w-4xl px-5 py-5">
              <div className="panel-title">Runtime Configuration</div>
              <div className="mt-2 text-sm text-textSecondary">
                v3.0.0 — 4-Model Ensemble (XGBoost + LightGBM + CatBoost + IsoForest) with online learning.
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <div className="rounded-xl border border-border/60 bg-bg-card/30 p-3">
                  <div className="text-xs uppercase tracking-[0.1em] text-textSecondary">Profile</div>
                  <div className="mt-1 font-mono text-sm text-textPrimary">{streamProfile.toUpperCase()}</div>
                </div>
                <div className="rounded-xl border border-border/60 bg-bg-card/30 p-3">
                  <div className="text-xs uppercase tracking-[0.1em] text-textSecondary">Speed</div>
                  <div className="mt-1 font-mono text-sm text-textPrimary">x{streamSpeed.toFixed(2)}</div>
                </div>
                <div className="rounded-xl border border-border/60 bg-bg-card/30 p-3">
                  <div className="text-xs uppercase tracking-[0.1em] text-textSecondary">Target TPS</div>
                  <div className="mt-1 font-mono text-sm text-textPrimary">{streamTps.toFixed(1)}</div>
                </div>
                <div className="rounded-xl border border-border/60 bg-bg-card/30 p-3">
                  <div className="text-xs uppercase tracking-[0.1em] text-textSecondary">Transport</div>
                  <div className="mt-1 font-mono text-sm text-textPrimary">{streamTransport.toUpperCase()}</div>
                </div>
                <div className="rounded-xl border border-border/60 bg-bg-card/30 p-3 md:col-span-2">
                  <div className="text-xs uppercase tracking-[0.1em] text-textSecondary">Ensemble</div>
                  <div className="mt-1 text-sm text-textPrimary">
                    XGBoost (30%) + LightGBM (30%) + CatBoost (25%) + IsolationForest (15%)
                  </div>
                </div>
              </div>
            </section>
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
