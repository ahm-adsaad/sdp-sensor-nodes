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
