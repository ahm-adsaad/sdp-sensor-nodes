"""Clear-sky energy per node, the slow per-node ratio, and the node forecast."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

import config
import solar


@dataclass(frozen=True)
class NodeRatio:
    ratio: float
    usable_hours: int
    is_default: bool


def clear_sky_energy_j(site: config.Site, node: config.Node, hour_start) -> pd.Series:
    hs = config.utc_ns(hour_start)
    poa = solar.clearsky_poa(site, hs, node.tilt_deg, node.azimuth_deg)
    return (node.panels * config.PANEL_W * poa / 1000.0 * 3600.0).rename("e_clear_j")


def expected_energy_j(site: config.Site, node: config.Node, k_actual: pd.Series) -> pd.Series:
    hs = config.utc_ns(k_actual.index)
    e = clear_sky_energy_j(site, node, hs)
    return pd.Series(e.to_numpy() * k_actual.to_numpy(dtype=float), index=hs, name="expected_j")


def node_ratio(
    records: pd.DataFrame,
    expected_j: pd.Series,
    elevation: pd.Series,
    previous: float = 1.0,
    window_days: int = 7,
    min_hours: int = 5,
    dark_frac: float = 0.02,
    min_seconds: float = 600.0,
) -> NodeRatio:
    """Median of measured / expected over usable hours in the last `window_days`.

    Usable: sun above USABLE_ELEVATION_DEG, at least `min_seconds` of harvesting time, expected > 0,
    not flagged store_full, and not "dark" (measured under `dark_frac` of expected, which
    is what a full store looks like from the panel side). The ratio is on power (energy over
    harvesting time against the expected hourly energy), so an hour where the store filled
    part-way through still measures the panel.
    """
    if records.empty:
        return NodeRatio(previous, 0, True)
    r = records.copy()
    r["hour_start"] = config.utc_ns(r["hour_start"])
    cutoff = r["hour_start"].max() - pd.Timedelta(days=window_days)
    r = r[r["hour_start"] > cutoff]
    exp = pd.Series(expected_j.to_numpy(), index=config.utc_ns(expected_j.index), name="expected_j")
    elev = pd.Series(elevation.to_numpy(), index=config.utc_ns(elevation.index), name="elevation")
    r = r.join(exp, on="hour_start").join(elev, on="hour_start")
    ok = (
        (r["elevation"] > config.USABLE_ELEVATION_DEG)
        & (r["seconds"] >= min_seconds)
        & (r["expected_j"] > 0)
        & (~r["store_full"].astype(bool))
    )
    # harvest power while the store was charging, against the expected power for the whole hour
    hourly = (r["energy_j"] / r["seconds"].where(r["seconds"] > 0)) * 3600.0 / r["expected_j"]
    usable = ok & (hourly >= dark_frac)
    n = int(usable.sum())
    if n < min_hours:
        return NodeRatio(float(previous), n, True)
    return NodeRatio(float(hourly[usable].median()), n, False)


def node_forecast(site: config.Site, node: config.Node, hours, k_q: pd.DataFrame, ratio: float) -> pd.DataFrame:
    hs = config.utc_ns(hours)
    e = clear_sky_energy_j(site, node, hs)
    k = k_q.copy()
    k.index = config.utc_ns(k.index)
    k = k.reindex(hs).fillna(0.0)
    out = pd.DataFrame({"hour_start": hs})
    for level in ("q10", "q50", "q90"):
        out[f"{level}_j"] = (e.to_numpy() * k[level].to_numpy() * ratio)
    return out
