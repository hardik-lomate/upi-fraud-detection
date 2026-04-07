"""Model metrics API endpoints."""

from __future__ import annotations

from pathlib import Path
import base64
import json

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["metrics"])

BASE_DIR = Path(__file__).resolve().parent
METRICS_PATH = BASE_DIR.parent.parent / "ml" / "models" / "metrics.json"
CONFUSION_IMAGE_PATH = BASE_DIR.parent.parent / "ml" / "reports" / "confusion_matrix.png"


@router.get("/api/v1/model/metrics")
def get_model_metrics():
    if not METRICS_PATH.exists():
        raise HTTPException(status_code=404, detail="metrics.json not found. Run training/report generation first.")
    try:
        with open(METRICS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read metrics: {exc}")


@router.get("/api/v1/model/confusion-matrix")
def get_confusion_matrix():
    payload = {}

    if METRICS_PATH.exists():
        try:
            with open(METRICS_PATH, "r", encoding="utf-8") as f:
                metrics = json.load(f)
            if isinstance(metrics, dict) and "confusion_matrix" in metrics:
                payload["matrix"] = metrics.get("confusion_matrix")
        except Exception:
            payload["matrix"] = None

    if CONFUSION_IMAGE_PATH.exists():
        try:
            raw = CONFUSION_IMAGE_PATH.read_bytes()
            payload["image_base64"] = base64.b64encode(raw).decode("ascii")
        except Exception:
            payload["image_base64"] = None

    if not payload:
        raise HTTPException(status_code=404, detail="No confusion matrix artifact available")

    return payload
