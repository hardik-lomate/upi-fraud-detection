import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { BrowserRouter, NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { Activity, BarChart3, RefreshCw, ShieldAlert, Zap } from 'lucide-react';
import DashboardPage from './pages/DashboardPage';
import TransactionsPage from './pages/TransactionsPage';
import AnalyticsPage from './pages/AnalyticsPage';
import TransactionDetailModal from './components/dashboard/TransactionDetailModal';
import {
  fetchMetrics,
  fetchTransactionDetail,
  fetchTransactions,
  mergeLatestTransactions,
  runSimulation,
} from './api/dashboardApi';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard' },
  { to: '/transactions', label: 'Transaction Monitor' },
  { to: '/analytics', label: 'Analytics' },
];

function NavTab({ to, label }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        `rounded-lg px-3 py-2 text-sm font-semibold transition ${
          isActive
            ? 'bg-cyan-400/20 text-cyan-200 ring-1 ring-cyan-300/40'
            : 'text-slate-300 hover:bg-slate-800/70 hover:text-slate-100'
        }`
      }
    >
      {label}
    </NavLink>
  );
}

function App() {
  const [transactions, setTransactions] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [highlightedTransactionId, setHighlightedTransactionId] = useState('');

  const [loadingTransactions, setLoadingTransactions] = useState(true);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [transactionsError, setTransactionsError] = useState('');
  const [metricsError, setMetricsError] = useState('');

  const [decisionFilter, setDecisionFilter] = useState('ALL');

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [selectedTransaction, setSelectedTransaction] = useState(null);

  const [simulationLoading, setSimulationLoading] = useState(false);
  const [simulationMessage, setSimulationMessage] = useState('');
  const clearMessageTimerRef = useRef(null);

  const pushMessage = useCallback((message) => {
    setSimulationMessage(message);
    if (clearMessageTimerRef.current) {
      clearTimeout(clearMessageTimerRef.current);
    }
    clearMessageTimerRef.current = setTimeout(() => setSimulationMessage(''), 5200);
  }, []);

  const loadTransactions = useCallback(async () => {
    setLoadingTransactions(true);
    setTransactionsError('');

    try {
      const rows = await fetchTransactions(180);
      setTransactions(rows);
    } catch (error) {
      const fallback = String(error?.response?.data?.detail || error?.message || 'Unable to fetch transactions.');
      setTransactionsError(fallback);
    } finally {
      setLoadingTransactions(false);
    }
  }, []);

  const loadMetrics = useCallback(async () => {
    setLoadingMetrics(true);
    setMetricsError('');

    try {
      const data = await fetchMetrics();
      setMetrics(data);
    } catch (error) {
      const fallback = String(error?.response?.data?.detail || error?.message || 'Unable to fetch metrics.');
      setMetricsError(fallback);
    } finally {
      setLoadingMetrics(false);
    }
  }, []);

  useEffect(() => {
    loadTransactions();
    loadMetrics();

    const timer = setInterval(() => {
      loadTransactions();
    }, 12000);

    return () => {
      clearInterval(timer);
      if (clearMessageTimerRef.current) clearTimeout(clearMessageTimerRef.current);
    };
  }, [loadTransactions, loadMetrics]);

  const handleRefresh = useCallback(() => {
    loadTransactions();
    loadMetrics();
  }, [loadTransactions, loadMetrics]);

  const handleOpenTransaction = useCallback(async (transaction) => {
    if (transaction?.transaction_id) {
      setHighlightedTransactionId(transaction.transaction_id);
    }
    setDetailOpen(true);
    setDetailLoading(true);
    setDetailError('');
    setSelectedTransaction(transaction);

    try {
      const detail = await fetchTransactionDetail(transaction.transaction_id, transaction);
      if (detail) {
        setSelectedTransaction(detail);
      }
    } catch (error) {
      setDetailError(String(error?.message || 'Unable to load transaction detail.'));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const handleRunSimulation = useCallback(async () => {
    setSimulationLoading(true);
    setTransactionsError('');
    pushMessage('Running simulation...');

    try {
      const result = await runSimulation();
      const rows = Array.isArray(result?.transactions) ? result.transactions : [];
      const latest = mergeLatestTransactions([], rows, 260);
      setTransactions(latest);
      const topRiskRow = [...rows].sort((a, b) => Number(b.risk_score || 0) - Number(a.risk_score || 0))[0];
      const topRiskLatest = [...latest].sort((a, b) => Number(b.risk_score || 0) - Number(a.risk_score || 0))[0];

      const fraudCandidate =
        rows.find((txn) => txn.decision === 'BLOCK')
        || rows.find((txn) => txn.decision === 'STEP-UP')
        || rows.find((txn) => Number(txn.risk_score || 0) >= 0.6)
        || latest.find((txn) => txn.decision === 'BLOCK')
        || latest.find((txn) => txn.decision === 'STEP-UP')
        || topRiskRow
        || topRiskLatest;

      if (fraudCandidate?.transaction_id) {
        setHighlightedTransactionId(fraudCandidate.transaction_id);
        void handleOpenTransaction(fraudCandidate);
        pushMessage(
          `Simulation complete: ${rows.length} transactions from ${result?.source || 'fallback'}. Highlighted high-risk case ${fraudCandidate.transaction_id}.`
        );
      } else {
        pushMessage(`Simulation complete: ${rows.length} transactions from ${result?.source || 'fallback'}.`);
      }
    } catch (error) {
      const fallback = String(error?.response?.data?.detail || error?.message || 'Simulation failed.');
      setTransactionsError(fallback);
    } finally {
      setSimulationLoading(false);
    }
  }, [handleOpenTransaction, pushMessage]);

  const headlineStats = useMemo(() => {
    const total = transactions.length;
    const block = transactions.filter((txn) => txn.decision === 'BLOCK').length;
    const step = transactions.filter((txn) => txn.decision === 'STEP-UP').length;
    const avgRisk =
      total > 0 ? transactions.reduce((acc, txn) => acc + Number(txn.risk_score || 0), 0) / total : 0;

    return {
      total,
      block,
      step,
      avgRisk,
    };
  }, [transactions]);

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-app px-4 pb-8 pt-5 text-slate-100 md:px-6 lg:px-10">
        <div className="mx-auto max-w-7xl space-y-6">
          <header className="rounded-2xl border border-slate-700/60 bg-slate-900/80 p-4 shadow-[0_14px_40px_rgba(2,6,23,0.5)]">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="space-y-2">
                <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-cyan-200">
                  <Activity className="h-3.5 w-3.5" />
                  Real-time UPI Fraud Intelligence
                </div>
                <h1 className="text-2xl font-bold tracking-tight text-slate-50 md:text-3xl">
                  UPI Risk Intelligence Console
                </h1>
                <p className="text-sm text-slate-400">
                  Real-time visibility into risk scoring, decisioning, and model intelligence.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={handleRefresh}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-400 hover:text-white"
                >
                  <RefreshCw className="h-4 w-4" />
                  Refresh
                </button>
                <button
                  type="button"
                  disabled={simulationLoading}
                  onClick={handleRunSimulation}
                  className="inline-flex items-center gap-2 rounded-xl border border-emerald-300/70 bg-gradient-to-r from-emerald-500/25 to-cyan-500/20 px-4 py-2.5 text-sm font-semibold text-emerald-100 shadow-[0_10px_24px_rgba(16,185,129,0.2)] transition hover:border-emerald-200 hover:from-emerald-500/35 hover:to-cyan-500/30 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Zap className="h-4 w-4" />
                  {simulationLoading ? 'Running Simulation...' : 'Run Simulation'}
                </button>
              </div>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-700/80 bg-slate-950/60 p-3">
                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Live Volume</p>
                <p className="mt-1 text-lg font-semibold text-slate-100">{headlineStats.total}</p>
              </div>
              <div className="rounded-xl border border-slate-700/80 bg-slate-950/60 p-3">
                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Fraud Pressure</p>
                <p className="mt-1 inline-flex items-center gap-2 text-lg font-semibold text-rose-200">
                  <ShieldAlert className="h-4 w-4" />
                  {headlineStats.block + headlineStats.step}
                </p>
              </div>
              <div className="rounded-xl border border-slate-700/80 bg-slate-950/60 p-3">
                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Average Risk</p>
                <p className="mt-1 inline-flex items-center gap-2 text-lg font-semibold text-amber-200">
                  <Activity className="h-4 w-4" />
                  {(headlineStats.avgRisk * 100).toFixed(1)}%
                </p>
              </div>
            </div>

            {simulationMessage ? (
              <div className="mt-4 rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-sm text-cyan-100">
                {simulationMessage}
              </div>
            ) : null}
            {metricsError ? (
              <div className="mt-3 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-100">
                Metrics endpoint notice: {metricsError}
              </div>
            ) : null}
          </header>

          <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-700/60 bg-slate-900/70 p-2">
            <div className="flex flex-wrap items-center gap-1">
              {NAV_ITEMS.map((item) => (
                <NavTab key={item.to} to={item.to} label={item.label} />
              ))}
            </div>
            <div className="inline-flex items-center gap-2 rounded-lg bg-slate-950/60 px-3 py-2 text-xs text-slate-400">
              <BarChart3 className="h-3.5 w-3.5" />
              {loadingMetrics ? 'Loading model metrics...' : `Metric source: ${metrics?._source || 'N/A'}`}
            </div>
          </div>

          <main>
            <Routes>
              <Route
                path="/"
                element={
                  <DashboardPage
                    transactions={transactions}
                    metrics={metrics}
                    loading={loadingTransactions}
                    error={transactionsError}
                    onSelectTransaction={handleOpenTransaction}
                    onRefresh={handleRefresh}
                    highlightedTransactionId={highlightedTransactionId}
                  />
                }
              />
              <Route
                path="/transactions"
                element={
                  <TransactionsPage
                    transactions={transactions}
                    loading={loadingTransactions}
                    error={transactionsError}
                    filter={decisionFilter}
                    onFilterChange={setDecisionFilter}
                    onSelectTransaction={handleOpenTransaction}
                    highlightedTransactionId={highlightedTransactionId}
                  />
                }
              />
              <Route
                path="/analytics"
                element={<AnalyticsPage transactions={transactions} metrics={metrics} />}
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>

        <TransactionDetailModal
          open={detailOpen}
          transaction={selectedTransaction}
          loading={detailLoading}
          error={detailError}
          onClose={() => {
            setDetailOpen(false);
            setDetailError('');
          }}
        />
      </div>
    </BrowserRouter>
  );
}

export default App;
