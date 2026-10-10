"""Rolling monthly back-test of the sky model against the baselines."""

from __future__ import annotations

import pathlib

import pandas as pd

import baselines
import features
import metrics
import model

METHODS = ("lightgbm", "lightgbm_nodust", "climatology", "persistence", "raw_forecast")
NODUST = [c for c in features.FEATURES if c not in features.DUST_FEATURES]


def year_month(hour_start: pd.Series) -> pd.Series:
    """Calendar month as an int like 202506 (to_period would drop the timezone with a warning)."""
    return hour_start.dt.year * 100 + hour_start.dt.month


def rolling_months(table: pd.DataFrame, min_train_months: int = 6):
    t = table.sort_values("hour_start").reset_index(drop=True)
    ym = year_month(t["hour_start"])
    months = sorted(ym.unique())
    for m in months[min_train_months:]:
        yield t[ym < m], t[ym == m]


def run(table: pd.DataFrame, methods=METHODS, max_rounds: int = 2000) -> pd.DataFrame:
    k_all = table.set_index("hour_start")["k"]
    rows = []
    for train, test in rolling_months(table):
        preds = {}
        if "lightgbm" in methods:
            preds["lightgbm"] = model.predict(model.train(train, max_rounds=max_rounds), test)
        if "lightgbm_nodust" in methods:
            preds["lightgbm_nodust"] = model.predict(model.train(train, NODUST, max_rounds=max_rounds), test)
        if "climatology" in methods:
            preds["climatology"] = baselines.climatology(train, test)
        if "persistence" in methods:
            preds["persistence"] = baselines.persistence(k_all, test, train)
        if "raw_forecast" in methods:
            preds["raw_forecast"] = baselines.raw_forecast(train, test)
        base = test[["hour_start", "month", "k", "cs_ghi", "aerosol_optical_depth"]]
        for name, p in preds.items():
            rows.append(pd.concat([base, p], axis=1).assign(method=name))
    return pd.concat(rows, ignore_index=True)


def aod_band(aod: pd.Series) -> pd.Series:
    lo, hi = aod.quantile([1 / 3, 2 / 3])
    return pd.Series(pd.cut(aod, [-1, lo, hi, 1e9], labels=["low", "mid", "high"]).astype(str), index=aod.index)


def _score(g: pd.DataFrame) -> pd.Series:
    return pd.Series(
        {
            "hours": int(len(g)),
            "pinball10": metrics.pinball(g["k"], g["q10"], 0.1),
            "pinball50": metrics.pinball(g["k"], g["q50"], 0.5),
            "pinball90": metrics.pinball(g["k"], g["q90"], 0.9),
            "cov10": metrics.coverage_below(g["k"], g["q10"]),
            "mae_wm2": float(((g["k"] - g["q50"]).abs() * g["cs_ghi"]).mean()),
        }
    )


def summarize(preds: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    keys = ["method"] + ([by] if by else [])
    out = preds.groupby(keys, observed=True).apply(_score, include_groups=False).reset_index()
    out["hours"] = out["hours"].astype(int)
    return out.sort_values(keys).reset_index(drop=True)


def _markdown(frame: pd.DataFrame, digits: int = 4) -> str:
    cols = list(frame.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in frame.iterrows():
        cells = [f"{v:.{digits}f}" if isinstance(v, float) else str(v) for v in r.tolist()]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_report(preds: pd.DataFrame, out_dir: pathlib.Path) -> pathlib.Path:
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    overall = summarize(preds)
    by_month = summarize(preds, by="month")
    by_aod = summarize(preds.assign(aod_band=aod_band(preds["aerosol_optical_depth"].fillna(preds["aerosol_optical_depth"].median()))), by="aod_band")
    overall.to_csv(out_dir / "backtest.csv", index=False)
    by_month.to_csv(out_dir / "backtest_by_month.csv", index=False)
    by_aod.to_csv(out_dir / "backtest_by_aod.csv", index=False)
    span = f"{preds['hour_start'].min():%Y-%m-%d} to {preds['hour_start'].max():%Y-%m-%d}"
    text = "\n\n".join(
        [
            "# Sky-model back-test",
            f"Rolling monthly folds, each trained on every earlier month, over {span}. "
            "Pinball loss in sky-ratio units (lower is better); cov10 is the share of hours below the 10 % level (target 0.10); "
            "mae_wm2 is the median's error in W/m2.",
            "## Overall\n\n" + _markdown(overall),
            "## By month\n\n" + _markdown(by_month),
            "## By aerosol optical depth tercile\n\n" + _markdown(by_aod),
        ]
    )
    path = out_dir / "backtest.md"
    path.write_text(text + "\n", encoding="utf-8")
    return path
