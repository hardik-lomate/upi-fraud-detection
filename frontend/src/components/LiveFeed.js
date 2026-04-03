import React, { useEffect, useRef, useState } from 'react';

const API_WS = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws/live-feed';

function LiveFeed() {
  const [feed, setFeed] = useState([]);
  const [paused, setPaused] = useState(false);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const pausedRef = useRef(false);
  const containerRef = useRef(null);

  useEffect(() => { pausedRef.current = paused; }, [paused]);

  useEffect(() => {
    const ws = new WebSocket(API_WS);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (e) => {
      if (pausedRef.current) return;
      try {
        const msg = JSON.parse(e.data);
        setFeed(prev => [msg, ...prev].slice(0, 20));
      } catch {}
    };

    return () => ws.close();
  }, []);

  // Auto-scroll
  useEffect(() => {
    if (containerRef.current && !paused) {
      containerRef.current.scrollTop = 0;
    }
  }, [feed, paused]);

  const getRowClass = (decision) => {
    switch (decision) {
      case 'BLOCK': return 'live-row-block';
      case 'FLAG': return 'live-row-flag';
      default: return 'live-row-allow';
    }
  };

  return (
    <div className="card live-feed-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <h2>📡 Live Transaction Feed</h2>
        <div>
          <span style={{ color: connected ? '#22c55e' : '#ef4444', marginRight: '12px', fontSize: '12px' }}>
            ● {connected ? 'Connected' : 'Disconnected'}
          </span>
          <button
            onClick={() => setPaused(!paused)}
            style={{
              padding: '4px 12px', borderRadius: '4px', border: '1px solid #444',
              backgroundColor: paused ? '#22c55e' : '#ef4444', color: '#fff',
              cursor: 'pointer', fontSize: '12px',
            }}
          >
            {paused ? '▶ Resume' : '⏸ Pause'}
          </button>
        </div>
      </div>

      <div ref={containerRef} style={{ maxHeight: '500px', overflowY: 'auto' }}>
        <table className="live-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Sender</th>
              <th>Receiver</th>
              <th>Amount</th>
              <th>Score</th>
              <th>Decision</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {feed.map((item, i) => {
              const p = item.prediction || {};
              const t = item.transaction || {};
              return (
                <tr key={item.seq || i} className={`${getRowClass(p.decision)} live-row-animate`}>
                  <td>{item.seq}</td>
                  <td>{t.sender_upi?.split('@')[0]}</td>
                  <td>{t.receiver_upi?.split('@')[0]}</td>
                  <td>₹{(t.amount || 0).toLocaleString('en-IN')}</td>
                  <td style={{ fontWeight: 'bold' }}>{((p.fraud_score || 0) * 100).toFixed(1)}%</td>
                  <td>
                    <span className={`decision-chip decision-${(p.decision || 'ALLOW').toLowerCase()}`}>
                      {p.decision || '-'}
                    </span>
                  </td>
                  <td>{new Date(item.timestamp).toLocaleTimeString()}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {feed.length === 0 && (
          <p style={{ textAlign: 'center', color: '#888', padding: '40px' }}>
            {connected ? 'Waiting for transactions...' : 'Connecting to live feed...'}
          </p>
        )}
      </div>
    </div>
  );
}

export default LiveFeed;
