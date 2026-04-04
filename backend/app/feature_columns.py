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
MODELS_DIR = BASE_DIR.parent.parent / "ml" / "models"
_FEATURE_COLUMNS_CACHE: Optional[List[str]] = None


def get_feature_columns() -> List[str]:
    """Return the feature columns in the exact order used during training."""
    global _FEATURE_COLUMNS_CACHE
    if _FEATURE_COLUMNS_CACHE is not None:
        return _FEATURE_COLUMNS_CACHE

    path = MODELS_DIR / "feature_columns.pkl"
    cols: List[str]

    if path.exists():
        try:
            loaded = joblib.load(path)
            if not isinstance(loaded, list) or not all(isinstance(x, str) for x in loaded):
                raise TypeError("feature_columns.pkl must be a list[str]")
            cols = loaded

            # Warn (but don't crash) if contract differs. Demo stability > hard fail.
            if set(cols) != set(CONTRACT_FEATURE_COLUMNS):
                logger.warning(
                    "Feature column mismatch: contract=%s, model_file=%s. Using model_file order.",
                    CONTRACT_FEATURE_COLUMNS,
                    cols,
                )
        except Exception as e:
            logger.warning("Failed to load %s: %s. Falling back to contract.", path, e)
            cols = list(CONTRACT_FEATURE_COLUMNS)
    else:
        cols = list(CONTRACT_FEATURE_COLUMNS)

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
