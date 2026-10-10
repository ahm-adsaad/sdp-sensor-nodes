"""Open-Meteo feeds as tidy hourly frames keyed by hour start."""

from __future__ import annotations

import time

import pandas as pd
import requests

import config

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
SATELLITE_URL = "https://satellite-api.open-meteo.com/v1/archive"
SATELLITE_MODEL = "eumetsat_sarah3"  # complete history at the site; never omit models=

WEATHER_VARS = [
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "cloud_cover",
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "precipitation",
]
AIR_VARS = ["dust", "aerosol_optical_depth", "pm10"]
SAT_RENAME = {"shortwave_radiation": "sat_ghi", "direct_radiation": "sat_direct", "diffuse_radiation": "sat_diffuse"}


class FeedError(RuntimeError):
    pass


def get_json(url, params, *, retries=3, pause_s=5.0, session=None) -> dict:
    """GET JSON; Open-Meteo reports overload as HTTP 200 with an error flag, so check both."""
    s = session or requests
    last = None
    for attempt in range(retries):
        try:
            r = s.get(url, params=params, timeout=60)
            payload = r.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
        else:
            if r.ok and not payload.get("error"):
                return payload
            last = FeedError(str(payload.get("reason", f"HTTP {r.status_code}")))
        if attempt < retries - 1:
            time.sleep(pause_s)
    raise FeedError(f"{url}: {last}")


def hourly_frame(payload: dict, rename: dict | None = None) -> pd.DataFrame:
    frame = pd.DataFrame(payload["hourly"])
    labels = config.utc_ns(frame.pop("time"))
    frame.insert(0, "hour_start", labels - pd.Timedelta(hours=1))
    if rename:
        frame = frame.rename(columns=rename)
    for c in frame.columns[1:]:
        frame[c] = pd.to_numeric(frame[c], errors="coerce").astype("float64")
    return frame


def _site(site):
    return {"latitude": site.lat, "longitude": site.lon, "timezone": "UTC"}


def forecast_params(site, *, days=3):
    return {**_site(site), "forecast_days": days, "hourly": ",".join(WEATHER_VARS)}


def air_params(site, *, days=5):
    return {**_site(site), "forecast_days": days, "hourly": ",".join(AIR_VARS)}


def previous_runs_params(site, start, end):
    return {**_site(site), "start_date": start, "end_date": end, "hourly": ",".join(v + "_previous_day1" for v in WEATHER_VARS)}


def air_history_params(site, start, end):
    return {**_site(site), "start_date": start, "end_date": end, "hourly": ",".join(AIR_VARS)}


def satellite_params(site, start, end):
    return {**_site(site), "models": SATELLITE_MODEL, "start_date": start, "end_date": end, "hourly": ",".join(SAT_RENAME)}


# `get` defaults to None and is resolved at call time so tests can monkeypatch feeds.get_json.
def fetch_forecast(site, *, days=3, get=None) -> pd.DataFrame:
    get = get or get_json
    return hourly_frame(get(FORECAST_URL, forecast_params(site, days=days)))[["hour_start"] + WEATHER_VARS]


def fetch_air_quality(site, *, days=5, get=None) -> pd.DataFrame:
    get = get or get_json
    return hourly_frame(get(AIR_URL, air_params(site, days=days)))[["hour_start"] + AIR_VARS]


def fetch_previous_runs(site, start, end, *, get=None) -> pd.DataFrame:
    get = get or get_json
    rename = {v + "_previous_day1": v for v in WEATHER_VARS}
    return hourly_frame(get(PREVIOUS_RUNS_URL, previous_runs_params(site, start, end)), rename)[["hour_start"] + WEATHER_VARS]


def fetch_air_quality_history(site, start, end, *, get=None) -> pd.DataFrame:
    get = get or get_json
    return hourly_frame(get(AIR_URL, air_history_params(site, start, end)))[["hour_start"] + AIR_VARS]


def fetch_satellite(site, start, end, *, get=None) -> pd.DataFrame:
    get = get or get_json
    return hourly_frame(get(SATELLITE_URL, satellite_params(site, start, end)), SAT_RENAME)[["hour_start", *SAT_RENAME.values()]]


def fetch_range(fetch_one, start, end, step_days=92) -> pd.DataFrame:
    """Call fetch_one(start_iso, end_iso) over consecutive date chunks and concatenate."""
    frames = []
    cur, stop_all = pd.Timestamp(start), pd.Timestamp(end)
    while cur <= stop_all:
        stop = min(cur + pd.Timedelta(days=step_days - 1), stop_all)
        frames.append(fetch_one(cur.date().isoformat(), stop.date().isoformat()))
        cur = stop + pd.Timedelta(days=1)
    return pd.concat(frames, ignore_index=True)
