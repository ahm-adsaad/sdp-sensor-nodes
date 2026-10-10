# Harvest Forecast Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python service in `forecast/` that archives public weather feeds for the Sharjah site every hour, trains three quantile LightGBM models on public history, and publishes a 36-hour, three-level harvest-energy forecast per node to InfluxDB, with a back-test table that shows whether LightGBM beats the baselines.

**Architecture:** Harvest is split into clear-sky energy (pvlib physics) x sky ratio (LightGBM, trained on Open-Meteo day-ahead forecasts against SARAH-3 satellite irradiance) x node ratio (a slow per-node median measured from harvest records). Flat modules under `forecast/` mirror the `enclosure/` sub-project: each module is pure and tested on recorded or synthetic data; only `influx.py` talks to the VPS database and only `feeds.py` talks to the network. `cli.py` wires the modules into the `fetch`, `fetch-history`, `train`, `backtest`, `predict`, `ratio`, `import-ppk2`, `dryrun` and `selfcheck` commands that systemd timers run on the VPS.

**Tech Stack:** Python 3.11+ (3.13 locally), lightgbm 4.7.0, pvlib 0.16.1, pandas 3.0.6, pyarrow 26.0.0, requests 2.34.2, pytest. Open-Meteo forecast, air-quality, previous-runs and satellite APIs. InfluxDB (1.x or 2.x) over its HTTP API. systemd timers.

**Spec:** `docs/superpowers/specs/2026-10-05-harvest-forecast-design.md`

## Global Constraints

- All code lives under `forecast/` as flat modules (`import solar`, not `from forecast import solar`), like `enclosure/`. Run Python as `forecast/.venv/Scripts/python.exe` locally; run tests with `cd forecast && .venv/Scripts/python.exe -m pytest`. On the VPS the same layout runs from `/opt/sdp-sensor-nodes/forecast` with `.venv/bin/python`.
- Every timestamp is UTC and tz-aware, at nanosecond resolution. Every hourly row is keyed by `hour_start`, the start of the hour. Open-Meteo labels an hour by its end and its radiation values are the mean over the preceding hour, so `hour_start = label - 1 h`, and sun geometry and clear-sky irradiance are evaluated at `hour_start + 30 min`.
- Site default: 25.29 N, 55.48 E, 23 m (`config.toml`). Panel rating 0.150 W per panel at 1000 W/m2 (`PANEL_W`). Levels 10, 50 and 90 % (`QUANTILES`). Horizon 36 hours (`HORIZON_H`). Daylight means apparent sun elevation above 5 degrees (`MIN_ELEVATION_DEG`); node-ratio hours need 15 degrees (`USABLE_ELEVATION_DEG`). Sky ratios are clipped to `[0, K_MAX]` with `K_MAX = 1.5`.
- Clear sky is pvlib Ineichen with a fixed Linke turbidity of 3.0 (a dust-free sky), so dust shows up in the learned sky ratio instead of the physics term.
- The training target is the Open-Meteo satellite feed with `models=eumetsat_sarah3` (complete history, about 1.5 days behind). Never call the satellite endpoint without `models`: without it the service silently returns ERA5 reanalysis.
- Training inputs are the previous-runs feed at `_previous_day1`; low, mid and high cloud cover are null at that lead, so only `cloud_cover` (total) is a feature. Day-ahead history at this site starts between 2024-01-10 and 2024-06-10; `HISTORY_START = "2024-02-01"` and null rows are dropped.
- LightGBM starting parameters: `objective=quantile`, `max_depth=4`, `num_leaves=15`, `min_data_in_leaf=50`, `learning_rate=0.05`, rounds by early stopping on the most recent 10 % of training rows, then refit on all rows with that round count. The three outputs are sorted so they never cross.
- No network in the test run. Feed functions take a `get` callable; tests pass fakes that return recorded JSON from `forecast/tests/fixtures/`.
- Synthetic data from `simulate.py` is tagged `source=sim` and is never reported as a result.
- Secrets come from environment variables (`forecast/.env` on the VPS, never committed). `forecast/data/`, `forecast/models/` and `forecast/.venv/` are ignored; `forecast/out/` (the back-test tables) is committed.
- Commit messages are short and plain, with no co-author trailer. Push to `origin main` after each task.

## Review Focus

1. Open-Meteo returns HTTP 200 with `{"error": true, "reason": "The service is overloaded"}` under load. `feeds.get_json` must treat it as a failure and retry, never parse it as data. (Task 2 test `test_get_json_retries_on_error_payload`.)
2. Hourly arrays contain `null` (previous runs before the start date, air quality beyond about 4.7 days). Training drops those rows; prediction keeps them as NaN, which LightGBM handles. (Task 4 tests `test_training_table_has_target_and_drops_null_rows`, `test_features_keep_nan_dust`.)
3. Running `fetch` twice in the same hour must not duplicate archive rows, and a forecast whose issue time is older than 12 hours must not be published. (Task 3 test `test_append_dedupes`; Task 10 test `test_predict_refuses_stale_forecast`.)
4. A PPK2 export has relative millisecond timestamps, may contain blank rows, and rarely covers whole hours. Hours with under 30 minutes of samples must be excluded from the node ratio, and energy must never be extrapolated to the full hour. (Task 9 test `test_partial_hour_keeps_seconds`; Task 8 test `test_node_ratio_ignores_short_hours`.)
5. With a 150 F store and a small load, most daylight hours will find the store full and the panel current near zero. Such hours look like darkness, and a median over them would report a soiled panel. Hours whose measured energy is under 2 % of the expected energy are treated as store-full and excluded, and the ratio keeps its previous value when fewer than 5 usable hours remain. (Task 8 tests `test_node_ratio_excludes_store_full_hours`, `test_node_ratio_infers_store_full_from_dark_hours`, `test_node_ratio_keeps_previous_when_too_few_hours`.)

## File Structure

| File | Responsibility |
|---|---|
| `forecast/requirements.txt` | pinned Python dependencies |
| `forecast/pytest.ini` | test discovery and import path |
| `forecast/config.toml` | site and node list (panels, tilt, azimuth) |
| `forecast/config.py` | constants, paths, `Site`, `Node`, `load_config`, `utc_ns` |
| `forecast/solar.py` | sun position, clear-sky irradiance, plane-of-array irradiance |
| `forecast/feeds.py` | Open-Meteo requests, error handling, tidy hourly frames |
| `forecast/archive.py` | Parquet archive of issued forecasts; Parquet history store |
| `forecast/features.py` | feature table from a weather frame and sun geometry; training table with the target |
| `forecast/metrics.py` | pinball loss, coverage, quantile sorting |
| `forecast/baselines.py` | climatology, persistence, raw-forecast baselines |
| `forecast/model.py` | train, save, load and apply the three LightGBM boosters |
| `forecast/backtest.py` | rolling monthly back-test and the report tables |
| `forecast/node.py` | clear-sky energy per node, node ratio, node forecast |
| `forecast/simulate.py` | synthetic harvest records for tests and the dry run |
| `forecast/ppk2.py` | PPK2 CSV export to hourly harvest records |
| `forecast/influx.py` | line-protocol writes and harvest reads over the InfluxDB HTTP API |
| `forecast/cli.py` | the commands the timers run |
| `forecast/deploy/*.service`, `*.timer`, `install.sh` | systemd units and the VPS install script |
| `forecast/tests/conftest.py` | shared fixtures: site, node, fixture loader |
| `forecast/tests/fixtures/*.json` | recorded feed responses |
| `forecast/tests/test_*.py` | one test file per module |
| `forecast/README.md` | run, deploy, measure, read the back-test |
| `.gitignore` | ignore the venv, data, models and `.env` |

## Interfaces shared by every task

Records of harvest are a `pandas.DataFrame` with exactly these columns, in any order:

| column | dtype | meaning |
|---|---|---|
| `node` | str | node id from `config.toml` |
| `hour_start` | datetime64[ns, UTC] | start of the hour |
| `energy_j` | float | joules harvested in the hour |
| `seconds` | float | seconds of the hour covered by the measurement |
| `source` | str | `ppk2`, `uplink`, `sim` |
| `store_full` | bool | the store was full during the hour, as reported by the source |

Quantile frames carry columns `q10`, `q50`, `q90` (sky ratio) or `q10_j`, `q50_j`, `q90_j` (joules).

---

### Task 1: Scaffold, config and solar geometry

**Files:**
- Create: `forecast/requirements.txt`, `forecast/pytest.ini`, `forecast/config.toml`, `forecast/config.py`, `forecast/solar.py`, `forecast/tests/conftest.py`, `forecast/tests/test_config.py`, `forecast/tests/test_solar.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: `config.ROOT`, `DATA`, `ARCHIVE`, `HISTORY`, `FORECASTS`, `MODELS`, `OUT` (Paths); `QUANTILES = {"q10": 0.1, "q50": 0.5, "q90": 0.9}`; `HORIZON_H`, `MIN_ELEVATION_DEG`, `USABLE_ELEVATION_DEG`, `K_MAX`, `PANEL_W`, `HISTORY_START`, `LINKE_TURBIDITY`; `Site(name, lat, lon, altitude_m)`, `Node(id, panels, tilt_deg, azimuth_deg)`; `load_config(path) -> tuple[Site, list[Node]]`; `utc_ns(values) -> pd.DatetimeIndex`. `solar.sun_position(site, hour_start) -> DataFrame[elevation, azimuth, zenith]` indexed by `hour_start`; `solar.clearsky(site, hour_start) -> DataFrame[cs_ghi, cs_dni, cs_dhi]`; `solar.clearsky_poa(site, hour_start, tilt_deg, azimuth_deg) -> Series` named `cs_poa`.

- [ ] **Step 1: Pin dependencies, ignore local artefacts, create the environment**

`forecast/requirements.txt`:

```
lightgbm==4.7.0
pvlib==0.16.1
pandas==3.0.6
pyarrow==26.0.0
requests==2.34.2
pytest>=8
```

`forecast/pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = .
```

Append to `.gitignore`:

```
forecast/.venv/
forecast/data/
forecast/models/
forecast/.env
```

Create the environment:

```bash
python -m venv forecast/.venv
forecast/.venv/Scripts/python.exe -m pip install -r forecast/requirements.txt
```

- [ ] **Step 2: Write the site and node config**

`forecast/config.toml`:

```toml
# Site and node list for the harvest forecast. Secrets are not here; see README.

[site]
name = "University City, Sharjah"
lat = 25.29
lon = 55.48
altitude_m = 23

# One entry per node. panels: MP3-37 count on the lid. tilt_deg 0 = flat.
# azimuth_deg 180 = facing south (pvlib convention, ignored when tilt is 0).

[[nodes]]
id = "node-01"
panels = 1
tilt_deg = 0
azimuth_deg = 180

[[nodes]]
id = "node-02"
panels = 1
tilt_deg = 0
azimuth_deg = 180

[[nodes]]
id = "node-03"
panels = 1
tilt_deg = 0
azimuth_deg = 180

[[nodes]]
id = "node-04"
panels = 1
tilt_deg = 0
azimuth_deg = 180

[[nodes]]
id = "node-05"
panels = 1
tilt_deg = 0
azimuth_deg = 180
```

- [ ] **Step 3: Write the failing config and solar tests**

`forecast/tests/conftest.py`:

```python
import json
import pathlib

import pytest

import config

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def site():
    return config.Site("test site", 25.29, 55.48, 23.0)


@pytest.fixture
def node_cfg():
    # named node_cfg so it never shadows the `node` module inside tests
    return config.Node("node-01", 1, 0.0, 180.0)


@pytest.fixture
def fixture_json():
    def load(name):
        return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))

    return load
```

`forecast/tests/test_config.py`:

```python
import pandas as pd

import config


def test_default_config_has_site_and_five_nodes():
    site, nodes = config.load_config()
    assert (site.lat, site.lon) == (25.29, 55.48)
    assert [n.id for n in nodes] == ["node-01", "node-02", "node-03", "node-04", "node-05"]
    assert all(n.panels == 1 and n.tilt_deg == 0 for n in nodes)


def test_load_config_from_path(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[site]\nname="x"\nlat=1.5\nlon=2.5\n[[nodes]]\nid="a"\npanels=2\ntilt_deg=20\n')
    site, nodes = config.load_config(p)
    assert site == config.Site("x", 1.5, 2.5, 0.0)
    assert nodes == [config.Node("a", 2, 20.0, 180.0)]


def test_utc_ns_normalises_strings_and_index():
    idx = config.utc_ns(["2025-06-10T00:00", "2025-06-10T01:00"])
    assert str(idx.dtype) == "datetime64[ns, UTC]"
    assert idx[1] - idx[0] == pd.Timedelta(hours=1)
    again = config.utc_ns(pd.DatetimeIndex(["2025-06-10 00:00"], tz="UTC").as_unit("s"))
    assert str(again.dtype) == "datetime64[ns, UTC]"
```

`forecast/tests/test_solar.py`:

```python
import pandas as pd

import config
import solar


def hours(day):
    return pd.date_range(f"{day} 00:00", f"{day} 23:00", freq="h", tz="UTC")


def test_solar_noon_elevation_matches_noaa(site):
    # NOAA: 2025-06-10 solar noon at 55.48 E is 08:17 UTC, max elevation 87.7 deg.
    hs = config.utc_ns(["2025-06-10T07:47"])  # mid-hour = 08:17
    sp = solar.sun_position(site, hs)
    assert abs(sp["elevation"].iloc[0] - 87.7) < 0.5


def test_sun_is_down_before_sunrise_and_up_after(site):
    # sunrise 2025-06-10 is 01:28 UTC
    sp = solar.sun_position(site, config.utc_ns(["2025-06-10T00:30", "2025-06-10T01:30"]))
    assert sp["elevation"].iloc[0] < 0
    assert sp["elevation"].iloc[1] > 0


def test_december_noon_elevation(site):
    sp = solar.sun_position(site, hours("2025-12-21"))
    assert 40.0 <= sp["elevation"].max() <= 42.0


def test_clearsky_june_noon_and_night(site):
    cs = solar.clearsky(site, hours("2025-06-10"))
    noon = cs.loc[pd.Timestamp("2025-06-10 08:00", tz="UTC")]
    assert abs(noon["cs_ghi"] - 1022) < 15
    assert noon["cs_dni"] > 850 and 80 < noon["cs_dhi"] < 130
    assert cs.loc[pd.Timestamp("2025-06-10 20:00", tz="UTC"), "cs_ghi"] == 0
    assert (cs >= 0).all().all()


def test_clearsky_is_indexed_by_hour_start(site):
    hs = hours("2025-06-10")
    cs = solar.clearsky(site, hs)
    assert cs.index.equals(hs)


def test_flat_poa_equals_ghi_and_tilt_changes_it(site):
    hs = hours("2025-06-10")
    cs = solar.clearsky(site, hs)
    flat = solar.clearsky_poa(site, hs, 0.0, 180.0)
    assert flat.name == "cs_poa"
    assert (flat - cs["cs_ghi"]).abs().max() < 1.0
    tilted = solar.clearsky_poa(site, hs, 20.0, 180.0)
    noon = pd.Timestamp("2025-06-10 08:00", tz="UTC")
    assert tilted[noon] < flat[noon]          # June sun is nearly overhead
    assert tilted.sum() > 0
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest -q`
Expected: errors importing `config` and `solar` (module not found).

- [ ] **Step 5: Write config.py**

`forecast/config.py`:

```python
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
```

- [ ] **Step 6: Write solar.py**

`forecast/solar.py`:

```python
"""Sun geometry and clear-sky irradiance for one site.

Every function takes hour starts and evaluates the sky at the middle of the
hour, which is where Open-Meteo's backward-averaged hourly radiation sits.
"""

from __future__ import annotations

import pandas as pd
import pvlib

import config


def _location(site: config.Site) -> pvlib.location.Location:
    return pvlib.location.Location(site.lat, site.lon, tz="UTC", altitude=site.altitude_m)


def hour_mid(hour_start) -> pd.DatetimeIndex:
    return config.utc_ns(hour_start) + pd.Timedelta(minutes=30)


def sun_position(site: config.Site, hour_start) -> pd.DataFrame:
    hs = config.utc_ns(hour_start)
    sp = _location(site).get_solarposition(hour_mid(hs))
    out = pd.DataFrame(
        {
            "elevation": sp["apparent_elevation"].to_numpy(),
            "azimuth": sp["azimuth"].to_numpy(),
            "zenith": sp["apparent_zenith"].to_numpy(),
        },
        index=hs,
    )
    out.index.name = "hour_start"
    return out


def clearsky(site: config.Site, hour_start) -> pd.DataFrame:
    hs = config.utc_ns(hour_start)
    cs = _location(site).get_clearsky(hour_mid(hs), model="ineichen", linke_turbidity=config.LINKE_TURBIDITY)
    out = pd.DataFrame(
        {"cs_ghi": cs["ghi"].to_numpy(), "cs_dni": cs["dni"].to_numpy(), "cs_dhi": cs["dhi"].to_numpy()},
        index=hs,
    ).clip(lower=0.0)
    out.index.name = "hour_start"
    return out


def clearsky_poa(site: config.Site, hour_start, tilt_deg: float, azimuth_deg: float) -> pd.Series:
    hs = config.utc_ns(hour_start)
    cs = clearsky(site, hs)
    if tilt_deg == 0:
        return cs["cs_ghi"].rename("cs_poa")
    sp = sun_position(site, hs)
    poa = pvlib.irradiance.get_total_irradiance(
        tilt_deg, azimuth_deg, sp["zenith"], sp["azimuth"], cs["cs_dni"], cs["cs_ghi"], cs["cs_dhi"]
    )
    return poa["poa_global"].clip(lower=0.0).rename("cs_poa")
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest -q`
Expected: 9 passed.

- [ ] **Step 8: Commit**

```bash
git add .gitignore forecast/requirements.txt forecast/pytest.ini forecast/config.toml forecast/config.py forecast/solar.py forecast/tests/
git commit -m "start the forecast sub-project with site config and solar geometry"
git push origin main
```

---

### Task 2: Feeds

**Files:**
- Create: `forecast/feeds.py`, `forecast/tests/record_fixtures.py`, `forecast/tests/fixtures/forecast.json`, `air_quality.json`, `previous_runs.json`, `air_quality_history.json`, `satellite.json`, `forecast/tests/test_feeds.py`

**Interfaces:**
- Consumes: `config.Site`, `config.utc_ns`.
- Produces: `feeds.FeedError`; `feeds.get_json(url, params, *, retries=3, pause_s=5.0, session=None) -> dict`; `feeds.hourly_frame(payload, rename=None) -> DataFrame` with `hour_start` first; `feeds.fetch_forecast(site, *, days=3, get=get_json)`; `feeds.fetch_air_quality(site, *, days=5, get=get_json)`; `feeds.fetch_previous_runs(site, start, end, *, get=get_json)`; `feeds.fetch_air_quality_history(site, start, end, *, get=get_json)`; `feeds.fetch_satellite(site, start, end, *, get=get_json)`; `feeds.fetch_range(fetch_one, start, end, step_days=92)`. Constants `WEATHER_VARS`, `AIR_VARS`, `SAT_RENAME`. Weather frames have columns `hour_start` + `WEATHER_VARS`; air frames `hour_start` + `AIR_VARS`; satellite frames `hour_start, sat_ghi, sat_direct, sat_diffuse`.

- [ ] **Step 1: Write the fixture recorder and record the fixtures (network, run once)**

`forecast/tests/record_fixtures.py`:

```python
"""Record real Open-Meteo responses for the tests. Run once, by hand, with network.

    cd forecast && .venv/Scripts/python.exe tests/record_fixtures.py
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # forecast/ on the path when run as a script

import config  # noqa: E402
import feeds  # noqa: E402

OUT = pathlib.Path(__file__).parent / "fixtures"
site, _ = config.load_config()


def save(name, payload):
    OUT.mkdir(exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    print(name, len(payload["hourly"]["time"]), "hours")


if __name__ == "__main__":
    save("forecast", feeds.get_json(feeds.FORECAST_URL, feeds.forecast_params(site, days=2)))
    save("air_quality", feeds.get_json(feeds.AIR_URL, feeds.air_params(site, days=5)))
    save("previous_runs", feeds.get_json(feeds.PREVIOUS_RUNS_URL, feeds.previous_runs_params(site, "2025-06-10", "2025-06-11")))
    save("air_quality_history", feeds.get_json(feeds.AIR_URL, feeds.air_history_params(site, "2025-06-10", "2025-06-11")))
    save("satellite", feeds.get_json(feeds.SATELLITE_URL, feeds.satellite_params(site, "2025-06-10", "2025-06-11")))
```

- [ ] **Step 2: Write the failing feeds tests**

`forecast/tests/test_feeds.py`:

```python
import pandas as pd
import pytest

import feeds


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code, self.ok = payload, status, status < 400

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.responses.pop(0)


def test_get_json_returns_payload(fixture_json):
    s = FakeSession([FakeResponse(fixture_json("forecast"))])
    out = feeds.get_json(feeds.FORECAST_URL, {"a": 1}, session=s)
    assert "hourly" in out
    assert s.calls[0][1] == {"a": 1}


def test_get_json_retries_on_error_payload(fixture_json):
    s = FakeSession([FakeResponse({"error": True, "reason": "The service is overloaded"}), FakeResponse(fixture_json("forecast"))])
    out = feeds.get_json(feeds.FORECAST_URL, {}, session=s, pause_s=0)
    assert "hourly" in out and len(s.calls) == 2


def test_get_json_raises_after_retries():
    s = FakeSession([FakeResponse({"error": True, "reason": "x"})] * 3)
    with pytest.raises(feeds.FeedError, match="x"):
        feeds.get_json(feeds.FORECAST_URL, {}, session=s, retries=3, pause_s=0)


def test_hourly_frame_shifts_labels_to_hour_start(fixture_json):
    f = feeds.hourly_frame(fixture_json("forecast"))
    assert f.columns[0] == "hour_start"
    assert str(f["hour_start"].dtype) == "datetime64[ns, UTC]"
    first_label = pd.Timestamp(fixture_json("forecast")["hourly"]["time"][0], tz="UTC")
    assert f["hour_start"].iloc[0] == first_label - pd.Timedelta(hours=1)
    assert set(feeds.WEATHER_VARS) <= set(f.columns)


def test_fetch_forecast_requests_the_right_variables(site, fixture_json):
    calls = []

    def get(url, params):
        calls.append((url, params))
        return fixture_json("forecast")

    f = feeds.fetch_forecast(site, days=3, get=get)
    url, params = calls[0]
    assert url == feeds.FORECAST_URL
    assert params["latitude"] == site.lat and params["timezone"] == "UTC" and params["forecast_days"] == 3
    assert params["hourly"] == ",".join(feeds.WEATHER_VARS)
    assert list(f.columns) == ["hour_start"] + feeds.WEATHER_VARS


def test_fetch_air_quality(site, fixture_json):
    f = feeds.fetch_air_quality(site, get=lambda url, params: fixture_json("air_quality"))
    assert list(f.columns) == ["hour_start"] + feeds.AIR_VARS
    assert f["aerosol_optical_depth"].notna().sum() > 0


def test_fetch_previous_runs_renames_to_plain_names(site, fixture_json):
    calls = []

    def get(url, params):
        calls.append(params)
        return fixture_json("previous_runs")

    f = feeds.fetch_previous_runs(site, "2025-06-10", "2025-06-11", get=get)
    assert calls[0]["hourly"] == ",".join(v + "_previous_day1" for v in feeds.WEATHER_VARS)
    assert calls[0]["start_date"] == "2025-06-10"
    assert list(f.columns) == ["hour_start"] + feeds.WEATHER_VARS
    assert f["shortwave_radiation"].max() > 800


def test_fetch_satellite_uses_sarah3_and_renames(site, fixture_json):
    calls = []

    def get(url, params):
        calls.append((url, params))
        return fixture_json("satellite")

    f = feeds.fetch_satellite(site, "2025-06-10", "2025-06-11", get=get)
    assert calls[0][0] == feeds.SATELLITE_URL
    assert calls[0][1]["models"] == "eumetsat_sarah3"
    assert list(f.columns) == ["hour_start", "sat_ghi", "sat_direct", "sat_diffuse"]
    assert 950 < f["sat_ghi"].max() < 1100


def test_fetch_air_quality_history_asks_for_dates(site, fixture_json):
    calls = []

    def get(url, params):
        calls.append(params)
        return fixture_json("air_quality_history")

    f = feeds.fetch_air_quality_history(site, "2025-06-10", "2025-06-11", get=get)
    assert calls[0]["start_date"] == "2025-06-10" and calls[0]["end_date"] == "2025-06-11"
    assert list(f.columns) == ["hour_start"] + feeds.AIR_VARS


def test_fetch_range_chunks_and_concatenates():
    seen = []

    def one(start, end):
        seen.append((start, end))
        return pd.DataFrame({"hour_start": [pd.Timestamp(start, tz="UTC")], "x": [1.0]})

    out = feeds.fetch_range(one, "2024-01-01", "2024-04-15", step_days=50)
    assert seen == [("2024-01-01", "2024-02-19"), ("2024-02-20", "2024-04-09"), ("2024-04-10", "2024-04-15")]
    assert len(out) == 3
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest tests/test_feeds.py -q`
Expected: import error for `feeds`.

- [ ] **Step 4: Write feeds.py**

`forecast/feeds.py`:

```python
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
```

- [ ] **Step 5: Record the fixtures, then run the tests**

Run: `cd forecast && .venv/Scripts/python.exe tests/record_fixtures.py`
Expected: five lines like `forecast 48 hours`, `air_quality 120 hours`, `previous_runs 48 hours`, `air_quality_history 48 hours`, `satellite 48 hours`. If the API answers "The service is overloaded" three times, wait a minute and rerun.

Run: `cd forecast && .venv/Scripts/python.exe -m pytest tests/test_feeds.py -q`
Expected: 10 passed.

- [ ] **Step 6: Commit**

```bash
git add forecast/feeds.py forecast/tests/
git commit -m "fetch the Open-Meteo feeds as hourly frames and record test fixtures"
git push origin main
```

---

### Task 3: Archive, the `fetch` command and the VPS archiver

The archive cannot be back-filled, so this task ends with the hourly fetch running on the VPS.

**Files:**
- Create: `forecast/archive.py`, `forecast/cli.py`, `forecast/deploy/forecast-fetch.service`, `forecast/deploy/forecast-fetch.timer`, `forecast/deploy/install.sh`, `forecast/tests/test_archive.py`, `forecast/tests/test_cli.py`

**Interfaces:**
- Consumes: `feeds.fetch_forecast`, `feeds.fetch_air_quality`, `config.ARCHIVE`, `config.HISTORY`.
- Produces: `archive.append(feed, frame, issued_at, root=config.ARCHIVE) -> Path`; `archive.load(feed, root) -> DataFrame` (all months, columns `issued_at` + frame columns); `archive.latest(feed, root) -> tuple[Timestamp, DataFrame] | None`; `archive.save_history(name, frame, root=config.HISTORY) -> Path` (merge on `hour_start`, keep last); `archive.load_history(name, root) -> DataFrame` (empty frame with just `hour_start` when missing). `cli.main(argv) -> int`; `cli.cmd_fetch(args)`; `cli.now_utc()`.

- [ ] **Step 1: Write the failing archive tests**

`forecast/tests/test_archive.py`:

```python
import pandas as pd

import archive


def frame(hours, value):
    return pd.DataFrame({"hour_start": pd.date_range(hours, periods=3, freq="h", tz="UTC"), "x": [value] * 3})


def test_append_creates_monthly_file_with_issue_time(tmp_path):
    issued = pd.Timestamp("2026-10-10 09:02", tz="UTC")
    path = archive.append("forecast", frame("2026-10-10 09:00", 1.0), issued, root=tmp_path)
    assert path == tmp_path / "forecast" / "2026-10.parquet"
    out = pd.read_parquet(path)
    assert list(out.columns) == ["issued_at", "hour_start", "x"]
    assert (out["issued_at"] == issued).all()


def test_append_dedupes(tmp_path):
    issued = pd.Timestamp("2026-10-10 09:02", tz="UTC")
    archive.append("forecast", frame("2026-10-10 09:00", 1.0), issued, root=tmp_path)
    archive.append("forecast", frame("2026-10-10 09:00", 2.0), issued, root=tmp_path)
    out = archive.load("forecast", root=tmp_path)
    assert len(out) == 3 and (out["x"] == 2.0).all()


def test_load_concatenates_months_and_latest_picks_newest(tmp_path):
    archive.append("forecast", frame("2026-09-30 22:00", 1.0), pd.Timestamp("2026-09-30 22:02", tz="UTC"), root=tmp_path)
    archive.append("forecast", frame("2026-10-01 00:00", 2.0), pd.Timestamp("2026-10-01 00:02", tz="UTC"), root=tmp_path)
    assert len(archive.load("forecast", root=tmp_path)) == 6
    issued, latest = archive.latest("forecast", root=tmp_path)
    assert issued == pd.Timestamp("2026-10-01 00:02", tz="UTC")
    assert len(latest) == 3 and "issued_at" not in latest.columns


def test_latest_is_none_when_empty(tmp_path):
    assert archive.latest("forecast", root=tmp_path) is None
    assert list(archive.load("forecast", root=tmp_path).columns) == ["issued_at", "hour_start"]


def test_history_merges_on_hour_start(tmp_path):
    archive.save_history("sat", frame("2025-06-10 00:00", 1.0), root=tmp_path)
    archive.save_history("sat", frame("2025-06-10 02:00", 2.0), root=tmp_path)
    out = archive.load_history("sat", root=tmp_path)
    assert len(out) == 5
    assert out.set_index("hour_start")["x"].loc["2025-06-10 02:00"] == 2.0
    assert list(archive.load_history("missing", root=tmp_path).columns) == ["hour_start"]
```

`forecast/tests/test_cli.py`:

```python
import pandas as pd

import cli


def test_fetch_appends_both_feeds(tmp_path, monkeypatch, site, fixture_json):
    monkeypatch.setattr(cli.config, "ARCHIVE", tmp_path)
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli.feeds, "get_json", lambda url, params, **kw: fixture_json("forecast" if "air" not in url else "air_quality"))
    monkeypatch.setattr(cli, "now_utc", lambda: pd.Timestamp("2026-10-10 09:02", tz="UTC"))
    assert cli.main(["fetch"]) == 0
    assert (tmp_path / "forecast" / "2026-10.parquet").exists()
    assert (tmp_path / "air_quality" / "2026-10.parquet").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest tests/test_archive.py tests/test_cli.py -q`
Expected: import errors for `archive` and `cli`.

- [ ] **Step 3: Write archive.py**

`forecast/archive.py`:

```python
"""Parquet stores: every issued forecast (archive) and the training history."""

from __future__ import annotations

import pathlib

import pandas as pd

import config


def append(feed: str, frame: pd.DataFrame, issued_at: pd.Timestamp, root: pathlib.Path = config.ARCHIVE) -> pathlib.Path:
    path = pathlib.Path(root) / feed / f"{issued_at:%Y-%m}.parquet"
    new = frame.copy()
    new.insert(0, "issued_at", pd.Timestamp(issued_at))
    if path.exists():
        new = pd.concat([pd.read_parquet(path), new], ignore_index=True)
    new = new.drop_duplicates(["issued_at", "hour_start"], keep="last").sort_values(["issued_at", "hour_start"])
    path.parent.mkdir(parents=True, exist_ok=True)
    new.to_parquet(path, index=False)
    return path


def load(feed: str, root: pathlib.Path = config.ARCHIVE) -> pd.DataFrame:
    files = sorted((pathlib.Path(root) / feed).glob("*.parquet"))
    if not files:
        return pd.DataFrame({"issued_at": pd.DatetimeIndex([], tz="UTC"), "hour_start": pd.DatetimeIndex([], tz="UTC")})
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def latest(feed: str, root: pathlib.Path = config.ARCHIVE):
    all_rows = load(feed, root)
    if all_rows.empty:
        return None
    issued = all_rows["issued_at"].max()
    rows = all_rows[all_rows["issued_at"] == issued].drop(columns="issued_at").reset_index(drop=True)
    return pd.Timestamp(issued), rows


def save_history(name: str, frame: pd.DataFrame, root: pathlib.Path = config.HISTORY) -> pathlib.Path:
    path = pathlib.Path(root) / f"{name}.parquet"
    new = frame
    if path.exists():
        new = pd.concat([pd.read_parquet(path), frame], ignore_index=True)
    new = new.drop_duplicates("hour_start", keep="last").sort_values("hour_start")
    path.parent.mkdir(parents=True, exist_ok=True)
    new.to_parquet(path, index=False)
    return path


def load_history(name: str, root: pathlib.Path = config.HISTORY) -> pd.DataFrame:
    path = pathlib.Path(root) / f"{name}.parquet"
    if not path.exists():
        return pd.DataFrame({"hour_start": pd.DatetimeIndex([], tz="UTC")})
    return pd.read_parquet(path)
```

- [ ] **Step 4: Write cli.py with the fetch command**

`forecast/cli.py`:

```python
"""Commands the systemd timers run. Each returns a process exit code."""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

import archive
import config
import feeds

log = logging.getLogger("forecast")


def now_utc() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").floor("min")


def load_site():
    return config.load_config()[0]


def load_nodes():
    return config.load_config()[1]


def cmd_fetch(args) -> int:
    site, issued = load_site(), now_utc()
    for feed, fetch in (("forecast", feeds.fetch_forecast), ("air_quality", feeds.fetch_air_quality)):
        try:
            frame = fetch(site)
        except feeds.FeedError as exc:
            log.error("%s: %s", feed, exc)
            return 1
        path = archive.append(feed, frame, issued, root=config.ARCHIVE)
        log.info("%s: %d hours -> %s", feed, len(frame), path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forecast")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("fetch", help="fetch the live forecast and air-quality feeds into the archive")
    p.set_defaults(func=cmd_fetch)
    return parser


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest -q`
Expected: all pass (25 tests so far).

- [ ] **Step 6: Write the systemd units and the install script**

`forecast/deploy/forecast-fetch.service`:

```ini
[Unit]
Description=Harvest forecast: fetch the live feeds into the archive
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=__FORECAST_DIR__
EnvironmentFile=-__FORECAST_DIR__/.env
ExecStart=__FORECAST_DIR__/.venv/bin/python cli.py fetch
```

`forecast/deploy/forecast-fetch.timer`:

```ini
[Unit]
Description=Run the feed fetch two minutes past every hour

[Timer]
OnCalendar=*-*-* *:02:00
Persistent=true
RandomizedDelaySec=60

[Install]
WantedBy=timers.target
```

`forecast/deploy/install.sh`:

```bash
#!/usr/bin/env bash
# Install or update the forecast service on the VPS. Run from anywhere:
#   bash /opt/sdp-sensor-nodes/forecast/deploy/install.sh
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
cd "$here"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
mkdir -p data models out
for unit in deploy/forecast-*.service deploy/forecast-*.timer; do
  sed "s#__FORECAST_DIR__#$here#g" "$unit" | sudo tee "/etc/systemd/system/$(basename "$unit")" > /dev/null
done
sudo systemctl daemon-reload
for timer in deploy/forecast-*.timer; do
  sudo systemctl enable --now "$(basename "$timer")"
done
systemctl list-timers 'forecast-*' --no-pager
```

- [ ] **Step 7: Commit and push, then deploy the archiver on the VPS**

```bash
git add forecast/archive.py forecast/cli.py forecast/deploy/ forecast/tests/
git commit -m "archive each fetched forecast and run the fetch hourly on the VPS"
git push origin main
```

On the VPS (the user runs these over SSH; Python 3.11 or newer is required):

```bash
sudo git clone https://github.com/ahm-ad-saad/sdp-sensor-nodes /opt/sdp-sensor-nodes   # or git -C /opt/sdp-sensor-nodes pull
sudo chown -R "$USER" /opt/sdp-sensor-nodes
bash /opt/sdp-sensor-nodes/forecast/deploy/install.sh
cd /opt/sdp-sensor-nodes/forecast && .venv/bin/python cli.py fetch
ls data/archive/forecast data/archive/air_quality
```

Expected: one Parquet file per feed named for the current month, and `systemctl list-timers` showing `forecast-fetch.timer` with a next run at :02.

---

### Task 4: Features, history and the training table

**Files:**
- Create: `forecast/features.py`, `forecast/tests/test_features.py`
- Modify: `forecast/cli.py` (add `fetch-history`), `forecast/tests/test_cli.py`

**Interfaces:**
- Consumes: `solar.sun_position`, `solar.clearsky`, `feeds.*`, `archive.save_history`, `archive.load_history`.
- Produces: `features.SUN_FEATURES`, `WEATHER_FEATURES`, `DUST_FEATURES`, `FEATURES` (lists of column names); `features.build_features(site, weather, air=None) -> DataFrame` with columns `hour_start, month` + `FEATURES`, daylight rows only, sorted by `hour_start`; `features.build_training_table(site, weather, air, sat) -> DataFrame` = features + `k` (target), rows with NaN `k` or NaN `k_fc` dropped; `features.sky_ratio(ghi, cs_ghi) -> Series` clipped to `[0, K_MAX]`, NaN where `cs_ghi <= 0`. `cli.cmd_fetch_history(args)` with `--start` (default `config.HISTORY_START`) and `--end` (default yesterday); saves `previous_runs`, `air_quality_history`, `satellite` under `config.HISTORY`.

- [ ] **Step 1: Write the failing feature tests**

`forecast/tests/test_features.py`:

```python
import numpy as np
import pandas as pd

import config
import feeds
import features


def weather_frame(fixture_json, name="previous_runs"):
    rename = {v + "_previous_day1": v for v in feeds.WEATHER_VARS} if name == "previous_runs" else None
    return feeds.hourly_frame(fixture_json(name), rename)[["hour_start"] + feeds.WEATHER_VARS]


def test_features_are_daylight_only_and_named(site, fixture_json):
    f = features.build_features(site, weather_frame(fixture_json), feeds.hourly_frame(fixture_json("air_quality_history")))
    assert list(f.columns) == ["hour_start", "month"] + features.FEATURES
    assert (f["elevation"] > config.MIN_ELEVATION_DEG).all()
    assert 20 <= len(f) <= 30                      # two June days of daylight
    assert f["hour_start"].is_monotonic_increasing
    assert set(f["doy"]) == {161, 162}


def test_forecast_sky_ratio_is_near_one_on_a_clear_day(site, fixture_json):
    f = features.build_features(site, weather_frame(fixture_json))
    noon = f[f["hour"] == 8]
    assert ((noon["k_fc"] > 0.8) & (noon["k_fc"] < 1.1)).all()
    assert ((f["direct_frac"] + f["diffuse_frac"]) - 1.0).abs().max() < 0.05


def test_features_keep_nan_dust(site, fixture_json):
    f = features.build_features(site, weather_frame(fixture_json))
    assert f[features.DUST_FEATURES].isna().all().all()
    assert len(f) > 0


def test_sky_ratio_is_clipped_and_nan_at_zero_clearsky():
    k = features.sky_ratio(pd.Series([500.0, 2000.0, 10.0]), pd.Series([1000.0, 1000.0, 0.0]))
    assert list(k.round(3)[:2]) == [0.5, config.K_MAX]
    assert np.isnan(k.iloc[2])


def test_training_table_has_target_and_drops_null_rows(site, fixture_json):
    w = weather_frame(fixture_json)
    w.loc[w.index[10:14], "shortwave_radiation"] = np.nan        # a gap in the day-ahead feed
    sat = feeds.hourly_frame(fixture_json("satellite"), feeds.SAT_RENAME)
    t = features.build_training_table(site, w, feeds.hourly_frame(fixture_json("air_quality_history")), sat)
    assert "k" in t.columns and t["k"].between(0, config.K_MAX).all()
    assert t["k_fc"].notna().all() and t["k"].notna().all()
    assert t[t["hour"] == 8]["k"].between(0.75, 1.1).all()      # SARAH-3 1015 vs TL=3 clear sky 1022 on 2025-06-10
    assert len(t) < len(features.build_features(site, weather_frame(fixture_json)))


def test_training_table_takes_nothing_but_the_target_from_the_satellite(site, fixture_json):
    w = weather_frame(fixture_json)
    air = feeds.hourly_frame(fixture_json("air_quality_history"))
    sat = feeds.hourly_frame(fixture_json("satellite"), feeds.SAT_RENAME)
    a = features.build_training_table(site, w, air, sat)
    b = features.build_training_table(site, w, air, sat.assign(sat_ghi=sat["sat_ghi"] * 2))
    pd.testing.assert_frame_equal(a[features.FEATURES], b[features.FEATURES])
    assert not a["k"].equals(b["k"])
    assert not any(c.startswith("sat_") for c in features.FEATURES)
```

Add to `forecast/tests/test_cli.py`:

```python
def test_fetch_history_saves_three_history_files(tmp_path, monkeypatch, site, fixture_json):
    monkeypatch.setattr(cli.config, "HISTORY", tmp_path)
    monkeypatch.setattr(cli, "load_site", lambda: site)

    def fake_get(url, params, **kw):
        if "previous-runs" in url:
            return fixture_json("previous_runs")
        if "air-quality" in url:
            return fixture_json("air_quality_history")
        return fixture_json("satellite")

    monkeypatch.setattr(cli.feeds, "get_json", fake_get)
    assert cli.main(["fetch-history", "--start", "2025-06-10", "--end", "2025-06-11"]) == 0
    for name in ("previous_runs", "air_quality_history", "satellite"):
        assert (tmp_path / f"{name}.parquet").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest tests/test_features.py tests/test_cli.py -q`
Expected: import error for `features`; `fetch-history` unknown command.

- [ ] **Step 3: Write features.py**

`forecast/features.py`:

```python
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
```

- [ ] **Step 4: Add fetch-history to cli.py**

Add after `cmd_fetch` in `forecast/cli.py`:

```python
def cmd_fetch_history(args) -> int:
    site = load_site()
    end = args.end or (now_utc() - pd.Timedelta(days=1)).date().isoformat()
    jobs = (
        ("previous_runs", lambda s, e: feeds.fetch_previous_runs(site, s, e)),
        ("air_quality_history", lambda s, e: feeds.fetch_air_quality_history(site, s, e)),
        ("satellite", lambda s, e: feeds.fetch_satellite(site, s, e)),
    )
    for name, one in jobs:
        try:
            frame = feeds.fetch_range(one, args.start, end)
        except feeds.FeedError as exc:
            log.error("%s: %s", name, exc)
            return 1
        frame = frame.dropna(subset=frame.columns[1:], how="all")
        path = archive.save_history(name, frame, root=config.HISTORY)
        log.info("%s: %d hours, first %s -> %s", name, len(frame), frame["hour_start"].min(), path)
    return 0
```

And in `build_parser`, after the `fetch` parser:

```python
    p = sub.add_parser("fetch-history", help="fetch the public training history (day-ahead runs, air quality, satellite)")
    p.add_argument("--start", default=config.HISTORY_START)
    p.add_argument("--end", default=None, help="ISO date, default yesterday")
    p.set_defaults(func=cmd_fetch_history)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Fetch the real history (network, a few minutes)**

Run: `cd forecast && .venv/Scripts/python.exe cli.py fetch-history`
Expected: three log lines; `previous_runs` first hour in 2024 between January and June, roughly 20,000 hourly rows per file. Rerun if overloaded; `save_history` merges, so reruns are safe.

- [ ] **Step 7: Commit**

```bash
git add forecast/features.py forecast/cli.py forecast/tests/
git commit -m "build the sky-model features and fetch the public training history"
git push origin main
```

---

### Task 5: Metrics and baselines

**Files:**
- Create: `forecast/metrics.py`, `forecast/baselines.py`, `forecast/tests/test_metrics.py`, `forecast/tests/test_baselines.py`

**Interfaces:**
- Consumes: `config.QUANTILES`, `config.K_MAX`, feature table columns `hour_start, month, hour, k_fc, k`.
- Produces: `metrics.pinball(y, q, alpha) -> float`; `metrics.coverage_below(y, q) -> float`; `metrics.sort_quantiles(frame) -> DataFrame` (columns `q10, q50, q90` sorted row-wise). `baselines.climatology(train, test) -> DataFrame[q10, q50, q90]` indexed like `test`; `baselines.raw_forecast(train, test) -> DataFrame[q10, q50, q90]`; `baselines.persistence(k_actual, test, train) -> DataFrame[q10, q50, q90]` where `k_actual` is a Series of `k` indexed by `hour_start` covering train and test; `baselines.residual_offsets(train) -> dict(q10=float, q90=float)`; `baselines.METHODS = ("climatology", "persistence", "raw_forecast")`.

- [ ] **Step 1: Write the failing tests**

`forecast/tests/test_metrics.py`:

```python
import numpy as np
import pandas as pd

import metrics


def test_pinball_matches_hand_cases():
    y = np.array([1.0, 1.0])
    assert metrics.pinball(y, np.array([0.5, 1.5]), 0.5) == 0.25            # mean of 0.25, 0.25
    assert np.isclose(metrics.pinball(y, np.array([0.5, 1.5]), 0.1), (0.1 * 0.5 + 0.9 * 0.5) / 2)
    assert metrics.pinball(y, y, 0.9) == 0.0


def test_coverage_below():
    assert metrics.coverage_below(np.array([1.0, 2.0, 3.0, 4.0]), np.array([1.5, 1.5, 1.5, 5.0])) == 0.5


def test_sort_quantiles_fixes_crossing():
    f = pd.DataFrame({"q10": [0.9, 0.1], "q50": [0.5, 0.5], "q90": [0.1, 0.9]})
    s = metrics.sort_quantiles(f)
    assert list(s["q10"]) == [0.1, 0.1] and list(s["q90"]) == [0.9, 0.9]
    assert list(f["q10"]) == [0.9, 0.1]  # input untouched
```

`forecast/tests/test_baselines.py`:

```python
import numpy as np
import pandas as pd

import baselines


def table(start, days, k_fc, k):
    hs = pd.date_range(start, periods=days * 24, freq="h", tz="UTC")
    t = pd.DataFrame({"hour_start": hs, "month": hs.month, "hour": hs.hour})
    t = t[(t["hour"] >= 3) & (t["hour"] <= 13)].reset_index(drop=True)
    rng = np.random.default_rng(0)
    t["k_fc"] = k_fc
    t["k"] = np.clip(k + rng.normal(0, 0.05, len(t)), 0, 1.5)
    return t


def test_climatology_is_per_month_and_hour():
    train = pd.concat([table("2025-01-01", 20, 0.9, 0.7), table("2025-06-01", 20, 0.9, 1.0)], ignore_index=True)
    test = table("2025-06-21", 2, 0.9, 1.0)
    out = baselines.climatology(train, test)
    assert list(out.columns) == ["q10", "q50", "q90"] and len(out) == len(test)
    assert out["q50"].between(0.9, 1.1).all()
    assert (out["q10"] <= out["q50"]).all() and (out["q50"] <= out["q90"]).all()


def test_climatology_falls_back_to_overall_for_unseen_month():
    train = table("2025-06-01", 20, 0.9, 1.0)
    out = baselines.climatology(train, table("2025-12-01", 1, 0.9, 1.0))
    assert out["q50"].between(0.9, 1.1).all()


def test_raw_forecast_centres_on_k_fc_with_residual_band():
    train = table("2025-06-01", 30, 0.9, 0.9)       # unbiased forecast: residuals are noise around 0
    test = table("2025-07-01", 2, 0.8, 0.8)
    out = baselines.raw_forecast(train, test)
    offs = baselines.residual_offsets(train)
    assert -0.15 < offs["q10"] < 0.0 < offs["q90"] < 0.15
    assert (out["q50"] == 0.8).all()
    assert np.allclose(out["q10"], 0.8 + offs["q10"]) and np.allclose(out["q90"], 0.8 + offs["q90"])


def test_raw_forecast_levels_stay_ordered_when_the_forecast_is_biased():
    train = table("2025-06-01", 30, 0.9, 1.0)       # actual sits 0.1 above the forecast: even the 10 % residual is positive
    test = table("2025-07-01", 2, 0.8, 0.9)
    out = baselines.raw_forecast(train, test)
    offs = baselines.residual_offsets(train)
    assert offs["q10"] > 0
    assert (out["q10"] <= out["q50"]).all() and (out["q50"] <= out["q90"]).all()
    assert (out["q10"] == 0.8).all()                  # after sorting, the raw forecast is the lowest level


def test_persistence_uses_the_same_hour_yesterday():
    train = table("2025-06-01", 10, 0.9, 1.0)
    test = table("2025-06-11", 2, 0.9, 1.0)
    k_all = pd.concat([train, test]).set_index("hour_start")["k"]
    out = baselines.persistence(k_all, test, train)
    expected = k_all.reindex(test["hour_start"] - pd.Timedelta(hours=24)).to_numpy()
    assert np.allclose(out["q50"].to_numpy(), expected)
    assert (out["q10"] <= out["q50"]).all() and (out["q90"] >= out["q50"]).all()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest tests/test_metrics.py tests/test_baselines.py -q`
Expected: import errors.

- [ ] **Step 3: Write metrics.py**

`forecast/metrics.py`:

```python
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
```

- [ ] **Step 4: Write baselines.py**

`forecast/baselines.py`:

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add forecast/metrics.py forecast/baselines.py forecast/tests/
git commit -m "add the quantile scores and the three baselines"
git push origin main
```

---

### Task 6: The LightGBM sky model and the `train` command

**Files:**
- Create: `forecast/model.py`, `forecast/tests/test_model.py`
- Modify: `forecast/cli.py` (add `train`), `forecast/tests/test_cli.py`

**Interfaces:**
- Consumes: `features.FEATURES`, `features.build_training_table`, `archive.load_history`, `baselines.residual_offsets`, `metrics.sort_quantiles`.
- Produces: `model.PARAMS`; `model.SkyModel(boosters: dict[str, lgb.Booster], features: list[str], trained_rows: int, last_hour: str)`; `model.train(table, features=FEATURES, valid_frac=0.1, max_rounds=2000) -> SkyModel`; `model.predict(sky, frame) -> DataFrame[q10, q50, q90]` indexed like `frame`, sorted and clipped; `model.save(sky, path)`, `model.load(path) -> SkyModel` (files `q10.txt`, `q50.txt`, `q90.txt`, `meta.json`); `model.synthetic_table(site, start, days, seed=0)` (test helper, daylight rows with a known rule). `cli.cmd_train(args)` writes `config.MODELS/sky/`, `config.MODELS/climatology.parquet` (the training table's `month, hour, k` columns) and `config.MODELS/raw_forecast.json` (residual offsets), then `config.MODELS/choice.json`.

- [ ] **Step 1: Write the failing model tests**

`forecast/tests/test_model.py`:

```python
import json

import numpy as np
import pandas as pd

import features
import metrics
import model


def test_synthetic_table_has_the_expected_shape(site):
    t = model.synthetic_table(site, "2025-01-01", 30)
    assert set(["hour_start", "month", "k"] + features.FEATURES) <= set(t.columns)
    assert 250 < len(t) < 400 and t["k"].between(0, 1.5).all()


def test_train_predict_learns_the_rule_and_orders_levels(site):
    t = model.synthetic_table(site, "2024-06-01", 400)
    sky = model.train(t.iloc[:-500], max_rounds=400)
    test = t.iloc[-500:]
    p = model.predict(sky, test)
    assert list(p.columns) == ["q10", "q50", "q90"] and p.index.equals(test.index)
    assert (p["q10"] <= p["q50"]).all() and (p["q50"] <= p["q90"]).all()
    assert metrics.pinball(test["k"], p["q50"], 0.5) < metrics.pinball(test["k"], np.full(len(test), t["k"].median()), 0.5) * 0.7
    assert 0.03 < metrics.coverage_below(test["k"], p["q10"]) < 0.2
    assert all(b.num_trees() >= 10 for b in sky.boosters.values())


def test_predict_accepts_nan_dust(site):
    t = model.synthetic_table(site, "2024-06-01", 200)
    sky = model.train(t, max_rounds=100)
    test = t.iloc[-20:].copy()
    test[features.DUST_FEATURES] = np.nan
    p = model.predict(sky, test)
    assert p.notna().all().all()


def test_save_and_load_round_trip(site, tmp_path):
    t = model.synthetic_table(site, "2024-06-01", 120)
    sky = model.train(t, max_rounds=100)
    model.save(sky, tmp_path / "sky")
    assert (tmp_path / "sky" / "q50.txt").exists()
    meta = json.loads((tmp_path / "sky" / "meta.json").read_text())
    assert meta["features"] == features.FEATURES and meta["trained_rows"] == len(t)
    back = model.load(tmp_path / "sky")
    pd.testing.assert_frame_equal(model.predict(back, t.iloc[:30]), model.predict(sky, t.iloc[:30]))
```

Add to `forecast/tests/test_cli.py`:

```python
def test_train_writes_models_and_choice(tmp_path, monkeypatch, site):
    import model

    monkeypatch.setattr(cli.config, "MODELS", tmp_path / "models")
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli, "load_training_table", lambda site: model.synthetic_table(site, "2024-06-01", 240))
    assert cli.main(["train"]) == 0
    assert (tmp_path / "models" / "sky" / "q10.txt").exists()
    assert (tmp_path / "models" / "climatology.parquet").exists()
    offs = json.loads((tmp_path / "models" / "raw_forecast.json").read_text())
    assert set(offs) == {"q10", "q90"}
    choice = json.loads((tmp_path / "models" / "choice.json").read_text())
    assert choice["model"] in ("lightgbm", "raw_forecast") and "pinball10" in choice
```

(add `import json` at the top of `test_cli.py`.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest tests/test_model.py tests/test_cli.py -q`
Expected: import error for `model`; `train` unknown.

- [ ] **Step 3: Write model.py**

`forecast/model.py`:

```python
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
```

- [ ] **Step 4: Add the train command to cli.py**

Add these imports at the top of `forecast/cli.py`: `import json`, `import baselines`, `import features`, `import metrics`, `import model`.

Add after `cmd_fetch_history`:

```python
def load_training_table(site) -> pd.DataFrame:
    return features.build_training_table(
        site,
        archive.load_history("previous_runs", root=config.HISTORY),
        archive.load_history("air_quality_history", root=config.HISTORY),
        archive.load_history("satellite", root=config.HISTORY),
    )


def choose_model(table: pd.DataFrame, days: int = 30) -> dict:
    """Score LightGBM against the raw-forecast baseline on the last `days`; publish LightGBM only if no worse at 10 %."""
    cut = table["hour_start"].max() - pd.Timedelta(days=days)
    train_rows, test_rows = table[table["hour_start"] < cut], table[table["hour_start"] >= cut]
    if len(test_rows) < 24 or len(train_rows) < 500:
        return {"model": "raw_forecast", "reason": "too little data to score", "pinball10": {}}
    sky = model.train(train_rows)
    lgb_p = model.predict(sky, test_rows)
    raw_p = baselines.raw_forecast(train_rows, test_rows)
    scores = {
        "lightgbm": metrics.pinball(test_rows["k"], lgb_p["q10"], 0.1),
        "raw_forecast": metrics.pinball(test_rows["k"], raw_p["q10"], 0.1),
    }
    chosen = "lightgbm" if scores["lightgbm"] <= scores["raw_forecast"] else "raw_forecast"
    return {"model": chosen, "pinball10": scores, "scored_hours": int(len(test_rows)), "scored_from": str(cut)}


def cmd_train(args) -> int:
    site = load_site()
    table = load_training_table(site)
    if len(table) < 500:
        log.error("only %d training rows; run fetch-history first", len(table))
        return 1
    config.MODELS.mkdir(parents=True, exist_ok=True)
    sky = model.train(table)
    model.save(sky, config.MODELS / "sky")
    table[["month", "hour", "k"]].to_parquet(config.MODELS / "climatology.parquet", index=False)
    (config.MODELS / "raw_forecast.json").write_text(json.dumps(baselines.residual_offsets(table)), encoding="utf-8")
    choice = {**choose_model(table), "trained_rows": len(table), "last_hour": sky.last_hour, "trained_at": str(now_utc())}
    (config.MODELS / "choice.json").write_text(json.dumps(choice, indent=2), encoding="utf-8")
    log.info("trained on %d rows to %s; publishing %s (%s)", len(table), sky.last_hour, choice["model"], choice.get("pinball10"))
    return 0
```

And in `build_parser`:

```python
    p = sub.add_parser("train", help="train the sky model on the history and pick the model to publish")
    p.set_defaults(func=cmd_train)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest -q`
Expected: all pass (the model tests take a few seconds).

- [ ] **Step 6: Train on the real history**

Run: `cd forecast && .venv/Scripts/python.exe cli.py train`
Expected: a log line like `trained on 7xxx rows to 2026-10-0x ...; publishing lightgbm ({'lightgbm': 0.0xx, 'raw_forecast': 0.0xx})`. Either choice is a valid result; record the two numbers in the commit message.

- [ ] **Step 7: Commit**

```bash
git add forecast/model.py forecast/cli.py forecast/tests/
git commit -m "train the quantile LightGBM sky model and choose what to publish"
git push origin main
```

---

### Task 7: Rolling back-test and the report

**Files:**
- Create: `forecast/backtest.py`, `forecast/tests/test_backtest.py`, `forecast/out/backtest.md`, `forecast/out/backtest.csv`, `forecast/out/backtest_by_month.csv`, `forecast/out/backtest_by_aod.csv`
- Modify: `forecast/cli.py` (add `backtest`)

**Interfaces:**
- Consumes: `model.train/predict`, `baselines.*`, `metrics.*`, `features.FEATURES`, `features.DUST_FEATURES`.
- Produces: `backtest.METHODS = ("lightgbm", "lightgbm_nodust", "climatology", "persistence", "raw_forecast")`; `backtest.year_month(hour_start: Series) -> Series` of ints like `202506`; `backtest.rolling_months(table, min_train_months=6) -> Iterator[tuple[DataFrame, DataFrame]]`; `backtest.run(table, methods=METHODS, max_rounds=2000) -> DataFrame` with columns `hour_start, month, k, cs_ghi, aerosol_optical_depth, method, q10, q50, q90`; `backtest.summarize(preds, by=None) -> DataFrame` with columns `method[, by], hours, pinball10, pinball50, pinball90, cov10, mae_wm2`; `backtest.aod_band(series) -> Series` of `low/mid/high`; `backtest.write_report(preds, out_dir) -> Path` to `backtest.md`.

- [ ] **Step 1: Write the failing back-test tests**

`forecast/tests/test_backtest.py`:

```python
import pandas as pd

import backtest
import model


def test_rolling_months_trains_only_on_the_past(site):
    t = model.synthetic_table(site, "2024-01-01", 300)
    folds = list(backtest.rolling_months(t, min_train_months=6))
    assert len(folds) == 4                                   # Jul, Aug, Sep, Oct
    for train, test in folds:
        assert train["hour_start"].max() < test["hour_start"].min()
        assert test["hour_start"].dt.month.nunique() == 1
    assert folds[0][0]["hour_start"].max() < pd.Timestamp("2024-07-01", tz="UTC")


def test_run_and_summarize(site):
    t = model.synthetic_table(site, "2024-01-01", 250)
    preds = backtest.run(t, max_rounds=150)
    assert set(preds["method"]) == set(backtest.METHODS)
    s = backtest.summarize(preds)
    assert list(s.columns) == ["method", "hours", "pinball10", "pinball50", "pinball90", "cov10", "mae_wm2"]
    s = s.set_index("method")
    assert s.loc["lightgbm", "pinball50"] < s.loc["climatology", "pinball50"]
    assert s.loc["lightgbm", "pinball50"] < s.loc["lightgbm_nodust", "pinball50"]   # the synthetic rule uses aod
    assert (s["cov10"].between(0.0, 0.4)).all()
    by_month = backtest.summarize(preds, by="month")
    assert set(by_month.columns) >= {"method", "month", "pinball10"}
    by_aod = backtest.summarize(preds.assign(aod_band=backtest.aod_band(preds["aerosol_optical_depth"])), by="aod_band")
    assert set(by_aod["aod_band"]) <= {"low", "mid", "high"}


def test_write_report_produces_markdown_and_csv(site, tmp_path):
    t = model.synthetic_table(site, "2024-01-01", 230)
    preds = backtest.run(t, methods=("lightgbm", "raw_forecast"), max_rounds=50)
    path = backtest.write_report(preds, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "| method |" in text and "lightgbm" in text and "raw_forecast" in text
    assert (tmp_path / "backtest.csv").exists() and (tmp_path / "backtest_by_month.csv").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest tests/test_backtest.py -q`
Expected: import error.

- [ ] **Step 3: Write backtest.py**

`forecast/backtest.py`:

```python
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
```

- [ ] **Step 4: Add the backtest command to cli.py**

Add `import backtest` to the imports, then after `cmd_train`:

```python
def cmd_backtest(args) -> int:
    table = load_training_table(load_site())
    if backtest.year_month(table["hour_start"]).nunique() < 8:
        log.error("need at least 8 months of history for a back-test")
        return 1
    preds = backtest.run(table)
    path = backtest.write_report(preds, config.OUT)
    log.info("wrote %s", path)
    print(backtest.summarize(preds).to_string(index=False))
    return 0
```

And in `build_parser`:

```python
    p = sub.add_parser("backtest", help="rolling monthly back-test on the public history; writes out/backtest.md")
    p.set_defaults(func=cmd_backtest)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest -q`
Expected: all pass (the back-test tests take 10 to 30 s).

- [ ] **Step 6: Run the back-test on the real Sharjah history and commit the tables**

Run: `cd forecast && .venv/Scripts/python.exe cli.py backtest`
Expected: a printed table with five methods and `out/backtest.md` written. There is no pass mark; the table is the result. Put the overall pinball10 of `lightgbm` and `raw_forecast` in the commit message.

```bash
git add forecast/backtest.py forecast/cli.py forecast/tests/ forecast/out/
git commit -m "back-test the sky model against the baselines on the Sharjah history"
git push origin main
```

---

### Task 8: Node conversion, node ratio, simulator and the dry run

**Files:**
- Create: `forecast/node.py`, `forecast/simulate.py`, `forecast/tests/test_node.py`, `forecast/tests/test_simulate.py`
- Modify: `forecast/cli.py` (add `dryrun`), `forecast/tests/test_cli.py`

**Interfaces:**
- Consumes: `solar.clearsky_poa`, `solar.sun_position`, `config.Node`, `config.PANEL_W`, `config.USABLE_ELEVATION_DEG`, the records schema.
- Produces: `node.clear_sky_energy_j(site, node, hour_start) -> Series` named `e_clear_j` indexed by `hour_start`; `node.expected_energy_j(site, node, k_actual: Series) -> Series` (= `e_clear_j * k_actual`, indexed by `k_actual.index`); `node.node_ratio(records, expected_j, elevation, previous=1.0, window_days=7, min_hours=5, dark_frac=0.02, min_seconds=1800) -> NodeRatio(ratio, usable_hours, is_default)`; `node.node_forecast(site, node, hours, k_q, ratio) -> DataFrame[hour_start, q10_j, q50_j, q90_j]` with zeros for hours missing from `k_q`. `simulate.harvest_records(site, node, hour_start, k_actual, ratio, store_full=None, source="sim") -> records`. `cli.cmd_dryrun(args)`.

- [ ] **Step 1: Write the failing node and simulator tests**

`forecast/tests/test_node.py`:

```python
import numpy as np
import pandas as pd

import config
import node
import simulate
import solar


def june_hours(days=1, start="2025-06-10"):
    return pd.date_range(start, periods=24 * days, freq="h", tz="UTC")


def elevation(site, hs):
    return solar.sun_position(site, hs)["elevation"]


def records_for(site, nd, days, ratio, store_full_hours=()):
    """Simulated week(s) at k = 0.95 with the given node ratio; returns (records, k)."""
    hs = june_hours(days)
    k = pd.Series(0.95, index=hs)
    full = pd.Series([h.hour in store_full_hours for h in hs], index=hs)
    return simulate.harvest_records(site, nd, hs, k, ratio, store_full=full), k


def test_clear_sky_energy_scales_with_panels_and_rating(site):
    hs = june_hours()
    one = node.clear_sky_energy_j(site, config.Node("a", 1, 0, 180), hs)
    two = node.clear_sky_energy_j(site, config.Node("b", 2, 0, 180), hs)
    assert one.name == "e_clear_j" and one.index.equals(hs)
    noon = pd.Timestamp("2025-06-10 08:00", tz="UTC")
    assert abs(one[noon] - 0.150 * 1022 / 1000 * 3600) < 12       # about 552 J
    assert np.allclose(two, 2 * one)
    assert one[pd.Timestamp("2025-06-10 20:00", tz="UTC")] == 0
    assert 4000 < one.sum() < 4600                                  # 8.23 kWh/m2 x 0.15 W x 3.6


def test_expected_energy_is_clear_sky_times_k(site, node_cfg):
    hs = june_hours()
    k = pd.Series(0.5, index=hs)
    exp = node.expected_energy_j(site, node_cfg, k)
    assert exp.name == "expected_j" and exp.index.equals(hs)
    assert np.allclose(exp, node.clear_sky_energy_j(site, node_cfg, hs) * 0.5)


def test_node_ratio_recovers_the_simulated_ratio(site, node_cfg):
    recs, k = records_for(site, node_cfg, 7, 0.8)
    out = node.node_ratio(recs, node.expected_energy_j(site, node_cfg, k), elevation(site, k.index))
    assert abs(out.ratio - 0.8) < 0.01 and out.usable_hours >= 5 * 7 and not out.is_default


def test_node_ratio_excludes_store_full_hours(site, node_cfg):
    clean, k = records_for(site, node_cfg, 7, 0.8)
    recs, _ = records_for(site, node_cfg, 7, 0.8, store_full_hours=(8, 9, 10))
    expected = node.expected_energy_j(site, node_cfg, k)
    base = node.node_ratio(clean, expected, elevation(site, k.index))
    out = node.node_ratio(recs, expected, elevation(site, k.index))
    assert abs(out.ratio - 0.8) < 0.01
    assert out.usable_hours == base.usable_hours - 3 * 7


def test_node_ratio_infers_store_full_from_dark_hours(site, node_cfg):
    recs, k = records_for(site, node_cfg, 7, 0.8)
    recs = recs.copy()
    midday = recs["hour_start"].dt.hour.between(7, 11)
    recs.loc[midday, "energy_j"] = 0.0                               # panel current gone while the sun is up
    out = node.node_ratio(recs, node.expected_energy_j(site, node_cfg, k), elevation(site, k.index))
    assert abs(out.ratio - 0.8) < 0.01


def test_node_ratio_ignores_short_hours(site, node_cfg):
    clean, k = records_for(site, node_cfg, 7, 0.8)
    expected = node.expected_energy_j(site, node_cfg, k)
    base = node.node_ratio(clean, expected, elevation(site, k.index))
    recs = clean.copy()
    at_five = recs["hour_start"].dt.hour == 5                        # a daylight hour, 7 rows
    recs.loc[at_five, "seconds"] = 600.0
    recs.loc[at_five, "energy_j"] = recs.loc[at_five, "energy_j"] * 0.5   # would drag the ratio down if counted
    out = node.node_ratio(recs, expected, elevation(site, k.index))
    assert abs(out.ratio - 0.8) < 0.01
    assert out.usable_hours == base.usable_hours - 7


def test_node_ratio_keeps_previous_when_too_few_hours(site, node_cfg):
    recs, k = records_for(site, node_cfg, 1, 0.8)
    recs = recs.head(3)
    out = node.node_ratio(recs, node.expected_energy_j(site, node_cfg, k), elevation(site, k.index), previous=0.9)
    assert out.ratio == 0.9 and out.is_default


def test_node_ratio_uses_only_the_window(site, node_cfg):
    old, k_old = records_for(site, node_cfg, 7, 0.5)
    new, _ = records_for(site, node_cfg, 7, 0.8)
    new = new.assign(hour_start=new["hour_start"] + pd.Timedelta(days=7))
    k = pd.concat([k_old, pd.Series(0.95, index=k_old.index + pd.Timedelta(days=7))])
    recs = pd.concat([old, new], ignore_index=True)
    out = node.node_ratio(recs, node.expected_energy_j(site, node_cfg, k), elevation(site, k.index), window_days=7)
    assert abs(out.ratio - 0.8) < 0.01


def test_node_forecast_scales_and_fills_night_with_zero(site, node_cfg):
    hs = june_hours()
    sun = elevation(site, hs).to_numpy()
    day, night = hs[sun > config.MIN_ELEVATION_DEG], hs[sun <= config.MIN_ELEVATION_DEG]
    k_q = pd.DataFrame({"q10": 0.5, "q50": 0.8, "q90": 1.0}, index=day)
    f = node.node_forecast(site, node_cfg, hs, k_q, 0.9)
    assert list(f.columns) == ["hour_start", "q10_j", "q50_j", "q90_j"] and len(f) == 24
    e = node.clear_sky_energy_j(site, node_cfg, hs)
    noon = pd.Timestamp("2025-06-10 08:00", tz="UTC")
    by_hour = f.set_index("hour_start")
    assert abs(by_hour.loc[noon, "q50_j"] - e[noon] * 0.8 * 0.9) < 1e-6
    assert (by_hour.loc[night] == 0).all().all()
    assert (f["q10_j"] <= f["q50_j"]).all() and (f["q50_j"] <= f["q90_j"]).all()
```

`forecast/tests/test_simulate.py`:

```python
import pandas as pd

import node
import simulate


def test_records_follow_schema_and_physics(site, node_cfg):
    hs = pd.date_range("2025-06-10", periods=24, freq="h", tz="UTC")
    k = pd.Series(0.9, index=hs)
    full = pd.Series(False, index=hs)
    full[hs[12]] = True
    r = simulate.harvest_records(site, node_cfg, hs, k, 0.7, store_full=full)
    assert set(r.columns) == {"node", "hour_start", "energy_j", "seconds", "source", "store_full"}
    assert (r["source"] == "sim").all() and (r["seconds"] == 3600).all() and (r["node"] == "node-01").all()
    e = node.clear_sky_energy_j(site, node_cfg, hs)
    noon = pd.Timestamp("2025-06-10 08:00", tz="UTC")
    by_hour = r.set_index("hour_start")
    assert abs(by_hour.loc[noon, "energy_j"] - e[noon] * 0.9 * 0.7) < 1e-6
    assert by_hour.loc[hs[12], "energy_j"] == 0 and by_hour.loc[hs[12], "store_full"]


def test_ratio_can_vary_by_hour(site, node_cfg):
    hs = pd.date_range("2025-06-10", periods=48, freq="h", tz="UTC")
    ratio = pd.Series([0.9] * 24 + [0.5] * 24, index=hs)
    r = simulate.harvest_records(site, node_cfg, hs, pd.Series(1.0, index=hs), ratio)
    day1 = r[r["hour_start"] < hs[24]]["energy_j"].sum()
    day2 = r[r["hour_start"] >= hs[24]]["energy_j"].sum()
    assert abs(day2 / day1 - 0.5 / 0.9) < 0.02
```

Add to `forecast/tests/test_cli.py`:

```python
def test_dryrun_shows_soiling_and_cleaning(tmp_path, monkeypatch, site, capsys):
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli.config, "OUT", tmp_path)
    assert cli.main(["dryrun"]) == 0
    text = capsys.readouterr().out
    rows = {line.split()[0]: float(line.split()[1]) for line in text.splitlines() if line.startswith("day-")}
    assert abs(rows["day-10"] - 0.9) < 0.02
    assert abs(rows["day-17"] - 0.6) < 0.02
    assert abs(rows["day-28"] - 0.9) < 0.02
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest tests/test_node.py tests/test_simulate.py tests/test_cli.py -q`
Expected: import errors for `node`, `simulate`; `dryrun` unknown.

- [ ] **Step 3: Write node.py**

`forecast/node.py`:

```python
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
    min_seconds: float = 1800.0,
) -> NodeRatio:
    """Median of measured / expected over usable hours in the last `window_days`.

    Usable: sun above USABLE_ELEVATION_DEG, at least `min_seconds` measured, expected > 0,
    not flagged store_full, and not "dark" (measured under `dark_frac` of expected, which
    is what a full store looks like from the panel side).
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
    hourly = r["energy_j"] / r["expected_j"]
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
```

- [ ] **Step 4: Write simulate.py**

`forecast/simulate.py`:

```python
"""Synthetic harvest records. Tagged source=sim; for tests and dry runs only."""

from __future__ import annotations

import pandas as pd

import config
import node as node_mod


def harvest_records(site, node, hour_start, k_actual, ratio, store_full=None, source="sim") -> pd.DataFrame:
    hs = config.utc_ns(hour_start)
    e = node_mod.clear_sky_energy_j(site, node, hs)
    k = pd.Series(k_actual, index=hs) if not isinstance(k_actual, pd.Series) else k_actual.reindex(hs).fillna(0.0)
    r = pd.Series(ratio, index=hs) if not isinstance(ratio, pd.Series) else ratio.reindex(hs).ffill().bfill()
    full = pd.Series(False, index=hs) if store_full is None else store_full.reindex(hs).fillna(False).astype(bool)
    energy = (e * k * r).where(~full, 0.0)
    return pd.DataFrame(
        {
            "node": node.id,
            "hour_start": hs,
            "energy_j": energy.to_numpy(),
            "seconds": 3600.0,
            "source": source,
            "store_full": full.to_numpy(),
        }
    )
```

- [ ] **Step 5: Add the dryrun command to cli.py**

Add `import node`, `import simulate`, `import solar` to the imports, then after `cmd_backtest`:

```python
def cmd_dryrun(args) -> int:
    """28 simulated days: soiling from day 11, cleaning on day 18, the store full 10:00-13:00 UTC daily."""
    site = load_site()
    nd = config.Node("sim-01", 1, 0.0, 180.0)
    hs = pd.date_range("2025-06-01", periods=28 * 24, freq="h", tz="UTC")
    k = pd.Series(0.95, index=hs)
    day = pd.Series(((hs - hs[0]).days + 1), index=hs)
    ratio = pd.Series(0.9, index=hs).where(~day.between(11, 17), 0.6)
    full = pd.Series(hs.hour.isin([10, 11, 12]), index=hs)
    recs = simulate.harvest_records(site, nd, hs, k, ratio, store_full=full)
    expected = node.expected_energy_j(site, nd, k)
    elev = solar.sun_position(site, hs)["elevation"]
    previous = 1.0
    for d in range(7, 29):
        upto = recs[day.reindex(recs["hour_start"]).to_numpy() <= d]
        out = node.node_ratio(upto, expected, elev, previous=previous)
        previous = out.ratio
        print(f"day-{d:02d} {out.ratio:.3f} usable={out.usable_hours} default={out.is_default}")
    return 0
```

And in `build_parser`:

```python
    p = sub.add_parser("dryrun", help="simulated node: the node ratio must follow an injected soiling drop and a cleaning")
    p.set_defaults(func=cmd_dryrun)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest -q`
Expected: all pass. Also run `cd forecast && .venv/Scripts/python.exe cli.py dryrun` and read the 22 lines: 0.9 through day 10, falling to 0.6 by day 17, back to 0.9 by day 24 to 28, `default=False` throughout.

- [ ] **Step 7: Commit**

```bash
git add forecast/node.py forecast/simulate.py forecast/cli.py forecast/tests/
git commit -m "convert sky ratios to node energy and track the per-node ratio"
git push origin main
```

---

### Task 9: PPK2 import

**Files:**
- Create: `forecast/ppk2.py`, `forecast/tests/test_ppk2.py`, `forecast/tests/fixtures/ppk2_sample.csv`
- Modify: `forecast/cli.py` (add `import-ppk2`, local records store), `forecast/tests/test_cli.py`

**Interfaces:**
- Consumes: the records schema, `config.utc_ns`.
- Produces: `ppk2.read_csv(path) -> DataFrame[t_ms, current_ua]` (blank and non-numeric rows dropped, sorted, non-increasing timestamps dropped); `ppk2.hourly_energy(samples, start_utc, volts, node_id, source="ppk2") -> records`; `cli.cmd_import_ppk2(args)` with `--node`, `--start` (ISO UTC of the first sample), `--volts` (line voltage, default 3.0), `path`; writes records to `config.DATA / "harvest" / f"{node}.parquet"` through `archive.save_records(node, records)` and `archive.load_records(node)` (merge on `hour_start`, keep last).

- [ ] **Step 1: Write the sample CSV and the failing tests**

`forecast/tests/fixtures/ppk2_sample.csv` is generated in the app's export format (header `Timestamp(ms),Current(uA)`, 10 s between samples, 90 minutes, one blank row, 10 mA for the first hour then 30 mA). `forecast/tests/make_ppk2_sample.py`:

```python
"""Write tests/fixtures/ppk2_sample.csv in the Power Profiler export format. Run once:
    cd forecast && .venv/Scripts/python.exe tests/make_ppk2_sample.py
"""

import pathlib

rows = ["Timestamp(ms),Current(uA)"]
for i in range(0, 541):                      # 0 .. 5,400,000 ms
    t = i * 10000
    if t == 40000:
        rows.append("")                      # the app never writes blank rows, but a hand-edited file might
    rows.append(f"{t},{10000.0 if t < 3600000 else 30000.0:.3f}")
out = pathlib.Path(__file__).parent / "fixtures" / "ppk2_sample.csv"
out.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
print(out, len(rows) - 1, "rows")
```

Run it and commit both the script and the CSV.

`forecast/tests/test_ppk2.py`:

```python
import pathlib

import pandas as pd

import ppk2

SAMPLE = pathlib.Path(__file__).parent / "fixtures" / "ppk2_sample.csv"


def test_read_csv_parses_header_and_drops_blank_rows():
    s = ppk2.read_csv(SAMPLE)
    assert list(s.columns) == ["t_ms", "current_ua"]
    assert len(s) == 541 and s["t_ms"].is_monotonic_increasing
    assert s["current_ua"].iloc[0] == 10000.0 and s["current_ua"].iloc[-1] == 30000.0


def test_read_csv_accepts_digital_columns(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("Timestamp(ms),Current(uA),D0-D7\n0,5.000,00000000\n1000,6.000,00000000\n")
    s = ppk2.read_csv(p)
    assert list(s["current_ua"]) == [5.0, 6.0]


def test_hourly_energy_integrates_current_times_volts():
    s = ppk2.read_csv(SAMPLE)
    r = ppk2.hourly_energy(s, "2026-10-14T06:00:00Z", volts=3.0, node_id="node-01")
    assert set(r.columns) == {"node", "hour_start", "energy_j", "seconds", "source", "store_full"}
    r = r.set_index("hour_start")
    h0 = pd.Timestamp("2026-10-14 06:00", tz="UTC")
    assert abs(r.loc[h0, "energy_j"] - 0.010 * 3.0 * 3600) < 0.5          # 10 mA x 3 V x 1 h = 108 J
    assert abs(r.loc[h0, "seconds"] - 3600) <= 10
    assert (r["source"] == "ppk2").all() and (~r["store_full"]).all() and (r["node"] == "node-01").all()


def test_partial_hour_keeps_seconds():
    s = ppk2.read_csv(SAMPLE)
    r = ppk2.hourly_energy(s, "2026-10-14T06:00:00Z", volts=3.0, node_id="node-01").set_index("hour_start")
    h1 = pd.Timestamp("2026-10-14 07:00", tz="UTC")
    assert abs(r.loc[h1, "seconds"] - 1800) <= 10
    assert abs(r.loc[h1, "energy_j"] - 0.030 * 3.0 * 1800) < 2.0          # not scaled to a full hour


def test_negative_current_counts_as_zero_harvest():
    s = pd.DataFrame({"t_ms": [0, 1000, 2000], "current_ua": [-500.0, -500.0, -500.0]})
    r = ppk2.hourly_energy(s, "2026-10-14T06:00:00Z", volts=3.0, node_id="n")
    assert r["energy_j"].iloc[0] == 0.0 and r["seconds"].iloc[0] == 3.0


def test_recording_gap_adds_neither_seconds_nor_energy():
    s = pd.DataFrame({"t_ms": [0, 1000, 2000, 3000, 3_600_000 + 2000, 3_600_000 + 3000], "current_ua": [10000.0] * 6})
    r = ppk2.hourly_energy(s, "2026-10-14T06:00:00Z", volts=3.0, node_id="n").set_index("hour_start")
    h0, h1 = pd.Timestamp("2026-10-14 06:00", tz="UTC"), pd.Timestamp("2026-10-14 07:00", tz="UTC")
    assert abs(r.loc[h0, "seconds"] - 4.0) < 1e-9
    assert abs(r.loc[h1, "seconds"] - 1.0) < 1e-9                    # the 3,599 s pause is not credited
    assert abs(r.loc[h1, "energy_j"] - 0.010 * 3.0 * 1.0) < 1e-9
```

Add to `forecast/tests/test_cli.py`:

```python
def test_import_ppk2_saves_records(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    monkeypatch.delenv("INFLUX_URL", raising=False)   # local import only; no InfluxDB in tests
    sample = pathlib.Path(__file__).parent / "fixtures" / "ppk2_sample.csv"
    assert cli.main(["import-ppk2", "--node", "node-01", "--start", "2026-10-14T06:00:00Z", "--volts", "3.0", str(sample)]) == 0
    recs = cli.archive.load_records("node-01", root=tmp_path / "harvest")
    assert len(recs) == 2 and (recs["source"] == "ppk2").all()
```

(add `import pathlib` at the top of `test_cli.py`.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest tests/test_ppk2.py tests/test_cli.py -q`
Expected: import error for `ppk2`; `import-ppk2` unknown; `archive.load_records` missing.

- [ ] **Step 3: Write ppk2.py**

`forecast/ppk2.py`:

```python
"""PPK2 (nRF Connect Power Profiler) CSV export to hourly harvest records.

The export header is "Timestamp(ms),Current(uA)" with optional digital columns.
Timestamps are relative to the start of the recording, so the absolute start
time is an argument. The PPK2 sits in ampere-meter mode on the panel line, so
current is panel current and energy is current x an assumed line voltage.
"""

from __future__ import annotations

import pandas as pd

import config

GAP_FACTOR = 5.0  # a dt above this multiple of the typical sample interval is a recording gap


def read_csv(path) -> pd.DataFrame:
    raw = pd.read_csv(path, usecols=[0, 1], skip_blank_lines=True)
    raw.columns = ["t_ms", "current_ua"]
    raw = raw.apply(pd.to_numeric, errors="coerce").dropna()
    raw = raw.sort_values("t_ms")
    raw = raw[raw["t_ms"].diff().fillna(1.0) > 0]
    return raw.reset_index(drop=True)


def hourly_energy(samples: pd.DataFrame, start_utc, volts: float, node_id: str, source: str = "ppk2") -> pd.DataFrame:
    start = config.utc_ns([start_utc])[0]
    t = start + pd.to_timedelta(samples["t_ms"].to_numpy(), unit="ms")
    dt_s = pd.Series(samples["t_ms"].diff().to_numpy() / 1000.0)
    typical = dt_s.median() if dt_s.notna().any() else 0.0
    dt_s = dt_s.fillna(typical)
    # a pause in the recording shows up as one huge dt; nothing is known about the
    # panel during it, so it contributes neither seconds nor energy
    dt_s = dt_s.where(dt_s <= GAP_FACTOR * typical, 0.0)
    amps = samples["current_ua"].clip(lower=0.0).to_numpy() / 1e6
    frame = pd.DataFrame({"hour_start": config.utc_ns(t).floor("h"), "energy_j": amps * volts * dt_s.to_numpy(), "seconds": dt_s.to_numpy()})
    hourly = frame.groupby("hour_start", as_index=False).sum()
    hourly["seconds"] = hourly["seconds"].clip(upper=3600.0)
    hourly.insert(0, "node", node_id)
    hourly["source"] = source
    hourly["store_full"] = False
    return hourly[["node", "hour_start", "energy_j", "seconds", "source", "store_full"]]
```

- [ ] **Step 4: Add the records store to archive.py and the import command to cli.py**

Append to `forecast/archive.py`:

```python
RECORD_COLUMNS = ["node", "hour_start", "energy_j", "seconds", "source", "store_full"]


def save_records(node: str, records: pd.DataFrame, root: pathlib.Path = config.DATA / "harvest") -> pathlib.Path:
    path = pathlib.Path(root) / f"{node}.parquet"
    new = records[RECORD_COLUMNS]
    if path.exists():
        new = pd.concat([pd.read_parquet(path), new], ignore_index=True)
    new = new.drop_duplicates("hour_start", keep="last").sort_values("hour_start")
    path.parent.mkdir(parents=True, exist_ok=True)
    new.to_parquet(path, index=False)
    return path


def load_records(node: str, root: pathlib.Path = config.DATA / "harvest") -> pd.DataFrame:
    path = pathlib.Path(root) / f"{node}.parquet"
    if not path.exists():
        return pd.DataFrame({c: pd.Series(dtype=t) for c, t in zip(RECORD_COLUMNS, ["str", "datetime64[ns, UTC]", "float64", "float64", "str", "bool"])})
    return pd.read_parquet(path)
```

Add `import ppk2` to `cli.py` and, after `cmd_dryrun`:

```python
def cmd_import_ppk2(args) -> int:
    samples = ppk2.read_csv(args.path)
    records = ppk2.hourly_energy(samples, args.start, args.volts, args.node)
    path = archive.save_records(args.node, records, root=config.DATA / "harvest")
    log.info("%s: %d hours from %s -> %s", args.node, len(records), records["hour_start"].min(), path)
    return 0
```

And in `build_parser`:

```python
    p = sub.add_parser("import-ppk2", help="turn a PPK2 CSV export (panel line, ampere-meter mode) into hourly harvest records")
    p.add_argument("path")
    p.add_argument("--node", required=True)
    p.add_argument("--start", required=True, help="UTC time of the first sample, e.g. 2026-10-14T06:00:00Z")
    p.add_argument("--volts", type=float, default=3.0, help="assumed panel-line voltage")
    p.set_defaults(func=cmd_import_ppk2)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add forecast/ppk2.py forecast/archive.py forecast/cli.py forecast/tests/
git commit -m "import PPK2 exports as hourly harvest records"
git push origin main
```

---

### Task 10: InfluxDB, `predict`, `ratio`, `selfcheck` and the remaining timers

**Files:**
- Create: `forecast/influx.py`, `forecast/tests/test_influx.py`, `forecast/deploy/forecast-predict.service`, `forecast-predict.timer`, `forecast-ratio.service`, `forecast-ratio.timer`, `forecast-train.service`, `forecast-train.timer`
- Modify: `forecast/cli.py`, `forecast/tests/test_cli.py`, `forecast/tests/conftest.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `influx.Settings(url, version, token, org, bucket, user, password, database)`; `influx.from_env(env=os.environ) -> Settings`; `influx.line(measurement, tags, fields, ts) -> str`; `influx.write(lines, settings, session=None)` (raises `influx.InfluxError`); `influx.write_forecast(frame, node_id, model_name, issued_at, ratio_default, settings, session=None)`; `influx.write_node_ratio(node_id, day, ratio, usable_hours, settings, session=None)`; `influx.write_harvest(records, settings, session=None)`; `influx.read_harvest(node_id, since, settings, session=None) -> records`. `cli.cmd_predict`, `cli.cmd_ratio`, `cli.cmd_selfcheck`; `cli.predict_frames(site, nodes, issued_at) -> tuple[str, dict[str, DataFrame]]` (pure: model name and one node frame each); `cli.load_ratio_state()`/`save_ratio_state()` on `config.DATA / "node_ratio.json"`.

- [ ] **Step 1: Write the failing InfluxDB tests**

`forecast/tests/test_influx.py`:

```python
import pandas as pd
import pytest

import influx


class FakeResp:
    def __init__(self, status=204, text=""):
        self.status_code, self.text, self.ok = status, text, status < 400


class FakeSession:
    def __init__(self, resp=None):
        self.resp, self.calls = resp or FakeResp(), []

    def post(self, url, params=None, data=None, headers=None, auth=None, json=None, timeout=None):
        self.calls.append({"url": url, "params": params, "data": data, "headers": headers, "auth": auth, "json": json})
        return self.resp

    def get(self, url, params=None, headers=None, auth=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers, "auth": auth})
        return self.resp


V2 = influx.Settings("http://db:8086", "2", "tok", "org1", "sdp", "", "", "")
V1 = influx.Settings("http://db:8086", "1", "", "", "", "u", "p", "sdp")


def test_from_env_reads_both_versions():
    s = influx.from_env({"INFLUX_URL": "http://x:8086/", "INFLUX_VERSION": "2", "INFLUX_TOKEN": "t", "INFLUX_ORG": "o", "INFLUX_BUCKET": "b"})
    assert s == influx.Settings("http://x:8086", "2", "t", "o", "b", "", "", "")
    s = influx.from_env({"INFLUX_URL": "http://x:8086", "INFLUX_VERSION": "1", "INFLUX_USER": "u", "INFLUX_PASSWORD": "p", "INFLUX_DB": "d"})
    assert (s.version, s.user, s.database) == ("1", "u", "d")


def test_line_protocol_formatting():
    ts = pd.Timestamp("2026-10-14 06:00", tz="UTC")
    line = influx.line("harvest", {"node": "node 01", "source": "ppk2"}, {"energy_j": 12.5, "seconds": 3600.0, "store_full": False, "lead_h": 3, "issued_at": "2026-10-14T05:00Z"}, ts)
    # 2026-10-14T06:00Z is 1791957600 s after the epoch (checked with pandas)
    assert line == 'harvest,node=node\\ 01,source=ppk2 energy_j=12.5,seconds=3600.0,store_full=false,lead_h=3i,issued_at="2026-10-14T05:00Z" 1791957600000000000'


def test_write_v2_posts_to_api_v2_with_token():
    s = FakeSession()
    influx.write(["m f=1 1"], V2, session=s)
    c = s.calls[0]
    assert c["url"] == "http://db:8086/api/v2/write" and c["params"] == {"org": "org1", "bucket": "sdp", "precision": "ns"}
    assert c["headers"]["Authorization"] == "Token tok" and c["data"] == "m f=1 1"


def test_write_v1_posts_to_write_with_basic_auth():
    s = FakeSession()
    influx.write(["m f=1 1"], V1, session=s)
    c = s.calls[0]
    assert c["url"] == "http://db:8086/write" and c["params"] == {"db": "sdp", "precision": "ns"} and c["auth"] == ("u", "p")


def test_write_raises_on_failure():
    with pytest.raises(influx.InfluxError):
        influx.write(["m f=1 1"], V2, session=FakeSession(FakeResp(401, "unauthorized")))


def test_write_forecast_lines():
    s = FakeSession()
    f = pd.DataFrame({"hour_start": pd.date_range("2026-10-14 06:00", periods=2, freq="h", tz="UTC"), "q10_j": [1.0, 2.0], "q50_j": [2.0, 3.0], "q90_j": [3.0, 4.0]})
    influx.write_forecast(f, "node-01", "lightgbm", pd.Timestamp("2026-10-14 05:00", tz="UTC"), True, V2, session=s)
    lines = s.calls[0]["data"].splitlines()
    assert lines[0].startswith("harvest_forecast,model=lightgbm,node=node-01 ")
    assert "lead_h=1i" in lines[0] and "lead_h=2i" in lines[1] and "node_ratio_default=true" in lines[0]


def test_read_harvest_v2_parses_flux_csv():
    csv = (
        ",result,table,_start,_stop,_time,_measurement,node,source,energy_j,seconds,store_full\r\n"
        ",_result,0,2026-10-01T00:00:00Z,2026-10-15T00:00:00Z,2026-10-14T06:00:00Z,harvest,node-01,ppk2,108.0,3600,false\r\n"
        ",_result,0,2026-10-01T00:00:00Z,2026-10-15T00:00:00Z,2026-10-14T07:00:00Z,harvest,node-01,ppk2,50.0,1800,true\r\n"
    )
    s = FakeSession(FakeResp(200, csv))
    r = influx.read_harvest("node-01", pd.Timestamp("2026-10-01", tz="UTC"), V2, session=s)
    assert list(r.columns) == influx.RECORD_COLUMNS and len(r) == 2
    assert r["store_full"].tolist() == [False, True] and r["energy_j"].tolist() == [108.0, 50.0]
    assert str(r["hour_start"].dtype) == "datetime64[ns, UTC]"
    assert "node-01" in s.calls[0]["json"]["query"]


def test_read_harvest_v1_parses_json():
    import json

    body = json.dumps({"results": [{"series": [{"name": "harvest", "columns": ["time", "energy_j", "seconds", "store_full", "source"], "values": [["2026-10-14T06:00:00Z", 108.0, 3600, False, "ppk2"]]}]}]})
    s = FakeSession(FakeResp(200, body))
    r = influx.read_harvest("node-01", pd.Timestamp("2026-10-01", tz="UTC"), V1, session=s)
    assert len(r) == 1 and r["node"].iloc[0] == "node-01" and r["energy_j"].iloc[0] == 108.0


def test_read_harvest_empty():
    s = FakeSession(FakeResp(200, "\r\n"))
    r = influx.read_harvest("node-01", pd.Timestamp("2026-10-01", tz="UTC"), V2, session=s)
    assert r.empty and list(r.columns) == influx.RECORD_COLUMNS
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest tests/test_influx.py -q`
Expected: import error.

- [ ] **Step 3: Write influx.py**

`forecast/influx.py`:

```python
"""InfluxDB over its HTTP API, for 1.x (InfluxQL) and 2.x (Flux). No client library."""

from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass

import pandas as pd
import requests

import config

RECORD_COLUMNS = ["node", "hour_start", "energy_j", "seconds", "source", "store_full"]


class InfluxError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    url: str
    version: str
    token: str
    org: str
    bucket: str
    user: str
    password: str
    database: str


def from_env(env=None) -> Settings:
    e = env if env is not None else os.environ
    return Settings(
        e.get("INFLUX_URL", "http://localhost:8086").rstrip("/"),
        e.get("INFLUX_VERSION", "2"),
        e.get("INFLUX_TOKEN", ""),
        e.get("INFLUX_ORG", ""),
        e.get("INFLUX_BUCKET", ""),
        e.get("INFLUX_USER", ""),
        e.get("INFLUX_PASSWORD", ""),
        e.get("INFLUX_DB", ""),
    )


def _tag(v) -> str:
    return str(v).replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")


def _field(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return f"{v}i"
    if isinstance(v, float):
        return repr(float(v))
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def line(measurement: str, tags: dict, fields: dict, ts: pd.Timestamp) -> str:
    tag_part = "".join(f",{k}={_tag(v)}" for k, v in sorted(tags.items()))
    field_part = ",".join(f"{k}={_field(v)}" for k, v in fields.items())
    ns = int(pd.Timestamp(ts).tz_convert("UTC").as_unit("ns").value)
    return f"{measurement}{tag_part} {field_part} {ns}"


def _auth(s: Settings):
    if s.version == "2":
        return {"headers": {"Authorization": f"Token {s.token}"}, "auth": None}
    return {"headers": {}, "auth": (s.user, s.password) if s.user else None}


def write(lines: list[str], s: Settings, session=None) -> None:
    if not lines:
        return
    http = session or requests
    a = _auth(s)
    if s.version == "2":
        url, params = f"{s.url}/api/v2/write", {"org": s.org, "bucket": s.bucket, "precision": "ns"}
    else:
        url, params = f"{s.url}/write", {"db": s.database, "precision": "ns"}
    r = http.post(url, params=params, data="\n".join(lines), headers={**a["headers"], "Content-Type": "text/plain; charset=utf-8"}, auth=a["auth"], timeout=30)
    if not r.ok:
        raise InfluxError(f"write failed: HTTP {r.status_code} {r.text[:200]}")


def write_forecast(frame: pd.DataFrame, node_id: str, model_name: str, issued_at: pd.Timestamp, ratio_default: bool, s: Settings, session=None) -> None:
    issued = pd.Timestamp(issued_at).tz_convert("UTC")
    lines = []
    for _, row in frame.iterrows():
        hs = pd.Timestamp(row["hour_start"]).tz_convert("UTC")
        fields = {
            "q10_j": float(row["q10_j"]),
            "q50_j": float(row["q50_j"]),
            "q90_j": float(row["q90_j"]),
            "lead_h": int(round((hs - issued.floor("h")) / pd.Timedelta(hours=1))),
            "issued_at": issued.strftime("%Y-%m-%dT%H:%MZ"),
            "node_ratio_default": bool(ratio_default),
        }
        lines.append(line("harvest_forecast", {"node": node_id, "model": model_name}, fields, hs))
    write(lines, s, session)


def write_node_ratio(node_id: str, day: pd.Timestamp, ratio: float, usable_hours: int, s: Settings, session=None) -> None:
    write([line("node_ratio", {"node": node_id}, {"ratio": float(ratio), "usable_hours": int(usable_hours)}, pd.Timestamp(day).tz_convert("UTC").floor("D"))], s, session)


def write_harvest(records: pd.DataFrame, s: Settings, session=None) -> None:
    lines = [
        line("harvest", {"node": r["node"], "source": r["source"]}, {"energy_j": float(r["energy_j"]), "seconds": float(r["seconds"]), "store_full": bool(r["store_full"])}, r["hour_start"])
        for _, r in records.iterrows()
    ]
    write(lines, s, session)


def _empty_records() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in zip(RECORD_COLUMNS, ["str", "datetime64[ns, UTC]", "float64", "float64", "str", "bool"])})


def read_harvest(node_id: str, since: pd.Timestamp, s: Settings, session=None) -> pd.DataFrame:
    http = session or requests
    a = _auth(s)
    since_iso = pd.Timestamp(since).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    if s.version == "2":
        flux = (
            f'from(bucket: "{s.bucket}") |> range(start: {since_iso}) '
            f'|> filter(fn: (r) => r._measurement == "harvest" and r.node == "{node_id}") '
            '|> pivot(rowKey: ["_time", "source"], columnKey: ["_field"], valueColumn: "_value")'
        )
        r = http.post(f"{s.url}/api/v2/query", params={"org": s.org}, json={"query": flux, "type": "flux"}, headers={**a["headers"], "Accept": "application/csv"}, auth=a["auth"], timeout=60)
        if not r.ok:
            raise InfluxError(f"query failed: HTTP {r.status_code} {r.text[:200]}")
        if not r.text.strip():
            return _empty_records()
        raw = pd.read_csv(io.StringIO(r.text), comment="#")
        if raw.empty or "_time" not in raw.columns:
            return _empty_records()
        out = pd.DataFrame(
            {
                "node": node_id,
                "hour_start": config.utc_ns(raw["_time"]),
                "energy_j": raw["energy_j"].astype(float),
                "seconds": raw["seconds"].astype(float),
                "source": raw["source"].astype(str) if "source" in raw else "uplink",
                "store_full": raw["store_full"].map(lambda v: str(v).lower() == "true") if "store_full" in raw else False,
            }
        )
    else:
        q = f"SELECT energy_j, seconds, store_full, source FROM harvest WHERE node = '{node_id}' AND time >= '{since_iso}'"
        r = http.get(f"{s.url}/query", params={"db": s.database, "q": q, "epoch": "ns"}, headers=a["headers"], auth=a["auth"], timeout=60)
        if not r.ok:
            raise InfluxError(f"query failed: HTTP {r.status_code} {r.text[:200]}")
        results = json.loads(r.text).get("results", [{}])[0].get("series", [])
        if not results:
            return _empty_records()
        series = results[0]
        raw = pd.DataFrame(series["values"], columns=series["columns"])
        out = pd.DataFrame(
            {
                "node": node_id,
                "hour_start": config.utc_ns(raw["time"]),
                "energy_j": raw["energy_j"].astype(float),
                "seconds": raw["seconds"].astype(float),
                "source": raw["source"].astype(str),
                "store_full": raw["store_full"].astype(bool),
            }
        )
    return out[RECORD_COLUMNS].sort_values("hour_start").reset_index(drop=True)
```

- [ ] **Step 4: Write the failing predict, ratio and selfcheck tests**

Add to `forecast/tests/conftest.py`:

```python
@pytest.fixture
def trained_models(tmp_path, site, monkeypatch):
    """A small trained model set under tmp_path/models, as cmd_train would write it."""
    import json

    import baselines
    import model

    root = tmp_path / "models"
    t = model.synthetic_table(site, "2024-06-01", 150)
    model.save(model.train(t, max_rounds=60), root / "sky")
    t[["month", "hour", "k"]].to_parquet(root / "climatology.parquet", index=False)
    (root / "raw_forecast.json").write_text(json.dumps(baselines.residual_offsets(t)))
    (root / "choice.json").write_text(json.dumps({"model": "lightgbm", "pinball10": {}}))
    monkeypatch.setattr(config, "MODELS", root)
    return root
```

Add to `forecast/tests/test_cli.py`:

```python
class FakeInflux:
    def __init__(self):
        self.lines = []

    def post(self, url, params=None, data=None, headers=None, auth=None, json=None, timeout=None):
        if data:
            self.lines += data.splitlines()
        return type("R", (), {"ok": True, "status_code": 204, "text": ""})()


def seed_archive(root, fixture_json, issued):
    import archive
    import feeds

    archive.append("forecast", feeds.fetch_forecast(cli.load_site(), get=lambda u, p: fixture_json("forecast")), issued, root=root)
    archive.append("air_quality", feeds.fetch_air_quality(cli.load_site(), get=lambda u, p: fixture_json("air_quality")), issued, root=root)


def first_hour(fixture_json):
    return pd.Timestamp(fixture_json("forecast")["hourly"]["time"][0], tz="UTC") - pd.Timedelta(hours=1)


def test_predict_writes_36_hours_per_node(tmp_path, monkeypatch, site, fixture_json, trained_models):
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli, "load_nodes", lambda: [cli.config.Node("node-01", 1, 0, 180), cli.config.Node("node-02", 2, 0, 180)])
    monkeypatch.setattr(cli.config, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    monkeypatch.setattr(cli.config, "FORECASTS", tmp_path / "forecasts")
    issued = first_hour(fixture_json) + pd.Timedelta(hours=6)
    seed_archive(tmp_path / "archive", fixture_json, issued)
    monkeypatch.setattr(cli, "now_utc", lambda: issued + pd.Timedelta(minutes=10))
    fake = FakeInflux()
    monkeypatch.setattr(cli, "influx_session", lambda: fake)
    monkeypatch.setenv("INFLUX_URL", "http://db:8086")
    assert cli.main(["predict"]) == 0
    assert len(fake.lines) == 72 and all(l.startswith("harvest_forecast,model=lightgbm,node=node-0") for l in fake.lines)
    assert all("node_ratio_default=true" in l for l in fake.lines)
    saved = list((tmp_path / "forecasts").glob("*.parquet"))
    assert len(saved) == 1 and len(pd.read_parquet(saved[0])) == 72


def test_predict_refuses_stale_forecast(tmp_path, monkeypatch, site, fixture_json, trained_models):
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli.config, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    monkeypatch.setattr(cli.config, "FORECASTS", tmp_path / "forecasts")
    issued = first_hour(fixture_json)
    seed_archive(tmp_path / "archive", fixture_json, issued)
    monkeypatch.setattr(cli, "now_utc", lambda: issued + pd.Timedelta(hours=13))
    fake = FakeInflux()
    monkeypatch.setattr(cli, "influx_session", lambda: fake)
    assert cli.main(["predict"]) == 0
    assert all(",model=climatology," in l for l in fake.lines) and len(fake.lines) == 36 * 5


def test_predict_uses_raw_forecast_when_no_models(tmp_path, monkeypatch, site, fixture_json):
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli.config, "MODELS", tmp_path / "nomodels")
    monkeypatch.setattr(cli.config, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    monkeypatch.setattr(cli.config, "FORECASTS", tmp_path / "forecasts")
    issued = first_hour(fixture_json) + pd.Timedelta(hours=6)
    seed_archive(tmp_path / "archive", fixture_json, issued)
    monkeypatch.setattr(cli, "now_utc", lambda: issued)
    fake = FakeInflux()
    monkeypatch.setattr(cli, "influx_session", lambda: fake)
    assert cli.main(["predict"]) == 0
    assert all(",model=raw_forecast," in l for l in fake.lines)


def test_predict_keeps_archive_and_fails_when_influx_down(tmp_path, monkeypatch, site, fixture_json, trained_models):
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli.config, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    monkeypatch.setattr(cli.config, "FORECASTS", tmp_path / "forecasts")
    issued = first_hour(fixture_json) + pd.Timedelta(hours=6)
    seed_archive(tmp_path / "archive", fixture_json, issued)
    monkeypatch.setattr(cli, "now_utc", lambda: issued)

    class Down:
        def post(self, *a, **kw):
            raise cli.requests.ConnectionError("down")

    monkeypatch.setattr(cli, "influx_session", lambda: Down())
    assert cli.main(["predict"]) == 1
    assert len(list((tmp_path / "forecasts").glob("*.parquet"))) == 1


def test_ratio_reads_harvest_and_writes_state(tmp_path, monkeypatch, site, fixture_json):
    import simulate
    import solar

    nd = cli.config.Node("node-01", 1, 0, 180)
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli, "load_nodes", lambda: [nd])
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    hs = pd.date_range("2025-06-03", periods=8 * 24, freq="h", tz="UTC")
    sat = pd.DataFrame({"hour_start": hs, "sat_ghi": solar.clearsky(site, hs)["cs_ghi"].to_numpy() * 0.95, "sat_direct": 0.0, "sat_diffuse": 0.0})
    monkeypatch.setattr(cli.feeds, "fetch_satellite", lambda site, s, e, **kw: sat)
    recs = simulate.harvest_records(site, nd, hs, pd.Series(0.95, index=hs), 0.7)
    monkeypatch.setattr(cli.influx, "read_harvest", lambda node_id, since, settings, session=None: recs)
    fake = FakeInflux()
    monkeypatch.setattr(cli, "influx_session", lambda: fake)
    monkeypatch.setattr(cli, "now_utc", lambda: hs[-1] + pd.Timedelta(days=2))
    assert cli.main(["ratio"]) == 0
    state = json.loads((tmp_path / "node_ratio.json").read_text())
    assert abs(state["node-01"]["ratio"] - 0.7) < 0.01 and not state["node-01"]["is_default"]
    assert fake.lines and fake.lines[0].startswith("node_ratio,node=node-01 ratio=0.")


def test_selfcheck_prints_ages(tmp_path, monkeypatch, site, fixture_json, trained_models, capsys):
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli.config, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    seed_archive(tmp_path / "archive", fixture_json, first_hour(fixture_json))
    assert cli.main(["selfcheck"]) == 0
    out = capsys.readouterr().out
    assert "forecast" in out and "air_quality" in out and "sky model" in out and "node-01" in out
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest tests/test_cli.py -q`
Expected: `predict`, `ratio`, `selfcheck` unknown; `influx_session` missing.

- [ ] **Step 6: Add predict, ratio and selfcheck to cli.py**

Add `import influx`, `import requests`, `import os` to the imports. Then after `cmd_import_ppk2`:

```python
STALE_FORECAST = pd.Timedelta(hours=12)


def influx_session():
    return requests.Session()


def load_ratio_state() -> dict:
    path = config.DATA / "node_ratio.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_ratio_state(state: dict) -> None:
    config.DATA.mkdir(parents=True, exist_ok=True)
    (config.DATA / "node_ratio.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def sky_levels(site, issued_at: pd.Timestamp):
    """Sky-ratio levels for the next HORIZON_H hours and the name of the method that produced them."""
    hours = pd.date_range(issued_at.floor("h"), periods=config.HORIZON_H, freq="h", tz="UTC")
    latest = archive.latest("forecast", root=config.ARCHIVE)
    air = archive.latest("air_quality", root=config.ARCHIVE)
    choice_path = config.MODELS / "choice.json"
    choice = json.loads(choice_path.read_text(encoding="utf-8"))["model"] if choice_path.exists() else "raw_forecast"
    if latest is None or issued_at - latest[0] > STALE_FORECAST:
        log.warning("no fresh forecast in the archive; publishing climatology")
        clim_path = config.MODELS / "climatology.parquet"
        if not clim_path.exists():
            raise RuntimeError("no forecast and no climatology; run fetch and train")
        clim = pd.read_parquet(clim_path)
        sun = solar.sun_position(site, hours)
        test = pd.DataFrame({"hour_start": hours, "month": hours.month, "hour": hours.hour, "k_fc": 0.0}, index=hours)
        test = test[sun["elevation"] > config.MIN_ELEVATION_DEG]
        return "climatology", baselines.climatology(clim, test)
    weather = latest[1]
    air_frame = air[1] if air is not None and issued_at - air[0] <= STALE_FORECAST else None
    if air_frame is None:
        log.warning("no fresh air-quality feed; dust features left empty")
    f = features.build_features(site, weather, air_frame)
    f = f[f["hour_start"].isin(hours)].set_index("hour_start", drop=False)
    sky_path = config.MODELS / "sky" / "meta.json"
    if choice == "lightgbm" and sky_path.exists():
        return "lightgbm", model.predict(model.load(config.MODELS / "sky"), f)
    offs_path = config.MODELS / "raw_forecast.json"
    offs = json.loads(offs_path.read_text(encoding="utf-8")) if offs_path.exists() else {"q10": -0.15, "q90": 0.05}
    mid = f["k_fc"].to_numpy(dtype=float)
    raw = pd.DataFrame({"q10": mid + offs["q10"], "q50": mid, "q90": mid + offs["q90"]}, index=f.index)
    return "raw_forecast", metrics.sort_quantiles(raw.clip(lower=0.0, upper=config.K_MAX))


def predict_frames(site, nodes, issued_at: pd.Timestamp):
    hours = pd.date_range(issued_at.floor("h"), periods=config.HORIZON_H, freq="h", tz="UTC")
    method, k_q = sky_levels(site, issued_at)
    state = load_ratio_state()
    frames = {}
    for nd in nodes:
        ratio = float(state.get(nd.id, {}).get("ratio", 1.0))
        frames[nd.id] = node.node_forecast(site, nd, hours, k_q, ratio)
    return method, frames


def cmd_predict(args) -> int:
    site, nodes, issued = load_site(), load_nodes(), now_utc()
    try:
        method, frames = predict_frames(site, nodes, issued)
    except RuntimeError as exc:
        log.error("%s", exc)
        return 1
    state = load_ratio_state()
    config.FORECASTS.mkdir(parents=True, exist_ok=True)
    all_rows = pd.concat([f.assign(node=n, model=method, issued_at=issued) for n, f in frames.items()], ignore_index=True)
    all_rows.to_parquet(config.FORECASTS / f"{issued:%Y%m%dT%H%M}.parquet", index=False)
    settings = influx.from_env()
    try:
        session = influx_session()
        for n, f in frames.items():
            is_default = bool(state.get(n, {}).get("is_default", True))
            influx.write_forecast(f, n, method, issued, is_default, settings, session)
    except (influx.InfluxError, requests.RequestException) as exc:
        log.error("InfluxDB write failed, forecast kept in %s: %s", config.FORECASTS, exc)
        return 1
    log.info("published %s levels for %d nodes issued %s", method, len(frames), issued)
    return 0


def cmd_ratio(args) -> int:
    site, nodes, now = load_site(), load_nodes(), now_utc()
    since = now - pd.Timedelta(days=9)
    try:
        sat = feeds.fetch_satellite(site, since.date().isoformat(), now.date().isoformat())
    except feeds.FeedError as exc:
        log.error("satellite feed: %s", exc)
        return 1
    sat = sat.dropna(subset=["sat_ghi"])
    if sat.empty:
        log.error("satellite feed returned no hours since %s", since.date())
        return 1
    hs = config.utc_ns(sat["hour_start"])
    cs = solar.clearsky(site, hs)
    k_actual = features.sky_ratio(pd.Series(sat["sat_ghi"].to_numpy(), index=hs), cs["cs_ghi"]).fillna(0.0)
    elev = solar.sun_position(site, hs)["elevation"]
    settings, session, state = influx.from_env(), influx_session(), load_ratio_state()
    failed = []
    for nd in nodes:
        prior = state.get(nd.id, {})
        try:
            records = influx.read_harvest(nd.id, since, settings, session)
        except (influx.InfluxError, requests.RequestException) as exc:
            log.error("%s: read failed: %s", nd.id, exc)
            failed.append(nd.id)
            continue
        out = node.node_ratio(records, node.expected_energy_j(site, nd, k_actual), elev, previous=float(prior.get("ratio", 1.0)))
        # a kept-previous ratio is still a measured one if the previous value was measured
        is_default = bool(out.is_default and prior.get("is_default", True))
        try:
            influx.write_node_ratio(nd.id, now, out.ratio, out.usable_hours, settings, session)
        except (influx.InfluxError, requests.RequestException) as exc:
            log.error("%s: write failed: %s", nd.id, exc)
            failed.append(nd.id)
            continue
        state[nd.id] = {"ratio": out.ratio, "usable_hours": out.usable_hours, "is_default": is_default, "updated": str(now)}
        log.info("%s: ratio %.3f from %d usable hours%s", nd.id, out.ratio, out.usable_hours, " (previous kept)" if out.is_default else "")
    save_ratio_state(state)
    if failed:
        log.error("ratio update failed for %s", ", ".join(failed))
        return 1
    return 0


def cmd_selfcheck(args) -> int:
    now = now_utc()
    for feed in ("forecast", "air_quality"):
        latest = archive.latest(feed, root=config.ARCHIVE)
        print(f"{feed:14s} {'none' if latest is None else f'issued {latest[0]}  age {now - latest[0]}'}")
    meta = config.MODELS / "sky" / "meta.json"
    if meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        choice = json.loads((config.MODELS / "choice.json").read_text(encoding="utf-8")) if (config.MODELS / "choice.json").exists() else {}
        print(f"sky model      rows {m['trained_rows']} to {m['last_hour']}; publishing {choice.get('model', '?')}")
    else:
        print("sky model      none")
    state = load_ratio_state()
    for nd in load_nodes():
        s = state.get(nd.id)
        print(f"{nd.id:14s} {'ratio default 1.0' if not s else f'ratio {s['ratio']:.3f} usable {s['usable_hours']} updated {s['updated']}'}")
    return 0
```

And in `build_parser`:

```python
    p = sub.add_parser("predict", help="publish 36 hours of q10/q50/q90 joules per node to InfluxDB")
    p.set_defaults(func=cmd_predict)
    p = sub.add_parser("ratio", help="update each node's ratio from the last week of harvest records")
    p.set_defaults(func=cmd_ratio)
    p = sub.add_parser("selfcheck", help="print the age of every feed, model and node ratio")
    p.set_defaults(func=cmd_selfcheck)
```

Also make `cmd_import_ppk2` push the records to InfluxDB when it is configured, so the `ratio` step can see them. Replace its body with:

```python
def cmd_import_ppk2(args) -> int:
    samples = ppk2.read_csv(args.path)
    records = ppk2.hourly_energy(samples, args.start, args.volts, args.node)
    path = archive.save_records(args.node, records, root=config.DATA / "harvest")
    log.info("%s: %d hours from %s -> %s", args.node, len(records), records["hour_start"].min(), path)
    if os.environ.get("INFLUX_URL"):
        try:
            influx.write_harvest(records, influx.from_env(), influx_session())
        except (influx.InfluxError, requests.RequestException) as exc:
            log.error("InfluxDB write failed, records kept locally: %s", exc)
            return 1
        log.info("wrote %d harvest rows to InfluxDB", len(records))
    return 0
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd forecast && .venv/Scripts/python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 8: Write the remaining systemd units**

`forecast/deploy/forecast-predict.service`:

```ini
[Unit]
Description=Harvest forecast: publish 36-hour levels per node
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=__FORECAST_DIR__
EnvironmentFile=-__FORECAST_DIR__/.env
ExecStart=__FORECAST_DIR__/.venv/bin/python cli.py predict
```

`forecast/deploy/forecast-predict.timer`:

```ini
[Unit]
Description=Publish the forecast twelve minutes past every hour, after the fetch

[Timer]
OnCalendar=*-*-* *:12:00
Persistent=true

[Install]
WantedBy=timers.target
```

`forecast/deploy/forecast-ratio.service`:

```ini
[Unit]
Description=Harvest forecast: update each node's ratio from harvest records
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=__FORECAST_DIR__
EnvironmentFile=-__FORECAST_DIR__/.env
ExecStart=__FORECAST_DIR__/.venv/bin/python cli.py ratio
```

`forecast/deploy/forecast-ratio.timer`:

```ini
[Unit]
Description=Update node ratios daily at 03:30 UTC (the satellite feed runs about 1.5 days behind)

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

`forecast/deploy/forecast-train.service`:

```ini
[Unit]
Description=Harvest forecast: extend the history and retrain the sky model
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=__FORECAST_DIR__
EnvironmentFile=-__FORECAST_DIR__/.env
ExecStart=/bin/sh -c '__FORECAST_DIR__/.venv/bin/python cli.py fetch-history --start "$(date -u -d "-14 days" +%%F)" && __FORECAST_DIR__/.venv/bin/python cli.py train'
```

`forecast/deploy/forecast-train.timer`:

```ini
[Unit]
Description=Retrain weekly on Monday 04:00 UTC

[Timer]
OnCalendar=Mon *-*-* 04:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 9: Commit, then finish the VPS deployment**

```bash
git add forecast/influx.py forecast/cli.py forecast/deploy/ forecast/tests/
git commit -m "publish node forecasts and node ratios to InfluxDB on timers"
git push origin main
```

On the VPS (the user): find the InfluxDB version with `influx version` (2.x) or `influxd version` / `curl -s localhost:8086/ping -I` (1.x answers with `X-Influxdb-Version: 1.x`), then write `/opt/sdp-sensor-nodes/forecast/.env`:

```
# InfluxDB 2.x
INFLUX_URL=http://localhost:8086
INFLUX_VERSION=2
INFLUX_TOKEN=...
INFLUX_ORG=...
INFLUX_BUCKET=...
# InfluxDB 1.x instead:
# INFLUX_VERSION=1
# INFLUX_USER=...
# INFLUX_PASSWORD=...
# INFLUX_DB=...
```

Then:

```bash
cd /opt/sdp-sensor-nodes && git pull
bash forecast/deploy/install.sh
cd forecast
.venv/bin/python cli.py fetch-history      # a few minutes
.venv/bin/python cli.py train
set -a; . ./.env; set +a; .venv/bin/python cli.py predict
.venv/bin/python cli.py selfcheck
```

Expected: `predict` logs `published lightgbm levels for 5 nodes` (or `raw_forecast`, as chosen by `train`), and in Grafana a query on `harvest_forecast` shows 36 points per node. `systemctl list-timers 'forecast-*'` shows four timers.

---

### Task 11: README and the spec's status

**Files:**
- Create: `forecast/README.md`
- Modify: `docs/superpowers/specs/2026-10-05-harvest-forecast-design.md` (status line and the "Inputs verified" section), `README.md` (one line pointing at `forecast/`)

- [ ] **Step 1: Write forecast/README.md**

```markdown
# Harvest forecast

Server-side forecast of the solar energy each node will harvest in each of
the next 36 hours, at the 10, 50 and 90 % levels. Design reasoning is in
`docs/superpowers/specs/2026-10-05-harvest-forecast-design.md`; the build
plan is `docs/superpowers/plans/2026-10-10-harvest-forecast.md`.

    harvest [J] = clear-sky energy (pvlib) x sky ratio (LightGBM) x node ratio (measured)

## Run locally

```bash
python -m venv forecast/.venv
forecast/.venv/Scripts/python.exe -m pip install -r forecast/requirements.txt
cd forecast
.venv/Scripts/python.exe -m pytest              # no network needed
.venv/Scripts/python.exe cli.py fetch-history   # public history since 2024-02 (network, minutes)
.venv/Scripts/python.exe cli.py train
.venv/Scripts/python.exe cli.py backtest        # writes out/backtest.md
.venv/Scripts/python.exe cli.py dryrun          # simulated node, soiling and cleaning
```

## Commands

| command | what it does | timer on the VPS |
|---|---|---|
| `fetch` | live forecast + air quality into `data/archive/` | hourly :02 |
| `predict` | 36 h of `q10_j q50_j q90_j` per node to InfluxDB `harvest_forecast` | hourly :12 |
| `ratio` | node ratio from the last week of `harvest` records to InfluxDB `node_ratio` | daily 03:30 UTC |
| `fetch-history`, `train` | extend the public history, retrain, choose LightGBM or the raw forecast | weekly Mon 04:00 UTC |
| `backtest` | rolling monthly comparison against the baselines | by hand |
| `import-ppk2` | PPK2 CSV export to hourly `harvest` records | by hand |
| `dryrun` | simulated node sanity check | by hand |
| `selfcheck` | age of every feed, model and node ratio | by hand |

## Deploy

```bash
sudo git clone https://github.com/ahm-ad-saad/sdp-sensor-nodes /opt/sdp-sensor-nodes
bash /opt/sdp-sensor-nodes/forecast/deploy/install.sh
```

Secrets go in `forecast/.env` (not committed): `INFLUX_URL`, `INFLUX_VERSION` (`1` or `2`),
and for 2.x `INFLUX_TOKEN INFLUX_ORG INFLUX_BUCKET`, for 1.x `INFLUX_USER INFLUX_PASSWORD INFLUX_DB`.

## Measuring harvest with a PPK2

Put the PPK2 in ampere-meter mode between the panel (VIN side) and the PMIC
input (VOUT side), record in the Power Profiler app, export CSV with the
default Timestamp and Current columns, then:

```bash
.venv/bin/python cli.py import-ppk2 --node node-01 --start 2026-10-14T06:00:00Z --volts 3.0 export.csv
```

`--start` is the UTC time of the first sample; the export only has relative
milliseconds. `--volts` is the assumed panel-line voltage; a constant error
there scales the node ratio and cancels out. Hours where the store is full
show near-zero panel current and are dropped from the ratio automatically.

## InfluxDB measurements

| measurement | tags | fields | time |
|---|---|---|---|
| `harvest` | node, source | energy_j, seconds, store_full | start of hour |
| `harvest_forecast` | node, model | q10_j, q50_j, q90_j, lead_h, issued_at, node_ratio_default | start of hour |
| `node_ratio` | node | ratio, usable_hours | day |

## Reading the back-test

`out/backtest.md` compares `lightgbm`, `lightgbm_nodust`, `climatology`,
`persistence` and `raw_forecast` on rolling monthly folds. Lower pinball is
better; `cov10` should sit near 0.10. There is no pass mark: the table is
the result, and `train` publishes LightGBM only when its 10 % pinball on the
last 30 days is no worse than the raw forecast's.
```

- [ ] **Step 2: Update the spec's status and record the verified inputs**

In `docs/superpowers/specs/2026-10-05-harvest-forecast-design.md` change `Status: draft, waiting for review` to `Status: approved 2026-10-10; plan at docs/superpowers/plans/2026-10-10-harvest-forecast.md` and add after the feeds table:

```markdown
Verified 2026-10-10 by live requests:

- The satellite endpoint must be called with `models=eumetsat_sarah3`; without it the
  service silently returns ERA5 reanalysis. SARAH-3 is complete at the site back to at
  least 2022-06 and runs about 1.5 days behind. `eumetsat_lsa_saf_iodc` is under an hour
  behind but starts only in 2025 with gaps; `satellite_radiation_seamless` has holes.
- June 2025 daily sums: ERA5 / SARAH-3 = 0.92, day-ahead forecast / SARAH-3 = 0.95,
  NASA POWER / SARAH-3 = 0.87 (NASA labels hours by interval start, Open-Meteo by
  interval end). The "actual" is therefore only known to about 10 %; the node ratio
  absorbs the constant part.
- Previous-runs day-ahead values exist from between 2024-01-10 and 2024-06-10; low, mid
  and high cloud cover are null at one-day lead, so only total cloud cover is a feature.
- Open-Meteo's hourly value at HH:00 is the mean over the preceding hour, so rows are keyed
  on hour start and sun geometry is evaluated at HH-0:30.
- PPK2 CSV export header is `Timestamp(ms),Current(uA)` (optionally `D0-D7`), timestamps
  relative to the recording start (from the Power Profiler app source).
```

Add to the root `README.md` under "Design docs": `` - `forecast/` — harvest forecasting service (see `forecast/README.md`) ``.

- [ ] **Step 3: Commit**

```bash
git add forecast/README.md README.md docs/superpowers/specs/2026-10-05-harvest-forecast-design.md
git commit -m "document the forecast service and record the verified feed facts"
git push origin main
```

---

## Self-review against the spec

- Goal, three levels, 36 hours, VPS: Tasks 6 and 10.
- Three-factor decomposition: `solar.py`/`node.py` (physics), `model.py` (sky ratio), `node.node_ratio` (node ratio).
- Sky model features: `features.FEATURES`; low/mid/high cloud dropped per the verified feed facts.
- Single lead for this version: training uses `previous_day1`, live uses the latest forecast run (Task 4, Task 10).
- LightGBM parameters, early stopping on the recent part, sorted outputs: `model.train`, `model.predict`.
- Training data span and the two honest limits: `HISTORY_START`, README and the spec note.
- Baselines, back-test metrics, by month and by AOD, dust ablation: Task 5, Task 7 (`lightgbm_nodust`).
- Node conversion, tilt via `clearsky_poa`, node ratio over 7 days of usable hours, store-full exclusion, default 1.0 flagged, ratio written daily: Task 8, Task 10.
- Harvest measurement option A (PPK2): Task 9. Options B and C are firmware and out of scope; the `harvest` schema accepts them unchanged (`source=uplink`).
- Components table: every module present; `metrics.py` added, `history` lives in `archive.py`.
- Data flow and timers: Tasks 3 and 10. `fetch` deployed first (Task 3) because the archive cannot be back-filled.
- InfluxDB measurements: `influx.py` writes exactly the spec's tags and fields; `harvest_forecast` keeps the latest per hour because InfluxDB overwrites on equal tags and time.
- Model switch on the last 30 days at the 10 % pinball: `cli.choose_model`.
- Error handling: feed retries then archive fallback (`get_json`, `sky_levels` stale check), missing air quality leaves dust NaN, no forecast publishes climatology, no models publishes raw forecast, InfluxDB down keeps the local forecast and exits 1 (`cmd_predict`), `selfcheck`.
- Testing list: recorded responses, solar vs NOAA, hand-made pinball/coverage/sort cases, leakage test (`test_training_table_takes_nothing_but_the_target_from_the_satellite`), dry run with soiling and cleaning and store-full hours, back-test table saved under `forecast/out/`.
- Done means: 1 (Task 7), 2 (Task 10), 3 (Task 8), 4 (`config.toml` + `harvest` records).
- Review Focus items 1 to 5 each have a named test in the owning task.
