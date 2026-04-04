"""
Graph Feature Extraction — Analyze sender/receiver transaction networks.
Detects ring transactions, mule accounts, and hub-and-spoke fraud patterns.
"""

import networkx as nx
import pandas as pd
from collections import defaultdict
from datetime import datetime, timedelta


class TransactionGraph:
    """Maintains a rolling transaction graph for fraud pattern detection."""

    def __init__(self):
        self.graph = nx.DiGraph()
        self._edge_timestamps = defaultdict(list)  # (sender, receiver) -> [timestamps]

    def add_transaction(self, sender: str, receiver: str, amount: float, timestamp: str = None):
        """Add a transaction edge to the graph."""
        if timestamp:
            try:
                ts_str = str(timestamp)
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                ts = datetime.fromisoformat(ts_str)
            except Exception:
                ts = datetime.utcnow()
        else:
            ts = datetime.utcnow()

        if self.graph.has_edge(sender, receiver):
            self.graph[sender][receiver]["count"] += 1
            self.graph[sender][receiver]["total_amount"] += amount
        else:
            self.graph.add_edge(sender, receiver, count=1, total_amount=amount)

        self._edge_timestamps[(sender, receiver)].append(ts)

        # Update node attributes
        for node in [sender, receiver]:
            if "first_seen" not in self.graph.nodes[node]:
                self.graph.nodes[node]["first_seen"] = ts.isoformat()
            self.graph.nodes[node]["last_seen"] = ts.isoformat()

    def get_node_features(self, node: str) -> dict:
        """Extract graph-based features for a node (sender or receiver)."""
        if node not in self.graph:
            return {
                "out_degree": 0,
                "in_degree": 0,
                "total_degree": 0,
                "pagerank": 0.0,
                "is_hub": False,
                "is_mule_suspect": False,
                "cycle_count": 0,
                "cluster_coefficient": 0.0,
            }

        out_degree = self.graph.out_degree(node)
        in_degree = self.graph.in_degree(node)
        total_degree = out_degree + in_degree

        # PageRank — hubs in fraud networks have high PageRank
        try:
            pagerank = nx.pagerank(self.graph, alpha=0.85).get(node, 0)
        except (nx.PowerIterationFailedConvergence, ZeroDivisionError):
            pagerank = 0.0

        # Hub detection — sends to many unique receivers
        is_hub = out_degree > 20

        # Mule suspect — receives from many senders, sends to few
        is_mule_suspect = in_degree > 10 and out_degree <= 2

        # Cycle detection — ring transactions (A→B→C→A)
        cycle_count = 0
        try:
            cycles = list(nx.simple_cycles(self.graph.subgraph(
                nx.descendants(self.graph, node) | {node}
            )))
            cycle_count = len([c for c in cycles if node in c and len(c) <= 5])
        except (nx.NetworkXError, RecursionError):
            pass

        # Clustering coefficient
        undirected = self.graph.to_undirected()
        try:
            cluster_coefficient = nx.clustering(undirected, node)
        except (nx.NetworkXError, ZeroDivisionError):
            cluster_coefficient = 0.0

        return {
            "out_degree": out_degree,
            "in_degree": in_degree,
            "total_degree": total_degree,
            "pagerank": round(pagerank, 6),
            "is_hub": is_hub,
            "is_mule_suspect": is_mule_suspect,
            "cycle_count": cycle_count,
            "cluster_coefficient": round(cluster_coefficient, 4),
        }

    def detect_ring_transactions(self, node: str, max_length: int = 5) -> list[list[str]]:
        """Find circular money flows involving this node."""
        rings = []
        try:
            for cycle in nx.simple_cycles(self.graph):
                if node in cycle and len(cycle) <= max_length:
                    rings.append(cycle)
                if len(rings) >= 10:  # Limit results
                    break
        except (nx.NetworkXError, RecursionError):
            pass
        return rings

    def get_graph_stats(self) -> dict:
        """Get overall graph statistics."""
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "density": round(nx.density(self.graph), 6) if self.graph.number_of_nodes() > 1 else 0,
            "connected_components": nx.number_weakly_connected_components(self.graph),
        }


# Singleton instance
_transaction_graph = TransactionGraph()


def get_graph() -> TransactionGraph:
    return _transaction_graph
