import React, { useState } from 'react';
import NetworkGraph from '../components/NetworkGraph';

export default function GraphView() {
  const [selectedNode, setSelectedNode] = useState(null);

  return (
    <main className="px-6 py-6">
      <NetworkGraph
        upiId=""
        depth={2}
        onNodeClick={(nodeId) => setSelectedNode(nodeId)}
      />
      {selectedNode && (
        <div className="mt-4 panel px-5 py-4 fade-in">
          <div className="panel-title">Node Details</div>
          <div className="mt-2 font-mono text-sm text-accent">{selectedNode}</div>
          <p className="mt-1 text-xs text-textSecondary">
            Click "Explore" with this UPI ID to expand the graph around this node.
          </p>
        </div>
      )}
    </main>
  );
}
