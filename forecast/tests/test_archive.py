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


def test_append_leaves_no_temp_file(tmp_path):
    issued = pd.Timestamp("2026-10-10 09:02", tz="UTC")
    archive.append("forecast", frame("2026-10-10 09:00", 1.0), issued, root=tmp_path)
    archive.save_history("sat", frame("2025-06-10 00:00", 1.0), root=tmp_path)
    assert not list(tmp_path.rglob("*.tmp"))


def test_latest_reads_only_the_newest_month(tmp_path):
    archive.append("forecast", frame("2026-09-30 22:00", 1.0), pd.Timestamp("2026-09-30 22:02", tz="UTC"), root=tmp_path)
    archive.append("forecast", frame("2026-10-01 00:00", 2.0), pd.Timestamp("2026-10-01 00:02", tz="UTC"), root=tmp_path)
    (tmp_path / "forecast" / "2026-09.parquet").write_bytes(b"torn")       # an older month is unreadable
    issued, rows = archive.latest("forecast", root=tmp_path)
    assert issued == pd.Timestamp("2026-10-01 00:02", tz="UTC") and (rows["x"] == 2.0).all()
