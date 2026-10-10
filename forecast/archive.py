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
