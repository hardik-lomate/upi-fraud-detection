import React, { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import axios from 'axios';

const COLORS = { ALLOW: '#22c55e', FLAG: '#f59e0b', BLOCK: '#ef4444' };

function MonitoringPanel({ apiUrl }) {
  const [stats, setStats] = useState(null);
  const [drift, setDrift] = useState(null);
  const [graphStats, setGraphStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchMonitoring = async () => {
    setLoading(true);
    try {
      const [statsRes, driftRes, graphRes] = await Promise.allSettled([
        axios.get(`${apiUrl}/monitoring/stats`, { timeout: 5000 }),
        axios.get(`${apiUrl}/monitoring/drift`, { timeout: 5000 }),
        axios.get(`${apiUrl}/monitoring/graph`, { timeout: 5000 }),
      ]);
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data);
      if (driftRes.status === 'fulfilled') setDrift(driftRes.value.data);
      if (graphRes.status === 'fulfilled') setGraphStats(graphRes.value.data);
    } catch (err) {
      console.error('Monitoring fetch failed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchMonitoring(); }, [apiUrl]);

  if (loading) return <div className="card"><p className="empty-state">Loading monitoring data...</p></div>;

  const pieData = stats?.decision_distribution
    ? Object.entries(stats.decision_distribution).map(([name, value]) => ({ name, value }))
    : [];

  const barData = stats?.decision_distribution
    ? Object.entries(stats.decision_distribution).map(([name, value]) => ({ name, count: value }))
    : [];

  const getDriftColor = (status) => {
    switch (status) {
      case 'STABLE': return '#22c55e';
      case 'WARNING': return '#f59e0b';
      case 'CRITICAL': return '#ef4444';
      default: return '#6b7280';
    }
  };

  return (
    <div className="monitoring-grid">
      {/* Stats Summary */}
      <div className="card">
        <h2>📊 Prediction Statistics</h2>
        {stats && stats.total > 0 ? (
          <>
            <div className="stats-grid">
              <div className="stat-card">
                <span className="stat-value">{stats.total}</span>
                <span className="stat-label">Total Predictions</span>
              </div>
              <div className="stat-card">
                <span className="stat-value">{(stats.mean_score * 100).toFixed(1)}%</span>
                <span className="stat-label">Avg. Fraud Score</span>
              </div>
              <div className="stat-card">
                <span className="stat-value" style={{ color: '#ef4444' }}>{stats.fraud_rate_pct}%</span>
                <span className="stat-label">Block Rate</span>
              </div>
              <div className="stat-card">
                <span className="stat-value">{(stats.max_score * 100).toFixed(1)}%</span>
                <span className="stat-label">Max Score</span>
              </div>
            </div>

            <div className="charts-row">
              <div className="chart-box">
                <h3>Decision Distribution</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                      outerRadius={75} label={({ name, value }) => `${name}: ${value}`}>
                      {pieData.map((entry) => (
                        <Cell key={entry.name} fill={COLORS[entry.name] || '#6b7280'} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="chart-box">
                <h3>Decisions by Count</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={barData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="name" stroke="#94a3b8" />
                    <YAxis stroke="#94a3b8" />
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }} />
                    <Bar dataKey="count">
                      {barData.map((entry) => (
                        <Cell key={entry.name} fill={COLORS[entry.name] || '#6b7280'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </>
        ) : (
          <p className="empty-state">No predictions yet. Submit transactions to see stats.</p>
        )}
      </div>

      {/* Drift Detection */}
      <div className="card">
        <h2>🔬 Model Drift Detection</h2>
        {drift ? (
          <div className="drift-panel">
            <div className="drift-status" style={{ borderLeftColor: getDriftColor(drift.status) }}>
              <span className="drift-badge" style={{ backgroundColor: getDriftColor(drift.status) }}>
                {drift.status}
              </span>
              <span className="drift-message">{drift.message}</span>
            </div>
            {drift.psi !== undefined && (
              <div className="drift-details">
                <div className="stat-card"><span className="stat-value">{drift.psi}</span><span className="stat-label">PSI Score</span></div>
                {drift.reference && (
                  <div className="stat-card"><span className="stat-value">{(drift.reference.mean * 100).toFixed(1)}%</span><span className="stat-label">Reference Mean</span></div>
                )}
                {drift.current && (
                  <div className="stat-card"><span className="stat-value">{(drift.current.mean * 100).toFixed(1)}%</span><span className="stat-label">Current Mean</span></div>
                )}
              </div>
            )}
          </div>
        ) : (
          <p className="empty-state">Drift data unavailable.</p>
        )}
      </div>

      {/* Graph Stats */}
      <div className="card">
        <h2>🕸️ Transaction Graph</h2>
        {graphStats ? (
          <div className="stats-grid">
            <div className="stat-card"><span className="stat-value">{graphStats.total_nodes}</span><span className="stat-label">Nodes (Accounts)</span></div>
            <div className="stat-card"><span className="stat-value">{graphStats.total_edges}</span><span className="stat-label">Edges (Txn Links)</span></div>
            <div className="stat-card"><span className="stat-value">{graphStats.connected_components}</span><span className="stat-label">Components</span></div>
            <div className="stat-card"><span className="stat-value">{graphStats.density?.toFixed(6)}</span><span className="stat-label">Graph Density</span></div>
          </div>
        ) : (
          <p className="empty-state">Graph data unavailable.</p>
        )}
      </div>

      <button onClick={fetchMonitoring} className="submit-btn" style={{ maxWidth: 200 }}>
        🔄 Refresh Data
      </button>
    </div>
  );
}

export default MonitoringPanel;
