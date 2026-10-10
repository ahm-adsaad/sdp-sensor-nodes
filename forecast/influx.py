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
        missing = {"energy_j", "seconds"} - set(raw.columns)
        if missing:
            raise InfluxError(f"query result lacks {sorted(missing)}")
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
        payload = json.loads(r.text)
        results = payload.get("results") or [{}]
        if results[0].get("error"):
            raise InfluxError(f"query error: {results[0]['error']}")
        found = results[0].get("series", [])
        if not found:
            return _empty_records()
        series = found[0]
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
