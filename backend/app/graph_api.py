"""
Graph API — Fraud investigation network endpoints.

Exposes the existing NetworkX graph as visual API endpoints for D3.js rendering.
Adds betweenness centrality, PageRank, community detection (Louvain), and
suspicious path finding for analyst investigation workflows.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import networkx as nx

from .graph_features import get_graph

router = APIRouter(prefix="/graph", tags=["Graph Investigation"])


class MuleMarkRequest(BaseModel):
    upi_id: str
    reason: Optional[str] = "Manual analyst tagging"


# In-memory mule list (persisted via graph node attributes)
_mule_tags = {}


@router.get("/subgraph", summary="Get ego subgraph for a UPI ID")
def get_subgraph(
    upi_id: str = Query(..., description="Center node UPI ID"),
    depth: int = Query(2, ge=1, le=4, description="Hop depth"),
):
    """Return nodes + edges JSON suitable for D3.js force-directed graph."""
    tg = get_graph()
    G = tg.graph

    if upi_id not in G:
        return {"nodes": [{"id": upi_id, "group": "center", "size": 1}], "edges": [], "center": upi_id}

    # Build ego graph
    ego_nodes = {upi_id}
    frontier = {upi_id}
    for _ in range(depth):
        next_frontier = set()
        for node in frontier:
            next_frontier.update(G.successors(node))
            next_frontier.update(G.predecessors(node))
        ego_nodes.update(next_frontier)
        frontier = next_frontier
        if len(ego_nodes) > 200:
            break

    subgraph = G.subgraph(ego_nodes)

    # Compute PageRank for sizing
    try:
        pr = nx.pagerank(subgraph, alpha=0.85)
    except Exception:
        pr = {n: 0.01 for n in subgraph.nodes()}

    # Build node list
    nodes = []
    for node in subgraph.nodes():
        is_mule = _mule_tags.get(node, False) or tg.get_node_features(node).get("is_mule_suspect", False)
        group = "center" if node == upi_id else ("mule" if is_mule else "normal")
        nodes.append({
            "id": node,
            "group": group,
            "pagerank": round(pr.get(node, 0), 6),
            "in_degree": subgraph.in_degree(node),
            "out_degree": subgraph.out_degree(node),
            "is_mule": is_mule,
        })

    # Build edge list
    edges = []
    for u, v, data in subgraph.edges(data=True):
        edges.append({
            "source": u,
            "target": v,
            "count": data.get("count", 1),
            "total_amount": round(data.get("total_amount", 0), 2),
        })

    return {
        "center": upi_id,
        "depth": depth,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }


@router.get("/communities", summary="Detect fraud communities (Louvain)")
def get_communities():
    """Run Louvain community detection on the transaction graph."""
    tg = get_graph()
    G = tg.graph

    if G.number_of_nodes() == 0:
        return {"communities": [], "total_communities": 0}

    undirected = G.to_undirected()

    try:
        communities = list(nx.community.louvain_communities(undirected, seed=42))
    except Exception:
        # Fallback: connected components
        communities = [set(c) for c in nx.connected_components(undirected)]

    # Sort by size (largest suspicious clusters first)
    communities.sort(key=len, reverse=True)

    result = []
    for i, community in enumerate(communities[:20]):  # Top 20
        members = list(community)[:50]
        # Check if any members are mule suspects
        has_mule = any(
            _mule_tags.get(m, False) or tg.get_node_features(m).get("is_mule_suspect", False)
            for m in members
        )
        result.append({
            "community_id": i,
            "size": len(community),
            "members": members,
            "has_mule_suspect": has_mule,
            "risk_level": "HIGH" if has_mule else ("MEDIUM" if len(community) > 5 else "LOW"),
        })

    return {
        "total_communities": len(communities),
        "communities": result,
    }


@router.get("/suspicious-paths", summary="Find suspicious paths between flagged nodes")
def get_suspicious_paths(
    source: Optional[str] = Query(None, description="Source UPI ID (if omitted, uses all mule suspects)"),
    target: Optional[str] = Query(None, description="Target UPI ID"),
    max_paths: int = Query(5, ge=1, le=20),
):
    """Find shortest paths between flagged/suspicious nodes."""
    tg = get_graph()
    G = tg.graph

    # Identify flagged nodes
    flagged = set(_mule_tags.keys())
    for node in G.nodes():
        features = tg.get_node_features(node)
        if features.get("is_mule_suspect") or features.get("is_hub"):
            flagged.add(node)

    if not flagged:
        return {"paths": [], "flagged_nodes": []}

    paths = []

    if source and target:
        # Specific source-target
        try:
            for path in nx.all_shortest_paths(G, source, target):
                paths.append(path)
                if len(paths) >= max_paths:
                    break
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass
    else:
        # Find paths between all flagged pairs
        flagged_list = list(flagged)[:10]
        for i, s in enumerate(flagged_list):
            for t in flagged_list[i + 1:]:
                try:
                    path = nx.shortest_path(G, s, t)
                    paths.append(path)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    pass
                if len(paths) >= max_paths:
                    break
            if len(paths) >= max_paths:
                break

    return {
        "flagged_nodes": list(flagged)[:50],
        "paths": [
            {
                "nodes": p,
                "length": len(p) - 1,
                "total_amount": sum(
                    G[p[j]][p[j + 1]].get("total_amount", 0)
                    for j in range(len(p) - 1)
                    if G.has_edge(p[j], p[j + 1])
                ),
            }
            for p in paths
        ],
    }


@router.post("/mark-mule", summary="Mark a UPI ID as a mule account")
def mark_mule(req: MuleMarkRequest):
    """Manual analyst tagging of a mule account."""
    _mule_tags[req.upi_id] = True

    tg = get_graph()
    if req.upi_id in tg.graph:
        tg.graph.nodes[req.upi_id]["is_mule_tagged"] = True
        tg.graph.nodes[req.upi_id]["mule_reason"] = req.reason

    return {
        "status": "ok",
        "upi_id": req.upi_id,
        "tagged_as_mule": True,
        "reason": req.reason,
    }
