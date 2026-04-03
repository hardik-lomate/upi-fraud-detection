import React from 'react';

function TransactionHistory({ history }) {
  const getDecisionColor = (decision) => {
    switch (decision) {
      case 'ALLOW':
        return '#22c55e';
      case 'FLAG':
        return '#f59e0b';
      case 'BLOCK':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };

  return (
    <div className="card">
      <h2>📊 Transaction History</h2>
      {history.length === 0 ? (
        <p className="empty-state">
          No transactions yet. Submit one to get started!
        </p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Amount</th>
                <th>Score</th>
                <th>Decision</th>
              </tr>
            </thead>
            <tbody>
              {history.map((txn, idx) => (
                <tr key={idx}>
                  <td title={txn.transaction_id}>
                    {txn.transaction_id.substring(0, 15)}...
                  </td>
                  <td>₹{txn.amount.toLocaleString()}</td>
                  <td>{(txn.fraud_score * 100).toFixed(1)}%</td>
                  <td>
                    <span
                      className="badge"
                      style={{
                        backgroundColor: getDecisionColor(txn.decision),
                      }}
                    >
                      {txn.decision}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default TransactionHistory;
