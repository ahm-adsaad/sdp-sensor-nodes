"""Feature table for the sky model, and the training table with its target."""

from __future__ import annotations

import numpy as np
import pandas as pd

import config
import solar

SUN_FEATURES = ["elevation", "azimuth", "cs_ghi", "hour", "doy"]
WEATHER_FEATURES = [
    "k_fc",
    "direct_frac",
    "diffuse_frac",
    "cloud_cover",
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "precipitation",
]
DUST_FEATURES = ["aerosol_optical_depth", "dust", "pm10"]
FEATURES = SUN_FEATURES + WEATHER_FEATURES + DUST_FEATURES


def sky_ratio(ghi: pd.Series, cs_ghi: pd.Series) -> pd.Series:
    cs = cs_ghi.where(cs_ghi > 0)
    return (ghi / cs).clip(lower=0.0, upper=config.K_MAX)


def build_features(site: config.Site, weather: pd.DataFrame, air: pd.DataFrame | None = None) -> pd.DataFrame:
    w = weather.drop_duplicates("hour_start").sort_values("hour_start").reset_index(drop=True)
    hs = config.utc_ns(w["hour_start"])
    sun = solar.sun_position(site, hs)
    cs = solar.clearsky(site, hs)
    f = pd.DataFrame({"hour_start": hs, "month": hs.month, "elevation": sun["elevation"].to_numpy(), "azimuth": sun["azimuth"].to_numpy()})
    f["cs_ghi"] = cs["cs_ghi"].to_numpy()
    f["hour"] = hs.hour
    f["doy"] = hs.dayofyear
    swr = w["shortwave_radiation"].astype("float64")
    f["k_fc"] = sky_ratio(swr, f["cs_ghi"]).to_numpy()
    sunny = swr.where(swr > 0)
    f["direct_frac"] = (w["direct_radiation"] / sunny).to_numpy()
    f["diffuse_frac"] = (w["diffuse_radiation"] / sunny).to_numpy()
    for c in ("cloud_cover", "temperature_2m", "relative_humidity_2m", "wind_speed_10m", "precipitation"):
        f[c] = w[c].astype("float64").to_numpy()
    if air is not None and len(air):
        a = air.drop_duplicates("hour_start")[["hour_start"] + DUST_FEATURES]
        a = a.assign(hour_start=config.utc_ns(a["hour_start"]))
        f = f.merge(a, on="hour_start", how="left")
    else:
        for c in DUST_FEATURES:
            f[c] = np.nan
    f = f[f["elevation"] > config.MIN_ELEVATION_DEG]
    return f[["hour_start", "month"] + FEATURES].reset_index(drop=True)


def build_training_table(site: config.Site, weather: pd.DataFrame, air: pd.DataFrame | None, sat: pd.DataFrame) -> pd.DataFrame:
    f = build_features(site, weather, air)
    s = sat.drop_duplicates("hour_start")[["hour_start", "sat_ghi"]]
    s = s.assign(hour_start=config.utc_ns(s["hour_start"]))
    t = f.merge(s, on="hour_start", how="left")
    t["k"] = sky_ratio(t["sat_ghi"].astype("float64"), t["cs_ghi"])
    t = t.drop(columns="sat_ghi")
    t = t[t["k"].notna() & t["k_fc"].notna()]
    return t.reset_index(drop=True)
