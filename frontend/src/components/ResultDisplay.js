import React from 'react';

function ResultDisplay({ result }) {
  const getColor = (decision) => {
    switch (decision) {
      case 'ALLOW': return '#22c55e';
      case 'FLAG': return '#f59e0b';
      case 'BLOCK': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getEmoji = (decision) => {
    switch (decision) {
      case 'ALLOW': return '✅';
      case 'FLAG': return '⚠️';
      case 'BLOCK': return '🚫';
      default: return '❓';
    }
  };

  return (
    <div className="card result-card" style={{ borderLeft: `4px solid ${getColor(result.decision)}` }}>
      <h2>{getEmoji(result.decision)} Prediction Result</h2>

      <div className="result-grid">
        <div className="result-item">
          <span className="label">Transaction ID</span>
          <span className="value">{result.transaction_id}</span>
        </div>
        <div className="result-item">
          <span className="label">Ensemble Score</span>
          <span className="value score" style={{ color: getColor(result.decision) }}>
            {(result.fraud_score * 100).toFixed(1)}%
          </span>
        </div>
        <div className="result-item">
          <span className="label">Decision</span>
          <span className="value decision-badge" style={{ backgroundColor: getColor(result.decision) }}>
            {result.decision}
          </span>
        </div>
        <div className="result-item">
          <span className="label">Risk Level</span>
          <span className="value">{result.risk_level}</span>
        </div>
      </div>

      {/* Individual Model Scores */}
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
      {result.reasons && result.reasons.length > 0 && (
        <div className="section">
          <h3>💡 Why This Decision</h3>
          <ul className="reasons-list">
            {result.reasons.map((reason, i) => (
              <li key={i} className={reason.startsWith('↑') ? 'risk-up' : 'risk-down'}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Rules Triggered */}
      {result.rules_triggered && result.rules_triggered.length > 0 && (
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
      {result.device_anomalies && result.device_anomalies.length > 0 && (
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
            <div><span className="label">PageRank</span><span className="value">{result.graph_info.pagerank.toFixed(6)}</span></div>
            <div><span className="label">Cycles</span><span className="value">{result.graph_info.cycle_count}</span></div>
            {result.graph_info.is_hub && <div className="badge-alert">🔴 Hub Account</div>}
            {result.graph_info.is_mule_suspect && <div className="badge-alert">🔴 Mule Suspect</div>}
          </div>
        </div>
      )}

      <p className="result-message">{result.message}</p>
      <p className="model-version">Model v{result.model_version} · {result.models_used?.join(' + ')}</p>
    </div>
  );
}

export default ResultDisplay;
