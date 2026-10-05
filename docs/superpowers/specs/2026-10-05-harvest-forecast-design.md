# Harvest forecasting (ML) — design

Date: 2026-10-05
Status: draft, waiting for review

## Goal

A forecasting service on the VPS that tells us, for every node and every hour
of the next 36 hours, how much energy the node's solar panel will harvest. It
gives three levels for each hour: a pessimistic one (10 %), a middle one (50 %)
and an optimistic one (90 %). The model is LightGBM.

The service is built and tested now, before any node exists, so that it only
needs configuration when the rev-2 nodes arrive. The ENS160 task allocator is
a later sub-project and reads this service's output.

Out of scope: the allocator, the node firmware, the LoRaWAN payload format,
the Node-RED flows, Grafana dashboards, and any LSTM or pretrained-model
comparison.

## Inputs and how sure we are

| Item | Value | Source | Confidence |
|---|---|---|---|
| Site | 25.29 N, 55.48 E (University City, Sharjah) | our assumption | to confirm |
| Solar panel | PowerFilm MP3-37, 150 mW and 50 mA in full sun | PowerFilm datasheet | exact |
| Panels per node, tilt | 1 to 3, flat on the lid | enclosure design | count not decided |
| Storage | Eaton HS1040 150 F, 384 J between 2.80 and 3.60 V | rev-2 decision, 2026-10-03 | nominal |
| Storage voltage to the MCU | not connected on rev-2, board already ordered | user, 2026-10-05 | exact |
| PMIC status pins to the MCU | ST_LOAD, ST_STO_RDY, ST_STO_OVDIS | 2026-10-02 schematic | read from the export |
| PPK2 | one per node; 200 nA to 1 A, 100 ksps, source or ampere-meter mode at 0.8 to 5 V, logs through a PC app | Nordic product page, 2026-10-05 | exact |
| VPS | ChirpStack, Node-RED, InfluxDB and Grafana running | user, 2026-10-05 | InfluxDB version unknown |
| Node data | none yet | user, 2026-10-05 | — |
| Deadline | this semester, about December 2026 | user, 2026-10-05 | — |

Public data feeds, each checked with a live request for the site on 2026-10-05:

| Feed | What it returned | Use |
|---|---|---|
| Open-Meteo forecast | hourly, 16 days: shortwave, direct and diffuse radiation, cloud cover, temperature, humidity, wind, rain | live inputs |
| Open-Meteo air quality | hourly dust, aerosol optical depth, PM10, PM2.5; about 4.7 days of forecast; history back to at least 2022-08-10 | live inputs and training |
| Open-Meteo previous runs | the day-ahead forecast for a past hour; present for 2025-01-10 and 2026-03-10, empty for 2024-01-10 | training inputs at a true one-day lead |
| Open-Meteo historical forecast | stitched past forecasts back to at least 2022-06-01, with low, mid and high cloud | fallback training inputs |
| Open-Meteo satellite radiation | hourly shortwave, direct and diffuse for 2025-06-01 | the "actual" sunlight for training |
| NASA POWER hourly | all-sky and clear-sky surface shortwave, source SYN1deg | cross-check of the "actual" |

Sharjah sunlight over 2025-10-01 to 2026-09-28, from the Open-Meteo archive
(reanalysis, not measurements): mean 5.82 kWh/m2 per day; 92 % of days within
20 % of a clear day; yesterday as the forecast is off by 5.7 % on average; the
29 days below 80 % fall in December (7), January (1), March (15), April (5)
and August (1).

## Decisions already made

- The model is LightGBM with the quantile objective (user, 2026-10-05).
- It runs on the VPS, not on the node.
- It predicts harvest as a ratio to the clear-sky expectation, at 10, 50 and
  90 %.
- Dust in the air and soiling on the panel are both taken into account.
- The allocator comes later and plans on the 10 % level.
- Code is written now and must be ready for the nodes without changes.

## The problem with labels, and how the design gets around it

A model needs measured harvest to learn from. We have none, and the rev-2
board cannot measure it by itself because the storage voltage does not reach
the MCU. The deadline leaves a few weeks of node data at best, and the papers
say a learned model needs 30 to 50 days (Kraemer 2020) and loses to a
no-training sun-angle model at three weeks (Bråten 2018).

So harvest is split into three factors, and only the one that can be learned
today is learned today:

```
harvest [J] = clear-sky energy  x  sky ratio  x  node ratio
              (physics)            (LightGBM)    (measured per node)
```

- **Clear-sky energy** is what the node's panels would collect in that hour
  under a cloudless, dust-free sky. It comes from sun geometry and the panel
  rating. No data needed.
- **Sky ratio** is how much of the clear-sky sunlight actually arrives: clouds
  and dust in the air. It is the same for every node at the site, so it can be
  trained on public history for Sharjah. This is the LightGBM model.
- **Node ratio** is how much of the arriving sunlight this node turns into
  stored energy: soiling on the panel, tilt, PMIC losses, heat. It changes
  slowly and is tracked per node from measurements once they exist. Until
  then it is a fixed starting value.

When 30 or more days of node harvest exist, a second LightGBM model can be
trained on node data directly (see "Node model, later").

## Sky model

Target: sky ratio k = actual sunlight / clear-sky sunlight for one hour, for
daylight hours only (sun more than 5 degrees above the horizon). At night the
forecast is zero.

One row per daylight hour. Features:

| Group | Features | Source |
|---|---|---|
| Sun | elevation, azimuth, clear-sky irradiance, hour, day of year | computed |
| Forecast sky ratio | forecast shortwave / clear-sky; forecast direct and diffuse fractions | Open-Meteo |
| Cloud | total, low, mid and high cloud cover | Open-Meteo |
| Weather | temperature, humidity, wind speed, rain | Open-Meteo |
| Dust in the air | aerosol optical depth, dust, PM10 | Open-Meteo air quality |

The previous-runs feed is confirmed to hold day-ahead shortwave radiation,
cloud cover and temperature. The build checks the other variables; any it
does not hold at a one-day lead are dropped from this version.

This version has a single lead: the model is trained on day-ahead inputs and
applied to all 36 hours. Hours ahead becomes a feature once the live archive
holds enough forecasts at each lead.

Three LightGBM models, one per level (alpha 0.1, 0.5, 0.9). After prediction
the three values are sorted so they never cross. Trees are kept shallow and
leaves large because the data set is small; the starting settings are depth 4,
at most 15 leaves, at least 50 rows per leaf, learning rate 0.05, with the
number of trees chosen by early stopping on the most recent part of the
training period. These are our starting values, tuned only on time-ordered
splits.

Training data: every daylight hour from the first date the previous-runs feed
has day-ahead values (some time in 2024; the build pins it down) to today.
That is roughly 7,000 rows. Inputs are the day-ahead forecast values; the
target is the satellite feed. Using day-ahead inputs for every lead means
short-lead skill is understated, never overstated.

Two honest limits on this training set:
- The air-quality history is the feed's best estimate for each past hour, not
  what it forecast a day earlier. Back-test results for the dust features are
  therefore optimistic. The live archive below fixes this over time.
- Which satellite the Open-Meteo satellite feed uses at this longitude, and
  how many hours behind real time it runs, are not confirmed. The build reads
  its documentation first and compares it against NASA POWER before trusting
  it.

## Baselines

The model has to beat these on the same hours:

| Name | Median | 10 % and 90 % |
|---|---|---|
| Climatology | median k for that month and hour | quantiles of k for that month and hour |
| Persistence | k of the same hour yesterday | that, shifted by its past error quantiles |
| Raw forecast | forecast shortwave / clear-sky, no learning | that, shifted by its past error quantiles |

## Back-test

Rolling in time order: train on everything before a month, test on that
month, move one month forward. The first test month starts after six months
of training data.

Reported for the model and each baseline:
- pinball loss at 10, 50 and 90 %, and the share of hours where the actual
  falls below the 10 % level (should be near 10 %);
- mean absolute error in W/m2;
- the same split by month, and by low, middle and high aerosol optical depth;
- the model with and without the dust features.

There is no accuracy pass mark. We do not know how much skill is available
at this site, and the weather figures above suggest the baselines will be
hard to beat on most days. The back-test table is the result either way.

## Node conversion

Clear-sky energy for a node in one hour:

```
E_clear [J] = panels x 0.150 W x (clear-sky irradiance on the panel / 1000 W/m2) x 3600 s
```

For a flat panel the irradiance on the panel is the horizontal clear-sky
irradiance. Tilt and direction are per-node settings. The formula assumes
panel output scales in proportion to irradiance from its full-sun rating;
that is our simplification, and the node ratio absorbs the error.

Node ratio: over the last 7 days, the median of (measured harvest / (E_clear
x actual sky ratio)) across hours that are usable. An hour is usable if the
sun is above 15 degrees, a harvest measurement exists, and the store was not
full. The PMIC stops charging when the store is full, so the measurement in
those hours says nothing about the sunlight (Kraemer 2017 reports the same
blind spot). With no usable hours the node ratio keeps its last value; before
any measurement it is 1.0, which overstates harvest and is flagged in the
output.

Forecast for a node and hour:

```
E_q = E_clear x k_q x node ratio        for q = 10, 50, 90 %
```

Soiling is carried by the node ratio. Over a 36-hour forecast the last
measured ratio is the estimate; no separate soiling forecast is made in this
version. The node ratio is written to InfluxDB each day so a falling ratio
can be seen and used as a cleaning prompt.

## Node model, later

Once a node has 30 or more days of harvest data, a second LightGBM model can
be trained on node data: target = measured harvest / E_clear; features = the
sky model's three levels, the node ratio, days since cleaning, days since
rain, PM10 accumulated since then, recent wind and humidity, the node's
harvest in the last 1 to 3 hours and in the same hour yesterday, node ID, and
SHT41 temperature. It replaces the node conversion only if it beats it in the
same back-test. The feature builder and model code are shared with the sky
model, so this is a configuration and data step, not new code. It is not
expected to be reachable before the December deadline.

## Harvest measurements

The service reads harvest as records of (node, hour, energy in joules,
source, store-full flag). Where they come from is still open, because rev-2
has no storage-voltage sensing:

| Option | How | Limits |
|---|---|---|
| A. PPK2 on the panel line | ampere-meter mode between panel and PMIC, logged to a computer, exported as CSV | needs a computer per PPK2 or a hub; needs 0.8 V or more; blind when the store is full; current only, so panel voltage must come from elsewhere |
| B. Divider bodge | two resistors from the storage screw terminal to a free analog pin, storage voltage sent in the uplink | needs a free analog pin (to check on the schematic) and firmware support |
| C. Status pins only | store-ready and over-discharge flags in the uplink | too coarse to give harvest; usable as the store-full flag |

The forecaster works with any of them and is tested with a simulator that
writes the same records. Without A or B there are no node labels: the node
ratio stays at 1.0 and the forecast is the site forecast times the panel
rating. The allocator will also need the store level, so this choice matters
beyond this spec.

## Components

A Python sub-project in `forecast/`, laid out like `enclosure/` (its own
`requirements.txt`, `pytest.ini` and `tests/`).

| Module | Does | Depends on |
|---|---|---|
| `config.py` | site, node list, feed variables, levels, paths; secrets from environment variables | — |
| `feeds.py` | fetches each feed and returns a tidy hourly table | requests |
| `solar.py` | sun position and clear-sky irradiance | pvlib |
| `archive.py` | appends every fetched forecast, with its issue time, to local Parquet files | feeds |
| `features.py` | builds the feature table from feeds and sun geometry | feeds, solar |
| `baselines.py` | the three baselines | features |
| `model.py` | trains, saves, loads and applies the three LightGBM models | lightgbm |
| `backtest.py` | rolling back-test and the report table | model, baselines |
| `node.py` | clear-sky energy per node, node ratio, node forecast | solar |
| `influx.py` | reads harvest records, writes forecasts and node ratios | InfluxDB client |
| `ppk2.py` | turns PPK2 CSV exports into harvest records | — |
| `simulate.py` | makes synthetic harvest records for tests and dry runs | solar |
| `cli.py` | commands: `fetch`, `train`, `predict`, `backtest`, `selfcheck` | all |

Training data and the forecast archive live in local Parquet files. InfluxDB
is only the source of node measurements and the place forecasts are
published, so everything except `influx.py` runs and is tested without it.

Synthetic data from `simulate.py` is for testing the code only. It is tagged
`source=sim` and is never reported as a result.

## Data flow on the VPS

```
hourly   fetch    feeds -> archive (Parquet)
hourly   predict  latest forecast + models + node ratios -> InfluxDB harvest_forecast
daily    ratio    harvest records + actual sky ratio -> InfluxDB node_ratio
weekly   train    archive + satellite actuals -> models, back-test on the last 30 days
```

Scheduled with systemd timers. `fetch` starts as soon as it is deployed,
before the model exists: the archive it builds is the only source of
forecasts at their true lead time, dust included, and it cannot be
back-filled.

InfluxDB measurements:

| Measurement | Tags | Fields | Time |
|---|---|---|---|
| `harvest` | node, source | energy_j, seconds, store_full | start of the hour |
| `harvest_forecast` | node, model | q10_j, q50_j, q90_j, lead_h, issued_at, node_ratio_default | start of the forecast hour |
| `node_ratio` | node | ratio, usable_hours | day |

`harvest_forecast` keeps the latest forecast for each hour. The full history
of issued forecasts stays in the Parquet archive for evaluation.

## Which model is published

At each weekly training run the LightGBM sky model and the raw-forecast
baseline are scored on the last 30 days. The service publishes the LightGBM
levels only if its 10 % pinball loss is no worse than the baseline's;
otherwise it publishes the baseline, and the `model` tag says which. Bråten
2018 found that switching between a physical and a learned model handles the
start of a deployment better than either alone.

## Error handling

- A feed request fails: retry three times, then use the newest archived
  forecast if it is under 12 hours old, and say so in the log.
- The air-quality feed is missing: the dust features are left empty, which
  LightGBM handles; the forecast is still published.
- No usable forecast at all: publish the climatology baseline.
- No models on disk: publish the raw-forecast baseline.
- InfluxDB is unreachable: keep the forecast in the local archive and exit
  with an error so the timer shows the failure.
- `selfcheck` prints, for each feed, model and node, the age of the newest
  data.

## Testing

- Unit tests with recorded feed responses; no network in the test run.
- `solar.py` checked against published sun positions for the site.
- Pinball loss, coverage and the quantile sort checked on hand-made cases.
- Feature builder: a test that no feature for an hour uses information from
  after its issue time.
- End-to-end dry run on simulated nodes: an injected soiling drop and a
  cleaning must show up in the node ratio, and store-full hours must be
  ignored.
- The back-test on public Sharjah data is run once the code passes and its
  table is saved under `forecast/out/`.

## Done means

1. `backtest` produces the comparison table on at least 12 months of public
   Sharjah data, with the dust ablation.
2. On the VPS, `fetch` and `predict` run hourly and write 36 hours of levels
   for every configured node.
3. The simulated-node dry run passes.
4. Adding a real node is a configuration change plus harvest records in the
   agreed schema.

## Build order

1. Feed archiver, deployed to the VPS first because the archive cannot be
   back-filled.
2. Training set from public history, baselines, sky model, back-test.
3. Node conversion, simulator, publishing to InfluxDB, model switch.
4. When nodes exist: harvest ingest, node ratio on real data, node back-test.

## What supports each choice

| Choice | Evidence |
|---|---|
| Server-side forecast from public weather forecasts for LoRaWAN nodes | Kraemer 2017 (10.1145/3131542.3131544), Kraemer 2020 (10.1109/JIOT.2020.3002330) |
| Tree ensembles; gradient boosting among the leading models | Hong 2016 (10.1016/j.ijforecast.2016.02.001), Mohammed and Aung 2016 (10.3390/en9121017), Visser 2022 (10.1016/j.renene.2021.10.102) |
| Quantile output from weather and aerosol forecasts | Bakker 2019 (10.1016/j.solener.2019.08.044) |
| A physical model beside the learned one, with switching | Bråten and Kraemer 2018 (10.1109/ICIOT.2018.00023) |
| 30 to 50 days before a node-level model | Kraemer 2020 |
| Dust inputs kept only if they help | Alfadda 2018 (10.1016/j.solener.2018.05.089) |
| Soiling as a slow measured ratio | Javed 2017 (10.1016/j.solener.2017.08.046), Hachicha 2019 (literature sheet #29) |
| Store-full hours excluded | Kraemer 2017 |

The same papers put gradient boosting within a few percent of random forest,
linear quantile regression and others, not ahead of them. LightGBM is the
chosen model; the back-test against the baselines is what shows whether it
earns its place here.

## Risks

- The gain over the raw forecast may be small or zero at this site.
- Few or no node measurements before December, so node-level results may be
  simulator-only by the deadline.
- No harvest sensing on rev-2 until option A or B is in place.
- The satellite feed may turn out to be unsuitable; NASA POWER is coarser
  (about 1 degree) and months behind.

## Open items and the default used if unanswered

| Item | Default |
|---|---|
| Site coordinates | 25.29 N, 55.48 E |
| Panels per node, tilt, direction | 1 panel, flat |
| InfluxDB version and credentials | `influx.py` written last, after this is known |
| Python version on the VPS | 3.11 or newer in a virtual environment |
| Harvest measurement option | none chosen; service tested on the simulator |
| Cleaning log | none; node ratio alone |
