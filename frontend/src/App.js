import React, { useState, useEffect, useCallback } from 'react';
import TransactionForm from './components/TransactionForm';
import ResultDisplay from './components/ResultDisplay';
import TransactionHistory from './components/TransactionHistory';
import MonitoringPanel from './components/MonitoringPanel';
import axios from 'axios';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState(null);
  const [backendOnline, setBackendOnline] = useState(true);
  const [activeTab, setActiveTab] = useState('predict');

  const fetchHistory = useCallback(async () => {
    try {
      const res = await axios.get(`${API_URL}/transactions?limit=30`, { timeout: 5000 });
      setHistory(res.data);
      setBackendOnline(true);
    } catch (err) {
      if (err.code === 'ERR_NETWORK' || err.code === 'ECONNABORTED') {
        setBackendOnline(false);
      }
    }
  }, []);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  const handleSubmit = async (transaction) => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_URL}/predict`, transaction, { timeout: 10000 });
      setResult(res.data);
      setBackendOnline(true);
      fetchHistory();
    } catch (err) {
      if (err.code === 'ERR_NETWORK' || err.code === 'ECONNABORTED') {
        setError('Backend unreachable. Ensure FastAPI is running on port 8000.');
        setBackendOnline(false);
      } else if (err.response?.status === 422) {
        const detail = err.response.data?.detail;
        const msg = Array.isArray(detail)
          ? detail.map((d) => `${d.loc?.join('.')}: ${d.msg}`).join('; ')
          : 'Invalid input.';
        setError(msg);
      } else {
        setError(err.response?.data?.detail || 'Prediction failed.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = () => { setError(null); setBackendOnline(true); fetchHistory(); };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>🛡️ UPI Fraud Detection System</h1>
          <p className="subtitle">v2.0 — Ensemble ML · SHAP · Graph Analysis · Real-time Monitoring</p>
          {!backendOnline && (
            <div className="status-bar offline">
              ⚠️ Backend offline — <button onClick={handleRetry} className="retry-link">Retry</button>
            </div>
          )}
        </div>
        <nav className="tab-nav">
          {['predict', 'monitor'].map(tab => (
            <button key={tab} className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}>
              {tab === 'predict' ? '🔍 Predict' : '📊 Monitor'}
            </button>
          ))}
        </nav>
      </header>

      <main className="app-main">
        {activeTab === 'predict' ? (
          <>
            <div className="left-panel">
              <TransactionForm onSubmit={handleSubmit} loading={loading} disabled={!backendOnline} />
              {error && (
                <div className="error-banner">
                  <span>{error}</span>
                  <button onClick={handleRetry} className="retry-btn">Retry</button>
                </div>
              )}
              {result && <ResultDisplay result={result} />}
            </div>
            <div className="right-panel">
              <TransactionHistory history={history} />
            </div>
          </>
        ) : (
          <div className="full-panel">
            <MonitoringPanel apiUrl={API_URL} />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
