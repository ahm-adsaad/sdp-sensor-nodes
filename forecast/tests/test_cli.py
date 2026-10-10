import json

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


def test_dryrun_shows_soiling_and_cleaning(tmp_path, monkeypatch, site, capsys):
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli.config, "OUT", tmp_path)
    assert cli.main(["dryrun"]) == 0
    text = capsys.readouterr().out
    rows = {line.split()[0]: float(line.split()[1]) for line in text.splitlines() if line.startswith("day-")}
    assert abs(rows["day-10"] - 0.9) < 0.02
    assert abs(rows["day-17"] - 0.6) < 0.02
    assert abs(rows["day-28"] - 0.9) < 0.02
