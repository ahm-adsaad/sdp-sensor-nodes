"""Three quantile LightGBM boosters for the sky ratio."""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

import config
import features
import metrics
import solar

PARAMS = {
    "objective": "quantile",
    "max_depth": 4,
    "num_leaves": 15,
    "min_data_in_leaf": 50,
    "learning_rate": 0.05,
    "verbose": -1,
    "seed": 1,
    "deterministic": True,
}


@dataclass
class SkyModel:
    boosters: dict
    features: list
    trained_rows: int
    last_hour: str


def train(table: pd.DataFrame, features_=None, valid_frac: float = 0.1, max_rounds: int = 2000) -> SkyModel:
    cols = list(features_ or features.FEATURES)
    t = table.sort_values("hour_start").reset_index(drop=True)
    X, y = t[cols], t["k"].to_numpy(dtype=float)
    split = max(int(len(t) * (1 - valid_frac)), 1)
    boosters = {}
    for name, alpha in config.QUANTILES.items():
        params = {**PARAMS, "alpha": alpha}
        dtrain = lgb.Dataset(X.iloc[:split], y[:split], feature_name=cols)
        dvalid = lgb.Dataset(X.iloc[split:], y[split:], reference=dtrain)
        probe = lgb.train(params, dtrain, max_rounds, valid_sets=[dvalid], callbacks=[lgb.early_stopping(50, verbose=False)])
        rounds = max(int(probe.best_iteration or probe.num_trees()), 10)
        boosters[name] = lgb.train(params, lgb.Dataset(X, y, feature_name=cols), rounds)
    return SkyModel(boosters, cols, len(t), str(t["hour_start"].iloc[-1]))


def predict(sky: SkyModel, frame: pd.DataFrame) -> pd.DataFrame:
    X = frame[sky.features]
    out = pd.DataFrame({name: b.predict(X) for name, b in sky.boosters.items()}, index=frame.index)
    return metrics.sort_quantiles(out.clip(lower=0.0, upper=config.K_MAX))


def save(sky: SkyModel, path: pathlib.Path) -> None:
    path = pathlib.Path(path)
    path.mkdir(parents=True, exist_ok=True)
    for name, b in sky.boosters.items():
        b.save_model(str(path / f"{name}.txt"))
    meta = {"features": sky.features, "trained_rows": sky.trained_rows, "last_hour": sky.last_hour}
    (path / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def load(path: pathlib.Path) -> SkyModel:
    path = pathlib.Path(path)
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    boosters = {name: lgb.Booster(model_file=str(path / f"{name}.txt")) for name in config.QUANTILES}
    return SkyModel(boosters, meta["features"], meta["trained_rows"], meta["last_hour"])


def synthetic_table(site: config.Site, start: str, days: int, seed: int = 0) -> pd.DataFrame:
    """Daylight rows with a known rule: k = 0.95 k_fc - 0.3 aod + noise. Test data only."""
    rng = np.random.default_rng(seed)
    hs = pd.date_range(start, periods=days * 24, freq="h", tz="UTC")
    sun = solar.sun_position(site, hs)
    cs = solar.clearsky(site, hs)
    t = pd.DataFrame({"hour_start": hs, "month": hs.month, "elevation": sun["elevation"].to_numpy(), "azimuth": sun["azimuth"].to_numpy()})
    t["cs_ghi"] = cs["cs_ghi"].to_numpy()
    t["hour"], t["doy"] = hs.hour, hs.dayofyear
    t = t[t["elevation"] > config.MIN_ELEVATION_DEG].reset_index(drop=True)
    n = len(t)
    cloudy = rng.random(n) < 0.15
    t["k_fc"] = np.where(cloudy, rng.uniform(0.2, 0.7, n), rng.uniform(0.85, 1.0, n))
    t["direct_frac"] = np.where(cloudy, 0.3, 0.8)
    t["diffuse_frac"] = 1 - t["direct_frac"]
    t["cloud_cover"] = np.where(cloudy, rng.uniform(50, 100, n), rng.uniform(0, 20, n))
    t["temperature_2m"] = 25 + 10 * np.sin((t["doy"] - 100) / 58.0) + rng.normal(0, 2, n)
    t["relative_humidity_2m"] = rng.uniform(20, 80, n)
    t["wind_speed_10m"] = rng.uniform(0, 30, n)
    t["precipitation"] = 0.0
    t["aerosol_optical_depth"] = rng.uniform(0.1, 0.8, n)
    t["dust"] = t["aerosol_optical_depth"] * 200 + rng.normal(0, 10, n)
    t["pm10"] = t["dust"] * 0.8
    t["k"] = np.clip(0.95 * t["k_fc"] - 0.3 * t["aerosol_optical_depth"] + rng.normal(0, 0.04, n), 0, config.K_MAX)
    return t[["hour_start", "month"] + features.FEATURES + ["k"]]
