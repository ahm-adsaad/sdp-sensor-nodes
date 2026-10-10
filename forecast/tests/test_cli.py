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
