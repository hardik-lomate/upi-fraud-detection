"""Graph risk engine.

Converts graph topology features into a normalized graph risk score.
"""

from __future__ import annotations

from typing import Any


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def score_graph_risk(graph_info: dict[str, Any]) -> dict[str, Any]:
    info = graph_info or {}

    mule = 1.0 if info.get("is_mule_suspect") else 0.0
    hub = 1.0 if info.get("is_hub") else 0.0
    in_degree = _clamp01(float(info.get("in_degree", 0) or 0) / 15.0)
    cycle_count = _clamp01(float(info.get("cycle_count", 0) or 0) / 4.0)
    pagerank = _clamp01(float(info.get("pagerank", 0.0) or 0.0) * 12.0)

    graph_score = _clamp01(
        (0.35 * mule)
        + (0.20 * hub)
        + (0.20 * in_degree)
        + (0.15 * cycle_count)
        + (0.10 * pagerank)
    )

    reasons: list[str] = []
    if mule:
        reasons.append("Account resembles mule-network behavior")
    if cycle_count >= 0.5:
        reasons.append("Graph cycle activity indicates ring movement")
    if in_degree >= 0.6:
        reasons.append("High inbound connectivity from multiple parties")
    if not reasons:
        reasons.append("No strong graph fraud signal detected")

    return {
        "graph_score": round(graph_score, 4),
        "components": {
            "mule": round(mule, 4),
            "hub": round(hub, 4),
            "in_degree": round(in_degree, 4),
            "cycle_count": round(cycle_count, 4),
            "pagerank": round(pagerank, 4),
        },
        "reasons": reasons,
    }
