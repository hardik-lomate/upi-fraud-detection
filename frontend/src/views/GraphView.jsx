import React, { useState, useEffect, useRef, useCallback } from 'react';
import { fetchGraphSubgraph, fetchGraphCommunities, markMule } from '../api/fraudApi';

/* ─── Force-directed graph with D3-free SVG implementation ──────── */

function forceSimulation(nodes, edges, width, height, iterations = 80) {
  const nodeMap = {};
  nodes.forEach((n, i) => {
    n.x = width / 2 + (Math.cos(i * 2.39996) * 150);
    n.y = height / 2 + (Math.sin(i * 2.39996) * 150);
    n.vx = 0;
    n.vy = 0;
    nodeMap[n.id] = n;
  });

  for (let iter = 0; iter < iterations; iter++) {
    const alpha = 1 - iter / iterations;
    // Repulsion
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[j].x - nodes[i].x;
        const dy = nodes[j].y - nodes[i].y;
        const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
        const force = (-300 * alpha) / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        nodes[i].vx -= fx;
        nodes[i].vy -= fy;
        nodes[j].vx += fx;
        nodes[j].vy += fy;
      }
    }
    // Attraction (edges)
    edges.forEach(e => {
      const s = nodeMap[e.source];
      const t = nodeMap[e.target];
      if (!s || !t) return;
      const dx = t.x - s.x;
      const dy = t.y - s.y;
      const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const force = (dist - 80) * 0.04 * alpha;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      s.vx += fx;
      s.vy += fy;
      t.vx -= fx;
      t.vy -= fy;
    });
    // Center gravity
    nodes.forEach(n => {
      n.vx += (width / 2 - n.x) * 0.01 * alpha;
      n.vy += (height / 2 - n.y) * 0.01 * alpha;
      n.x += n.vx * 0.8;
      n.y += n.vy * 0.8;
      n.vx *= 0.6;
      n.vy *= 0.6;
      n.x = Math.max(40, Math.min(width - 40, n.x));
      n.y = Math.max(40, Math.min(height - 40, n.y));
    });
  }
  return { nodes, edges };
}

function nodeColor(node, centerId) {
  if (node.id === centerId) return '#6C47FF';
  if (node.is_mule_suspect) return '#E24B4A';
  if ((node.degree || 0) >= 6) return '#EF9F27';
  return '#1E2235';
}

function nodeStroke(node, centerId) {
  if (node.id === centerId) return '#A78BFA';
  if (node.is_mule_suspect) return '#F87171';
  if ((node.degree || 0) >= 6) return '#FCD34D';
  return '#3B3F5C';
}

function edgeColor(edge) {
  const amt = edge.total_amount || 0;
  if (amt > 50000) return '#E24B4A';
  if (amt > 10000) return '#EF9F27';
  return '#252A40';
}

export default function GraphView() {
  const [upiSearch, setUpiSearch] = useState('');
  const [depth, setDepth] = useState(2);
  const [graphData, setGraphData] = useState(null);
  const [communities, setCommunities] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [layoutData, setLayoutData] = useState(null);
  const svgRef = useRef(null);

  const WIDTH = 800;
  const HEIGHT = 550;

  // Load communities on mount
  useEffect(() => {
    fetchGraphCommunities()
      .then(d => setCommunities(d))
      .catch(() => {});
  }, []);

  const doSearch = useCallback(async (searchId) => {
    const id = searchId || upiSearch.trim();
    if (!id) return;
    setLoading(true);
    setError('');
    setSelectedNode(null);
    try {
      const data = await fetchGraphSubgraph(id, depth);
      setGraphData(data);
      if (data.nodes && data.nodes.length > 0) {
        const sim = forceSimulation(
          data.nodes.map(n => ({ ...n })),
          data.edges || [],
          WIDTH,
          HEIGHT,
        );
        setLayoutData(sim);
      } else {
        setLayoutData(null);
        setError('No graph data found for this UPI ID. Try a different one.');
      }
    } catch (e) {
      setError('Failed to fetch graph data. Backend may be offline.');
    }
    setLoading(false);
  }, [upiSearch, depth]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') doSearch();
  };

  const handleMarkMule = async (nodeId) => {
    try {
      await markMule(nodeId, 'Analyst flagged via graph investigation');
      doSearch(upiSearch);
    } catch {}
  };

  const selNodeData = layoutData?.nodes?.find(n => n.id === selectedNode);
  const centerNode = upiSearch.trim();

  return (
    <main className="px-6 py-6" style={{ display: 'flex', gap: 24, height: 'calc(100vh - 80px)' }}>
      {/* Left: Graph Canvas */}
      <div style={{ flex: '1 1 70%', display: 'flex', flexDirection: 'column' }}>
        <div className="panel px-5 py-4" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <input
              type="text"
              placeholder="Enter UPI ID (e.g., user_0001@upi)"
              value={upiSearch}
              onChange={e => setUpiSearch(e.target.value)}
              onKeyDown={handleKeyDown}
              className="input"
              style={{ flex: 1, background: '#0D0E14', border: '1px solid #252A40', borderRadius: 8, padding: '10px 14px', color: '#E0E0E6', fontSize: 14 }}
            />
            <select
              value={depth}
              onChange={e => setDepth(Number(e.target.value))}
              style={{ background: '#0D0E14', border: '1px solid #252A40', borderRadius: 8, padding: '10px 12px', color: '#E0E0E6', fontSize: 13 }}
            >
              <option value={1}>1 hop</option>
              <option value={2}>2 hops</option>
              <option value={3}>3 hops</option>
            </select>
            <button
              onClick={() => doSearch()}
              disabled={loading || !upiSearch.trim()}
              className="btn-primary"
              style={{ padding: '10px 24px', borderRadius: 8, background: loading ? '#3B3F5C' : 'linear-gradient(135deg, #6C47FF, #A78BFA)', border: 'none', color: '#fff', fontWeight: 600, cursor: loading ? 'wait' : 'pointer', fontSize: 14 }}
            >
              {loading ? 'Exploring…' : '🔍 Explore'}
            </button>
          </div>
        </div>

        {/* SVG Canvas */}
        <div className="panel" style={{ flex: 1, overflow: 'hidden', position: 'relative', borderRadius: 12 }}>
          {!layoutData && !loading && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', opacity: 0.5 }}>
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#6C47FF" strokeWidth="1.5">
                <circle cx="12" cy="5" r="3" /><circle cx="5" cy="19" r="3" /><circle cx="19" cy="19" r="3" />
                <line x1="12" y1="8" x2="5" y2="16" /><line x1="12" y1="8" x2="19" y2="16" /><line x1="5" y1="19" x2="19" y2="19" />
              </svg>
              <p style={{ marginTop: 16, color: '#8B8FA3', fontSize: 14 }}>Enter a UPI ID above to explore the transaction network</p>
            </div>
          )}

          {loading && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <div className="spinner" style={{ width: 40, height: 40, border: '3px solid #252A40', borderTopColor: '#6C47FF', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            </div>
          )}

          {error && (
            <div style={{ padding: 24, textAlign: 'center', color: '#EF9F27' }}>{error}</div>
          )}

          {layoutData && !loading && (
            <svg ref={svgRef} width="100%" height="100%" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} style={{ background: '#080910' }}>
              <defs>
                <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="20" refY="3" orient="auto">
                  <polygon points="0 0, 8 3, 0 6" fill="#3B3F5C" opacity="0.6" />
                </marker>
                <filter id="glow">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
                </filter>
              </defs>

              {/* Edges */}
              {layoutData.edges.map((e, i) => {
                const s = layoutData.nodes.find(n => n.id === e.source);
                const t = layoutData.nodes.find(n => n.id === e.target);
                if (!s || !t) return null;
                return (
                  <line
                    key={i}
                    x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                    stroke={edgeColor(e)}
                    strokeWidth={Math.min((e.count || 1) / 2, 6)}
                    opacity={0.6}
                    markerEnd="url(#arrowhead)"
                  />
                );
              })}

              {/* Edge amount labels */}
              {layoutData.edges.map((e, i) => {
                const s = layoutData.nodes.find(n => n.id === e.source);
                const t = layoutData.nodes.find(n => n.id === e.target);
                if (!s || !t || !e.total_amount) return null;
                const mx = (s.x + t.x) / 2;
                const my = (s.y + t.y) / 2;
                const amt = e.total_amount >= 100000 ? `₹${(e.total_amount / 100000).toFixed(1)}L` :
                            e.total_amount >= 1000 ? `₹${(e.total_amount / 1000).toFixed(0)}K` :
                            `₹${e.total_amount}`;
                return (
                  <text key={`lbl-${i}`} x={mx} y={my - 6} textAnchor="middle" fontSize="9" fill="#8B8FA3">
                    {amt} ({e.count || 1}x)
                  </text>
                );
              })}

              {/* Nodes */}
              {layoutData.nodes.map(n => {
                const r = Math.max(8, Math.sqrt((n.pagerank || 0.001) * 10000) + 4);
                const isSelected = selectedNode === n.id;
                return (
                  <g key={n.id} onClick={() => setSelectedNode(n.id)} style={{ cursor: 'pointer' }}>
                    <circle
                      cx={n.x} cy={n.y} r={r + 3}
                      fill="none"
                      stroke={isSelected ? '#A78BFA' : 'transparent'}
                      strokeWidth={2}
                      filter={isSelected ? 'url(#glow)' : undefined}
                    />
                    <circle
                      cx={n.x} cy={n.y} r={r}
                      fill={nodeColor(n, centerNode)}
                      stroke={nodeStroke(n, centerNode)}
                      strokeWidth={1.5}
                    />
                    {n.is_mule_suspect && (
                      <text x={n.x} y={n.y + 3} textAnchor="middle" fontSize="10" fill="#fff">⚠</text>
                    )}
                    <text
                      x={n.x} y={n.y + r + 14}
                      textAnchor="middle"
                      fontSize="9"
                      fill={isSelected ? '#E0E0E6' : '#6B7094'}
                    >
                      {n.id.length > 18 ? n.id.slice(0, 16) + '…' : n.id}
                    </text>
                  </g>
                );
              })}
            </svg>
          )}
        </div>

        {/* Legend */}
        {layoutData && (
          <div style={{ display: 'flex', gap: 20, marginTop: 8, fontSize: 11, color: '#8B8FA3' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#6C47FF', display: 'inline-block' }} /> Search target
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#E24B4A', display: 'inline-block' }} /> Mule suspect
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#EF9F27', display: 'inline-block' }} /> Hub (6+ connections)
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#1E2235', border: '1px solid #3B3F5C', display: 'inline-block' }} /> Normal
            </span>
            <span>|</span>
            <span>{layoutData.nodes.length} nodes · {layoutData.edges.length} edges</span>
          </div>
        )}
      </div>

      {/* Right: Details Panel */}
      <div style={{ flex: '1 1 30%', minWidth: 280, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Selected Node Details */}
        {selNodeData ? (
          <div className="panel px-5 py-4 fade-in">
            <div className="panel-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Node Details</span>
              {selNodeData.is_mule_suspect && (
                <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: '#E24B4A22', color: '#E24B4A', border: '1px solid #E24B4A44' }}>⚠ MULE SUSPECT</span>
              )}
            </div>
            <div className="font-mono text-sm" style={{ color: '#A78BFA', marginTop: 8, wordBreak: 'break-all' }}>{selNodeData.id}</div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 16 }}>
              <div className="panel" style={{ padding: '10px 12px', background: '#0D0E14' }}>
                <div style={{ fontSize: 10, color: '#6B7094' }}>Total Sent</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#E24B4A' }}>₹{((selNodeData.total_sent || 0) / 1000).toFixed(1)}K</div>
              </div>
              <div className="panel" style={{ padding: '10px 12px', background: '#0D0E14' }}>
                <div style={{ fontSize: 10, color: '#6B7094' }}>Total Received</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#34D399' }}>₹{((selNodeData.total_received || 0) / 1000).toFixed(1)}K</div>
              </div>
              <div className="panel" style={{ padding: '10px 12px', background: '#0D0E14' }}>
                <div style={{ fontSize: 10, color: '#6B7094' }}>Connections</div>
                <div style={{ fontSize: 16, fontWeight: 700 }}>{selNodeData.degree || 0}</div>
              </div>
              <div className="panel" style={{ padding: '10px 12px', background: '#0D0E14' }}>
                <div style={{ fontSize: 10, color: '#6B7094' }}>PageRank</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#EF9F27' }}>{((selNodeData.pagerank || 0) * 1000).toFixed(2)}</div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <button
                onClick={() => { setUpiSearch(selNodeData.id); doSearch(selNodeData.id); }}
                style={{ flex: 1, padding: '8px 0', borderRadius: 6, background: '#6C47FF22', border: '1px solid #6C47FF44', color: '#A78BFA', fontSize: 12, cursor: 'pointer' }}
              >
                🔍 Expand Graph
              </button>
              {!selNodeData.is_mule_suspect && (
                <button
                  onClick={() => handleMarkMule(selNodeData.id)}
                  style={{ flex: 1, padding: '8px 0', borderRadius: 6, background: '#E24B4A22', border: '1px solid #E24B4A44', color: '#E24B4A', fontSize: 12, cursor: 'pointer' }}
                >
                  ⚠ Flag as Mule
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="panel px-5 py-4" style={{ opacity: 0.6 }}>
            <div className="panel-title">Node Details</div>
            <p style={{ fontSize: 12, color: '#6B7094', marginTop: 8 }}>Click a node in the graph to see details</p>
          </div>
        )}

        {/* Communities */}
        <div className="panel px-5 py-4" style={{ flex: 1, overflow: 'auto' }}>
          <div className="panel-title" style={{ marginBottom: 12 }}>
            Communities
            {communities && <span style={{ fontSize: 11, color: '#6B7094', marginLeft: 8 }}>({communities.total_communities || 0} detected)</span>}
          </div>
          {communities?.communities?.slice(0, 8).map((c, i) => (
            <div
              key={i}
              style={{ padding: '10px 12px', marginBottom: 8, borderRadius: 8, background: '#0D0E14', border: `1px solid ${c.risk_level === 'HIGH' ? '#E24B4A33' : '#252A40'}`, cursor: 'pointer' }}
              onClick={() => { if (c.members?.[0]) { setUpiSearch(c.members[0]); doSearch(c.members[0]); }}}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12, fontWeight: 600 }}>Community #{i + 1}</span>
                <span style={{
                  fontSize: 10, padding: '2px 6px', borderRadius: 4,
                  background: c.risk_level === 'HIGH' ? '#E24B4A22' : c.risk_level === 'MEDIUM' ? '#EF9F2722' : '#34D39922',
                  color: c.risk_level === 'HIGH' ? '#E24B4A' : c.risk_level === 'MEDIUM' ? '#EF9F27' : '#34D399',
                }}>
                  {c.risk_level || 'LOW'}
                </span>
              </div>
              <div style={{ fontSize: 11, color: '#8B8FA3', marginTop: 4 }}>
                {c.size || c.members?.length || 0} members · {c.has_mule_suspect ? '⚠ Has mule suspect' : 'No suspects'}
              </div>
            </div>
          ))}
          {(!communities || !communities.communities?.length) && (
            <p style={{ fontSize: 12, color: '#6B7094' }}>Communities populate as transaction data flows in.</p>
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </main>
  );
}
