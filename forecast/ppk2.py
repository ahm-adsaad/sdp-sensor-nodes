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
