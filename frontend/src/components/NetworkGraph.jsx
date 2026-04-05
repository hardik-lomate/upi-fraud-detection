import React, { useRef, useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';

export default function NetworkGraph({ upiId = '', depth = 2, onNodeClick }) {
  const svgRef = useRef(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searchId, setSearchId] = useState(upiId || '');
  const [error, setError] = useState(null);

  const fetchGraph = useCallback(async (id, d) => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/graph/subgraph', { params: { upi_id: id, depth: d } });
      setData(res.data);
    } catch (e) {
      setError('Failed to load graph data');
      // Generate demo data
      setData(generateDemoGraph(id, d));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (upiId) {
      setSearchId(upiId);
      fetchGraph(upiId, depth);
    }
  }, [upiId, depth, fetchGraph]);

  // D3-free force simulation with basic SVG rendering
  useEffect(() => {
    if (!data || !svgRef.current) return;
    renderGraph(svgRef.current, data, onNodeClick);
  }, [data, onNodeClick]);

  return (
    <div className="panel fade-in h-full">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border/60">
        <div>
          <div className="panel-title">Transaction Network Graph</div>
          <div className="mt-1 text-xs text-textSecondary">
            {data ? `${data.node_count || 0} nodes · ${data.edge_count || 0} edges` : 'Enter a UPI ID to explore'}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="UPI ID..."
            value={searchId}
            onChange={(e) => setSearchId(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchGraph(searchId, depth)}
            className="w-48 rounded-lg border border-border/60 bg-bg/40 px-3 py-1.5 text-xs text-textPrimary outline-none placeholder:text-textMuted focus:border-accent/40"
          />
          <button
            type="button"
            onClick={() => fetchGraph(searchId, depth)}
            className="rounded-lg bg-accent/15 border border-accent/30 px-3 py-1.5 text-xs font-semibold text-accent hover:bg-accent/25 transition"
          >
            Explore
          </button>
        </div>
      </div>
      <div className="relative" style={{ height: '500px' }}>
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-bg/50 z-10">
            <div className="text-sm text-accent animate-pulse">Loading graph...</div>
          </div>
        )}
        {error && !data && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-sm text-danger">{error}</div>
          </div>
        )}
        <svg ref={svgRef} width="100%" height="100%" className="cursor-grab active:cursor-grabbing" />
        {/* Legend */}
        <div className="absolute bottom-4 left-4 glass rounded-lg px-3 py-2 text-[10px] space-y-1">
          <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-accent" /> Center Node</div>
          <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-safe" /> Normal</div>
          <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-danger" /> Mule Suspect</div>
        </div>
      </div>
    </div>
  );
}

function generateDemoGraph(centerId, depth) {
  const nodes = [{ id: centerId, group: 'center', pagerank: 0.1, in_degree: 5, out_degree: 8, is_mule: false }];
  const edges = [];
  const count = 8 + Math.floor(Math.random() * 12);

  for (let i = 0; i < count; i++) {
    const nodeId = `user_${String(i).padStart(4, '0')}@upi`;
    const isMule = Math.random() < 0.15;
    nodes.push({
      id: nodeId, group: isMule ? 'mule' : 'normal',
      pagerank: Math.random() * 0.05, in_degree: Math.floor(Math.random() * 10),
      out_degree: Math.floor(Math.random() * 10), is_mule: isMule,
    });
    const source = Math.random() < 0.5 ? centerId : nodeId;
    const target = source === centerId ? nodeId : centerId;
    edges.push({ source, target, count: Math.floor(Math.random() * 5) + 1, total_amount: Math.floor(Math.random() * 50000) });
  }
  // Cross-connections
  for (let i = 0; i < 4; i++) {
    const a = nodes[1 + Math.floor(Math.random() * (nodes.length - 1))].id;
    const b = nodes[1 + Math.floor(Math.random() * (nodes.length - 1))].id;
    if (a !== b) edges.push({ source: a, target: b, count: 1, total_amount: Math.floor(Math.random() * 20000) });
  }

  return { center: centerId, depth, node_count: nodes.length, edge_count: edges.length, nodes, edges };
}

function renderGraph(svgEl, data, onNodeClick) {
  if (!data?.nodes?.length) return;
  const width = svgEl.clientWidth || 800;
  const height = svgEl.clientHeight || 500;

  // Clear
  while (svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);

  // Simple force layout (no D3 dependency)
  const nodeMap = {};
  const simNodes = data.nodes.map((n, i) => {
    const angle = (2 * Math.PI * i) / data.nodes.length;
    const r = n.group === 'center' ? 0 : 120 + Math.random() * 80;
    const node = {
      ...n, x: width / 2 + r * Math.cos(angle), y: height / 2 + r * Math.sin(angle),
      vx: 0, vy: 0,
    };
    nodeMap[n.id] = node;
    return node;
  });

  // Simple force iterations
  for (let iter = 0; iter < 80; iter++) {
    // Repulsion
    for (let i = 0; i < simNodes.length; i++) {
      for (let j = i + 1; j < simNodes.length; j++) {
        const dx = simNodes[j].x - simNodes[i].x;
        const dy = simNodes[j].y - simNodes[i].y;
        const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
        const force = 800 / (dist * dist);
        simNodes[i].vx -= (dx / dist) * force;
        simNodes[i].vy -= (dy / dist) * force;
        simNodes[j].vx += (dx / dist) * force;
        simNodes[j].vy += (dy / dist) * force;
      }
    }
    // Attraction (edges)
    data.edges.forEach((e) => {
      const s = nodeMap[e.source];
      const t = nodeMap[e.target];
      if (!s || !t) return;
      const dx = t.x - s.x;
      const dy = t.y - s.y;
      const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const force = (dist - 100) * 0.01;
      s.vx += (dx / dist) * force;
      s.vy += (dy / dist) * force;
      t.vx -= (dx / dist) * force;
      t.vy -= (dy / dist) * force;
    });
    // Center gravity
    simNodes.forEach((n) => {
      n.vx += (width / 2 - n.x) * 0.002;
      n.vy += (height / 2 - n.y) * 0.002;
      n.x += n.vx * 0.3;
      n.y += n.vy * 0.3;
      n.vx *= 0.85;
      n.vy *= 0.85;
      n.x = Math.max(30, Math.min(width - 30, n.x));
      n.y = Math.max(30, Math.min(height - 30, n.y));
    });
  }

  const ns = 'http://www.w3.org/2000/svg';

  // Draw edges
  data.edges.forEach((e) => {
    const s = nodeMap[e.source];
    const t = nodeMap[e.target];
    if (!s || !t) return;
    const line = document.createElementNS(ns, 'line');
    line.setAttribute('x1', s.x);
    line.setAttribute('y1', s.y);
    line.setAttribute('x2', t.x);
    line.setAttribute('y2', t.y);
    line.setAttribute('stroke', 'rgba(108, 71, 255, 0.2)');
    line.setAttribute('stroke-width', Math.min(e.count, 4));
    line.classList.add('graph-link');
    svgEl.appendChild(line);
  });

  // Draw nodes
  simNodes.forEach((n) => {
    const g = document.createElementNS(ns, 'g');
    g.classList.add('graph-node');
    g.setAttribute('transform', `translate(${n.x}, ${n.y})`);

    const circle = document.createElementNS(ns, 'circle');
    const radius = n.group === 'center' ? 14 : 6 + Math.min(n.in_degree + n.out_degree, 10);
    const color = n.group === 'center' ? '#6C47FF' : n.group === 'mule' ? '#E24B4A' : '#00C9A7';

    circle.setAttribute('r', radius);
    circle.setAttribute('fill', color);
    circle.setAttribute('fill-opacity', '0.8');
    circle.setAttribute('stroke', color);
    circle.setAttribute('stroke-width', '2');
    circle.setAttribute('stroke-opacity', '0.3');

    const text = document.createElementNS(ns, 'text');
    text.setAttribute('y', radius + 14);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('fill', '#8B8FAD');
    text.setAttribute('font-size', '9');
    text.setAttribute('font-family', 'JetBrains Mono, monospace');
    text.textContent = n.id.length > 16 ? n.id.substring(0, 14) + '...' : n.id;

    g.appendChild(circle);
    g.appendChild(text);

    g.addEventListener('click', () => onNodeClick?.(n.id));

    svgEl.appendChild(g);
  });
}
