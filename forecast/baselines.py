"""The three no-learning baselines the sky model has to beat."""

from __future__ import annotations

import numpy as np
import pandas as pd

import config
import metrics

METHODS = ("climatology", "persistence", "raw_forecast")
_ALPHAS = config.QUANTILES


def _frame(index, q10, q50, q90) -> pd.DataFrame:
    out = pd.DataFrame({"q10": q10, "q50": q50, "q90": q90}, index=index)
    return metrics.sort_quantiles(out.clip(lower=0.0, upper=config.K_MAX))


def climatology(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Quantiles of k for the same month and hour; overall quantiles for unseen (month, hour)."""
    by = train.groupby(["month", "hour"])["k"].quantile(list(_ALPHAS.values())).unstack()
    by.columns = list(_ALPHAS)
    overall = train["k"].quantile(list(_ALPHAS.values())).to_numpy()
    keys = pd.MultiIndex.from_arrays([test["month"], test["hour"]])
    rows = by.reindex(keys)
    for i, c in enumerate(_ALPHAS):
        rows[c] = rows[c].fillna(overall[i])
    return _frame(test.index, rows["q10"].to_numpy(), rows["q50"].to_numpy(), rows["q90"].to_numpy())


def residual_offsets(train: pd.DataFrame) -> dict:
    resid = (train["k"] - train["k_fc"]).dropna()
    return {"q10": float(resid.quantile(_ALPHAS["q10"])), "q90": float(resid.quantile(_ALPHAS["q90"]))}


def raw_forecast(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """The forecast sky ratio as the median, widened by the training residual quantiles."""
    offs = residual_offsets(train)
    mid = test["k_fc"].to_numpy(dtype=float)
    return _frame(test.index, mid + offs["q10"], mid, mid + offs["q90"])


def persistence(k_actual: pd.Series, test: pd.DataFrame, train: pd.DataFrame) -> pd.DataFrame:
    """k at the same hour yesterday, widened by the quantiles of that rule's past errors."""
    k_actual = k_actual.copy()
    k_actual.index = config.utc_ns(k_actual.index)
    yesterday = lambda frame: k_actual.reindex(config.utc_ns(frame["hour_start"]) - pd.Timedelta(hours=24)).to_numpy()
    past_err = pd.Series(train["k"].to_numpy() - yesterday(train)).dropna()
    lo, hi = past_err.quantile(_ALPHAS["q10"]), past_err.quantile(_ALPHAS["q90"])
    mid = yesterday(test)
    mid = np.where(np.isnan(mid), test["k_fc"].to_numpy(dtype=float), mid)
    return _frame(test.index, mid + lo, mid, mid + hi)
