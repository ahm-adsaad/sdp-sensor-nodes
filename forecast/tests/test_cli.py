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
