"""
Graph Feature Extraction — Analyze sender/receiver transaction networks.
Detects ring transactions, mule accounts, and hub-and-spoke fraud patterns.
"""

import logging
import os
import pickle
import networkx as nx
import pandas as pd
from collections import defaultdict
from datetime import datetime
from pathlib import Path


logger = logging.getLogger(__name__)


class TransactionGraph:
    """Maintains a rolling transaction graph for fraud pattern detection."""

    def __init__(self, state_path: str | None = None):
        self.graph = nx.DiGraph()
        self._edge_timestamps = defaultdict(list)  # (sender, receiver) -> [timestamps]
        self._seen_txn_ids = set()
        env_path = str(os.getenv("GRAPH_STATE_PATH", "")).strip()
        default_state_path = Path(__file__).resolve().parents[1] / "data" / "transaction_graph.pkl"
        self._state_path = Path(state_path or env_path or default_state_path)
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self.loaded_from_disk = self.load_state()

    def load_state(self) -> bool:
        """Load graph state from disk if available."""
        if not self._state_path.exists():
            return False

        try:
            with open(self._state_path, "rb") as f:
                payload = pickle.load(f)

            loaded_graph = payload.get("graph")
            if loaded_graph is None:
                return False

            self.graph = loaded_graph if isinstance(loaded_graph, nx.DiGraph) else nx.DiGraph(loaded_graph)

            edge_ts = payload.get("edge_timestamps", {}) or {}
            restored = defaultdict(list)
            if isinstance(edge_ts, dict):
                for key, values in edge_ts.items():
                    try:
                        src, dst = key
                        restored[(str(src), str(dst))] = list(values or [])
                    except Exception:
                        continue
            self._edge_timestamps = restored

            seen_ids = payload.get("seen_txn_ids", []) or []
            self._seen_txn_ids = {str(x) for x in seen_ids if str(x).strip()}
            logger.info(
                "Loaded persisted transaction graph from %s (nodes=%s edges=%s)",
                self._state_path,
                self.graph.number_of_nodes(),
                self.graph.number_of_edges(),
            )
            return True
        except Exception as exc:
            logger.warning("Failed to load graph state from %s: %s", self._state_path, exc)
            return False

    def save_state(self) -> bool:
        """Persist graph state to disk atomically."""
        payload = {
            "graph": self.graph,
            "edge_timestamps": dict(self._edge_timestamps),
            "seen_txn_ids": list(self._seen_txn_ids),
            "saved_at": datetime.utcnow().isoformat(),
        }
        tmp_path = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        try:
            with open(tmp_path, "wb") as f:
                pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp_path, self._state_path)
            return True
        except Exception as exc:
            logger.warning("Failed to persist graph state at %s: %s", self._state_path, exc)
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            return False

    def add_transaction(
        self,
        sender: str,
        receiver: str,
        amount: float,
        timestamp: str = None,
        transaction_id: str = None,
        persist: bool = True,
    ):
        """Add a transaction edge to the graph."""
        if transaction_id:
            if transaction_id in self._seen_txn_ids:
                return
            self._seen_txn_ids.add(transaction_id)

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

        if persist:
            self.save_state()

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
            "loaded_from_disk": bool(self.loaded_from_disk),
            "state_path": str(self._state_path),
        }


# Singleton instance
_transaction_graph = TransactionGraph()


def get_graph() -> TransactionGraph:
    return _transaction_graph
