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

Needs Python 3.11 or newer with `python3-venv`. Everything runs as one unprivileged user with sudo that owns the
checkout; the systemd units run as that user too (`adduser forecast && usermod -aG sudo forecast` if the server only
has root). The repository is private: make a read-only deploy key on the server
(`ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_ed25519`), add its `.pub` under the repository's Settings, Deploy keys,
and clone over SSH.

```bash
sudo mkdir -p /opt/sdp-sensor-nodes && sudo chown "$USER" /opt/sdp-sensor-nodes
git clone git@github.com:ahm-adsaad/sdp-sensor-nodes.git /opt/sdp-sensor-nodes
cd /opt/sdp-sensor-nodes/forecast
nano .env                                  # see the variables below; write it BEFORE install.sh, the timers start at once
bash deploy/install.sh                     # venv, pip, units, timers
set -a; . ./.env; set +a                   # hand-run commands need the same variables the units get
.venv/bin/python cli.py fetch-history      # once: public history since 2024-02, a few minutes
.venv/bin/python cli.py train              # once: without it predict publishes the raw-forecast fallback
.venv/bin/python cli.py fetch
.venv/bin/python cli.py predict
.venv/bin/python cli.py selfcheck
```

Later updates: `git -C /opt/sdp-sensor-nodes pull && bash /opt/sdp-sensor-nodes/forecast/deploy/install.sh`.
The weekly `forecast-train` timer extends the history by 14 days and retrains; it relies on the one-off
`fetch-history` above having been run. Always `set -a; . ./.env; set +a` in a shell before running `predict`,
`ratio` or `import-ppk2` by hand; without `INFLUX_URL`, `import-ppk2` only saves records locally, where nothing
in production reads them.

`forecast/.env` (not committed): `INFLUX_URL`, `INFLUX_VERSION` (`1` or `2`), and for 2.x
`INFLUX_TOKEN INFLUX_ORG INFLUX_BUCKET`, for 1.x `INFLUX_USER INFLUX_PASSWORD INFLUX_DB`.

If no models are on disk, `predict` publishes the raw-forecast baseline with fixed offsets (-0.15 / +0.05 on the sky
ratio) and the `model` tag says `raw_forecast`; after a stale spell it publishes `climatology`. Points under an
older `model` tag are not overwritten, so group Grafana queries on `harvest_forecast` by `model` or filter to the
one you want.

## Measuring harvest with a PPK2

Put the PPK2 in ampere-meter mode between the panel (VIN side) and the PMIC input (VOUT side), record in the
Power Profiler app at 1 to 10 samples per second (a day at 1 kS/s is 86 million rows and is loaded whole), export
CSV with the default Timestamp and Current columns, then:

```bash
set -a; . ./.env; set +a
.venv/bin/python cli.py import-ppk2 --node node-01 --start 2026-10-14T06:00:00Z --volts 3.0 export.csv
```

`--start` is the UTC time of the first sample; the export only has relative milliseconds. `--volts` (default 3.0)
is the panel-line voltage and scales the result directly, so measure it with a meter under sun rather than guessing.
The records are panel-side energy, before PMIC losses. Export whole hours: re-importing a file that covers only part
of an already-stored hour replaces that hour.

With a full store the PMIC stops drawing from the panel, so the current trace shows when the store was charging
and when it was full. `seconds` in each record is the time the panel was delivering current, and the node ratio is
taken on harvest power over that time, so an hour where the store filled after twenty minutes still measures the
panel correctly. Hours with under ten minutes of charging are left out.

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
The persistence row uses yesterday's satellite sky ratio, which in production arrives about 1.5 days late, so it is a comparator only and is never published.
