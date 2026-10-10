"""Constants, paths and the site/node configuration for the harvest forecast."""

from __future__ import annotations

import pathlib
import tomllib
from dataclasses import dataclass

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"
ARCHIVE = DATA / "archive"
HISTORY = DATA / "history"
FORECASTS = DATA / "forecasts"
MODELS = ROOT / "models"
OUT = ROOT / "out"

QUANTILES = {"q10": 0.1, "q50": 0.5, "q90": 0.9}
HORIZON_H = 36
MIN_ELEVATION_DEG = 5.0       # rows below this are night: forecast 0, not trained on
USABLE_ELEVATION_DEG = 15.0   # node-ratio hours need this much sun
K_MAX = 1.5                   # sky ratio clip
PANEL_W = 0.150               # MP3-37 at 1000 W/m2
HISTORY_START = "2024-02-01"  # day-ahead previous-runs data exists from somewhere in 2024 H1
LINKE_TURBIDITY = 3.0         # dust-free clear sky; dust is learned, not assumed


@dataclass(frozen=True)
class Site:
    name: str
    lat: float
    lon: float
    altitude_m: float


@dataclass(frozen=True)
class Node:
    id: str
    panels: int
    tilt_deg: float
    azimuth_deg: float


def load_config(path: pathlib.Path = ROOT / "config.toml") -> tuple[Site, list[Node]]:
    raw = tomllib.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    s = raw["site"]
    site = Site(s["name"], float(s["lat"]), float(s["lon"]), float(s.get("altitude_m", 0.0)))
    nodes = [
        Node(n["id"], int(n.get("panels", 1)), float(n.get("tilt_deg", 0.0)), float(n.get("azimuth_deg", 180.0)))
        for n in raw.get("nodes", [])
    ]
    return site, nodes


def utc_ns(values) -> pd.DatetimeIndex:
    """Any datetime-like sequence to a tz-aware UTC DatetimeIndex at ns resolution."""
    idx = pd.DatetimeIndex(pd.to_datetime(values, utc=True))
    return idx.as_unit("ns")
