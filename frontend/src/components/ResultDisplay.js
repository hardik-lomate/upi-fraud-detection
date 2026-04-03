import React, { useState } from 'react';
import FraudGauge from './FraudGauge';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function ResultDisplay({ result }) {
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  const getColor = (decision) => {
    switch (decision) {
      case 'ALLOW': return '#22c55e';
      case 'FLAG': return '#f59e0b';
      case 'BLOCK': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const submitFeedback = async (verdict) => {
    setFeedbackLoading(true);
    try {
      await axios.post(`${API_URL}/feedback`, {
        transaction_id: result.transaction_id,
        analyst_verdict: verdict,
      });
      setFeedbackSent(true);
    } catch (err) {
      console.error('Feedback failed:', err);
    }
    setFeedbackLoading(false);
  };

  const rb = result.risk_breakdown;

  return (
    <div className="card result-card" style={{ borderLeft: `4px solid ${getColor(result.decision)}` }}>
      {/* Fraud Gauge — hero element */}
      <FraudGauge score={result.fraud_score} decision={result.decision} />

      {/* Risk Breakdown */}
      {rb && (
        <div className="section risk-breakdown-grid">
          <h3>📊 Risk Breakdown</h3>
          <div className="risk-bars">
            {[
              { label: 'Behavioral', value: rb.behavioral, color: '#8b5cf6' },
              { label: 'Temporal', value: rb.temporal, color: '#06b6d4' },
              { label: 'Network', value: rb.network, color: '#f97316' },
              { label: 'Device', value: rb.device, color: '#ec4899' },
            ].map(({ label, value, color }) => (
              <div key={label} className="risk-bar-item">
                <div className="risk-bar-header">
                  <span>{label}</span>
                  <span style={{ fontWeight: 'bold' }}>{value}%</span>
                </div>
                <div className="risk-bar-bg">
                  <div className="risk-bar-fill" style={{ width: `${value}%`, backgroundColor: color }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Model Scores */}
      {result.individual_scores && Object.keys(result.individual_scores).length > 0 && (
        <div className="section">
          <h3>🤖 Model Scores</h3>
          <div className="model-scores">
            {Object.entries(result.individual_scores).map(([model, score]) => (
              <div key={model} className="model-score-item">
                <span className="model-name">{model}</span>
                <div className="score-bar-bg">
                  <div className="score-bar" style={{
                    width: `${score * 100}%`,
                    backgroundColor: score > 0.7 ? '#ef4444' : score > 0.3 ? '#f59e0b' : '#22c55e'
                  }}/>
                </div>
                <span className="model-score-val">{(score * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SHAP Reasons */}
      {result.reasons?.length > 0 && (
        <div className="section">
          <h3>💡 Why This Decision</h3>
          <ul className="reasons-list">
            {result.reasons.map((reason, i) => (
              <li key={i} className={reason.startsWith('↑') ? 'risk-up' : 'risk-down'}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Rules */}
      {result.rules_triggered?.length > 0 && (
        <div className="section">
          <h3>📋 Rules Triggered</h3>
          {result.rules_triggered.map((rule, i) => (
            <div key={i} className="rule-item">
              <span className={`rule-badge rule-${rule.action.toLowerCase()}`}>{rule.action}</span>
              <span className="rule-name">{rule.rule_name}</span>
              <span className="rule-reason">{rule.reason}</span>
            </div>
          ))}
        </div>
      )}

      {/* Device Anomalies */}
      {result.device_anomalies?.length > 0 && (
        <div className="section">
          <h3>📱 Device Anomalies</h3>
          {result.device_anomalies.map((a, i) => (
            <div key={i} className={`anomaly-item severity-${a.severity.toLowerCase()}`}>
              <span className="anomaly-type">{a.type}</span>
              <span className="anomaly-detail">{a.detail}</span>
            </div>
          ))}
        </div>
      )}

      {/* Graph Info */}
      {result.graph_info && (
        <div className="section">
          <h3>🕸️ Network Analysis</h3>
          <div className="graph-grid">
            <div><span className="label">Out-degree</span><span className="value">{result.graph_info.out_degree}</span></div>
            <div><span className="label">In-degree</span><span className="value">{result.graph_info.in_degree}</span></div>
            <div><span className="label">PageRank</span><span className="value">{result.graph_info.pagerank?.toFixed(6)}</span></div>
            <div><span className="label">Cycles</span><span className="value">{result.graph_info.cycle_count}</span></div>
            {result.graph_info.is_mule_suspect && <div className="badge-alert">🔴 Mule Suspect</div>}
          </div>
        </div>
      )}

      <p className="result-message">{result.message}</p>
      <p className="model-version">Model v{result.model_version} · {result.models_used?.join(' + ')}</p>

      {/* Feedback */}
      <div className="section feedback-section">
        <h3>🏷️ Submit Feedback</h3>
        {feedbackSent ? (
          <p style={{ color: '#22c55e' }}>✅ Feedback submitted — thank you!</p>
        ) : (
          <div className="feedback-buttons">
            <button onClick={() => submitFeedback('confirmed_fraud')} disabled={feedbackLoading}
              className="feedback-btn feedback-fraud">🚨 Confirmed Fraud</button>
            <button onClick={() => submitFeedback('false_positive')} disabled={feedbackLoading}
              className="feedback-btn feedback-fp">⚠️ False Positive</button>
            <button onClick={() => submitFeedback('true_negative')} disabled={feedbackLoading}
              className="feedback-btn feedback-legit">✅ Legitimate</button>
          </div>
        )}
      </div>
    </div>
  );
}

export default ResultDisplay;
