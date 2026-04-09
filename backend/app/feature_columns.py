"""Feature column management (training ↔ serving consistency).

Single source of truth is `ml/models/feature_columns.pkl` if present.
Fallbacks to `feature_contract.FEATURE_COLUMNS`.

This module exists to prevent silent feature-order drift between training and serving.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import logging

import joblib

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from feature_contract import FEATURE_COLUMNS as CONTRACT_FEATURE_COLUMNS

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODELS_DIR = BASE_DIR.parent.parent / "ml" / "models"
COMPAT_MODELS_DIR = BASE_DIR.parent.parent / "model"
_FEATURE_COLUMNS_CACHE: Optional[List[str]] = None


def _model_dirs() -> List[Path]:
    env_dir = str(os.getenv("MODEL_DIR", "")).strip()
    candidates: List[Path] = []
    if env_dir:
        candidates.append(Path(env_dir).expanduser())
    candidates.extend([DEFAULT_MODELS_DIR, COMPAT_MODELS_DIR])

    out: List[Path] = []
    seen = set()
    for item in candidates:
        resolved = item.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        out.append(resolved)
    return out


def _load_columns_from_file(path: Path) -> List[str]:
    loaded = joblib.load(path)
    if not isinstance(loaded, list) or not all(isinstance(x, str) for x in loaded):
        raise TypeError(f"{path.name} must be a list[str]")
    return loaded


def get_feature_columns() -> List[str]:
    """Return the feature columns in the exact order used during training."""
    global _FEATURE_COLUMNS_CACHE
    if _FEATURE_COLUMNS_CACHE is not None:
        return _FEATURE_COLUMNS_CACHE

    cols: List[str]

    cols = []
    loaded_from: Optional[Path] = None
    for model_dir in _model_dirs():
        for file_name in ("feature_columns.pkl", "features.pkl"):
            path = model_dir / file_name
            if not path.exists():
                continue
            try:
                cols = _load_columns_from_file(path)
                loaded_from = path
                break
            except Exception as exc:
                logger.warning("Failed to load %s: %s", path, exc)
        if loaded_from is not None:
            break

    if not cols:
        cols = list(CONTRACT_FEATURE_COLUMNS)
    elif set(cols) != set(CONTRACT_FEATURE_COLUMNS):
        # Warn (but don't crash) if contract differs. Demo stability > hard fail.
        logger.warning(
            "Feature column mismatch: contract=%s, model_file=%s. Using model_file order.",
            CONTRACT_FEATURE_COLUMNS,
            cols,
        )

    if loaded_from is not None:
        logger.info("Loaded feature columns from %s", loaded_from)

    # Basic sanity: unique, stable order.
    seen = set()
    cols = [c for c in cols if not (c in seen or seen.add(c))]

    _FEATURE_COLUMNS_CACHE = cols
    return cols


def validate_feature_dict(features: dict) -> List[str]:
    """Validate that all required feature keys exist; return list of missing."""
    cols = get_feature_columns()
    missing = [c for c in cols if c not in features]
    return missing
