"""Scores for quantile forecasts."""

from __future__ import annotations

import numpy as np
import pandas as pd

LEVELS = ["q10", "q50", "q90"]


def pinball(y, q, alpha: float) -> float:
    d = np.asarray(y, dtype=float) - np.asarray(q, dtype=float)
    return float(np.mean(np.maximum(alpha * d, (alpha - 1.0) * d)))


def coverage_below(y, q) -> float:
    return float(np.mean(np.asarray(y, dtype=float) < np.asarray(q, dtype=float)))


def sort_quantiles(frame: pd.DataFrame) -> pd.DataFrame:
    values = np.sort(frame[LEVELS].to_numpy(dtype=float), axis=1)
    out = frame.copy()
    for i, c in enumerate(LEVELS):
        out[c] = values[:, i]
    return out
