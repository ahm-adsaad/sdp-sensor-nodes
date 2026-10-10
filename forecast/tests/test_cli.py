import json
import pathlib

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


def test_import_ppk2_saves_records(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    monkeypatch.delenv("INFLUX_URL", raising=False)   # local import only; no InfluxDB in tests
    sample = pathlib.Path(__file__).parent / "fixtures" / "ppk2_sample.csv"
    assert cli.main(["import-ppk2", "--node", "node-01", "--start", "2026-10-14T06:00:00Z", "--volts", "3.0", str(sample)]) == 0
    recs = cli.archive.load_records("node-01", root=tmp_path / "harvest")
    assert len(recs) == 2 and (recs["source"] == "ppk2").all()


class FakeInflux:
    def __init__(self):
        self.lines = []

    def post(self, url, params=None, data=None, headers=None, auth=None, json=None, timeout=None):
        if data:
            self.lines += data.splitlines()
        return type("R", (), {"ok": True, "status_code": 204, "text": ""})()


def seed_archive(root, fixture_json, issued):
    import archive
    import feeds

    archive.append("forecast", feeds.fetch_forecast(cli.load_site(), get=lambda u, p: fixture_json("forecast")), issued, root=root)
    archive.append("air_quality", feeds.fetch_air_quality(cli.load_site(), get=lambda u, p: fixture_json("air_quality")), issued, root=root)


def first_hour(fixture_json):
    return pd.Timestamp(fixture_json("forecast")["hourly"]["time"][0], tz="UTC") - pd.Timedelta(hours=1)


def test_predict_writes_36_hours_per_node(tmp_path, monkeypatch, site, fixture_json, trained_models):
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli, "load_nodes", lambda: [cli.config.Node("node-01", 1, 0, 180), cli.config.Node("node-02", 2, 0, 180)])
    monkeypatch.setattr(cli.config, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    monkeypatch.setattr(cli.config, "FORECASTS", tmp_path / "forecasts")
    issued = first_hour(fixture_json) + pd.Timedelta(hours=6)
    seed_archive(tmp_path / "archive", fixture_json, issued)
    monkeypatch.setattr(cli, "now_utc", lambda: issued + pd.Timedelta(minutes=10))
    fake = FakeInflux()
    monkeypatch.setattr(cli, "influx_session", lambda: fake)
    monkeypatch.setenv("INFLUX_URL", "http://db:8086")
    assert cli.main(["predict"]) == 0
    assert len(fake.lines) == 72 and all(l.startswith("harvest_forecast,model=lightgbm,node=node-0") for l in fake.lines)
    assert all("node_ratio_default=true" in l for l in fake.lines)
    saved = list((tmp_path / "forecasts").glob("*.parquet"))
    assert len(saved) == 1 and len(pd.read_parquet(saved[0])) == 72


def test_predict_refuses_stale_forecast(tmp_path, monkeypatch, site, fixture_json, trained_models):
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli.config, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    monkeypatch.setattr(cli.config, "FORECASTS", tmp_path / "forecasts")
    issued = first_hour(fixture_json)
    seed_archive(tmp_path / "archive", fixture_json, issued)
    monkeypatch.setattr(cli, "now_utc", lambda: issued + pd.Timedelta(hours=13))
    fake = FakeInflux()
    monkeypatch.setattr(cli, "influx_session", lambda: fake)
    assert cli.main(["predict"]) == 0
    assert all(",model=climatology," in l for l in fake.lines) and len(fake.lines) == 36 * 5


def test_predict_uses_raw_forecast_when_no_models(tmp_path, monkeypatch, site, fixture_json):
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli.config, "MODELS", tmp_path / "nomodels")
    monkeypatch.setattr(cli.config, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    monkeypatch.setattr(cli.config, "FORECASTS", tmp_path / "forecasts")
    issued = first_hour(fixture_json) + pd.Timedelta(hours=6)
    seed_archive(tmp_path / "archive", fixture_json, issued)
    monkeypatch.setattr(cli, "now_utc", lambda: issued)
    fake = FakeInflux()
    monkeypatch.setattr(cli, "influx_session", lambda: fake)
    assert cli.main(["predict"]) == 0
    assert all(",model=raw_forecast," in l for l in fake.lines)


def test_predict_keeps_archive_and_fails_when_influx_down(tmp_path, monkeypatch, site, fixture_json, trained_models):
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli.config, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    monkeypatch.setattr(cli.config, "FORECASTS", tmp_path / "forecasts")
    issued = first_hour(fixture_json) + pd.Timedelta(hours=6)
    seed_archive(tmp_path / "archive", fixture_json, issued)
    monkeypatch.setattr(cli, "now_utc", lambda: issued)

    class Down:
        def post(self, *a, **kw):
            raise cli.requests.ConnectionError("down")

    monkeypatch.setattr(cli, "influx_session", lambda: Down())
    assert cli.main(["predict"]) == 1
    assert len(list((tmp_path / "forecasts").glob("*.parquet"))) == 1


def test_ratio_reads_harvest_and_writes_state(tmp_path, monkeypatch, site, fixture_json):
    import simulate
    import solar

    nd = cli.config.Node("node-01", 1, 0, 180)
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli, "load_nodes", lambda: [nd])
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    hs = pd.date_range("2025-06-03", periods=8 * 24, freq="h", tz="UTC")
    sat = pd.DataFrame({"hour_start": hs, "sat_ghi": solar.clearsky(site, hs)["cs_ghi"].to_numpy() * 0.95, "sat_direct": 0.0, "sat_diffuse": 0.0})
    monkeypatch.setattr(cli.feeds, "fetch_satellite", lambda site, s, e, **kw: sat)
    recs = simulate.harvest_records(site, nd, hs, pd.Series(0.95, index=hs), 0.7)
    monkeypatch.setattr(cli.influx, "read_harvest", lambda node_id, since, settings, session=None: recs)
    fake = FakeInflux()
    monkeypatch.setattr(cli, "influx_session", lambda: fake)
    monkeypatch.setattr(cli, "now_utc", lambda: hs[-1] + pd.Timedelta(days=2))
    assert cli.main(["ratio"]) == 0
    state = json.loads((tmp_path / "node_ratio.json").read_text())
    assert abs(state["node-01"]["ratio"] - 0.7) < 0.01 and not state["node-01"]["is_default"]
    assert fake.lines and fake.lines[0].startswith("node_ratio,node=node-01 ratio=0.")


def test_selfcheck_prints_ages(tmp_path, monkeypatch, site, fixture_json, trained_models, capsys):
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli.config, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    seed_archive(tmp_path / "archive", fixture_json, first_hour(fixture_json))
    assert cli.main(["selfcheck"]) == 0
    out = capsys.readouterr().out
    assert "forecast" in out and "air_quality" in out and "sky model" in out and "node-01" in out


def test_ratio_keeps_measured_flag_when_a_day_has_no_usable_hours(tmp_path, monkeypatch, site):
    import solar

    nd = cli.config.Node("node-01", 1, 0, 180)
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli, "load_nodes", lambda: [nd])
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    cli.save_ratio_state({"node-01": {"ratio": 0.7, "usable_hours": 40, "is_default": False, "updated": "x"}})
    hs = pd.date_range("2025-06-03", periods=8 * 24, freq="h", tz="UTC")
    sat = pd.DataFrame({"hour_start": hs, "sat_ghi": solar.clearsky(site, hs)["cs_ghi"].to_numpy() * 0.95, "sat_direct": 0.0, "sat_diffuse": 0.0})
    monkeypatch.setattr(cli.feeds, "fetch_satellite", lambda site, s, e, **kw: sat)
    monkeypatch.setattr(cli.influx, "read_harvest", lambda node_id, since, settings, session=None: cli.archive.load_records("none", root=tmp_path))
    fake = FakeInflux()
    monkeypatch.setattr(cli, "influx_session", lambda: fake)
    monkeypatch.setattr(cli, "now_utc", lambda: hs[-1] + pd.Timedelta(days=2))
    assert cli.main(["ratio"]) == 0
    state = json.loads((tmp_path / "node_ratio.json").read_text())
    assert state["node-01"]["ratio"] == 0.7 and not state["node-01"]["is_default"]


def test_ratio_continues_past_a_failing_node_and_saves_the_rest(tmp_path, monkeypatch, site):
    import simulate
    import solar

    nodes = [cli.config.Node("node-01", 1, 0, 180), cli.config.Node("node-02", 1, 0, 180)]
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli, "load_nodes", lambda: nodes)
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    hs = pd.date_range("2025-06-03", periods=8 * 24, freq="h", tz="UTC")
    sat = pd.DataFrame({"hour_start": hs, "sat_ghi": solar.clearsky(site, hs)["cs_ghi"].to_numpy() * 0.95, "sat_direct": 0.0, "sat_diffuse": 0.0})
    monkeypatch.setattr(cli.feeds, "fetch_satellite", lambda site, s, e, **kw: sat)
    recs = simulate.harvest_records(site, nodes[1], hs, pd.Series(0.95, index=hs), 0.7)

    def read(node_id, since, settings, session=None):
        if node_id == "node-01":
            raise cli.influx.InfluxError("boom")
        return recs

    monkeypatch.setattr(cli.influx, "read_harvest", read)
    fake = FakeInflux()
    monkeypatch.setattr(cli, "influx_session", lambda: fake)
    monkeypatch.setattr(cli, "now_utc", lambda: hs[-1] + pd.Timedelta(days=2))
    assert cli.main(["ratio"]) == 1
    state = json.loads((tmp_path / "node_ratio.json").read_text())
    assert "node-01" not in state and abs(state["node-02"]["ratio"] - 0.7) < 0.01
    assert len(fake.lines) == 1 and fake.lines[0].startswith("node_ratio,node=node-02 ")


def test_ratio_survives_an_unexpected_error_from_one_node(tmp_path, monkeypatch, site):
    import simulate
    import solar

    nodes = [cli.config.Node("node-01", 1, 0, 180), cli.config.Node("node-02", 1, 0, 180)]
    monkeypatch.setattr(cli, "load_site", lambda: site)
    monkeypatch.setattr(cli, "load_nodes", lambda: nodes)
    monkeypatch.setattr(cli.config, "DATA", tmp_path)
    hs = pd.date_range("2025-06-03", periods=8 * 24, freq="h", tz="UTC")
    sat = pd.DataFrame({"hour_start": hs, "sat_ghi": solar.clearsky(site, hs)["cs_ghi"].to_numpy() * 0.95, "sat_direct": 0.0, "sat_diffuse": 0.0})
    monkeypatch.setattr(cli.feeds, "fetch_satellite", lambda site, s, e, **kw: sat)
    recs = simulate.harvest_records(site, nodes[1], hs, pd.Series(0.95, index=hs), 0.7)

    def read(node_id, since, settings, session=None):
        if node_id == "node-01":
            raise KeyError("energy_j")
        return recs

    monkeypatch.setattr(cli.influx, "read_harvest", read)
    fake = FakeInflux()
    monkeypatch.setattr(cli, "influx_session", lambda: fake)
    monkeypatch.setattr(cli, "now_utc", lambda: hs[-1] + pd.Timedelta(days=2))
    assert cli.main(["ratio"]) == 1
    state = json.loads((tmp_path / "node_ratio.json").read_text())
    assert "node-01" not in state and abs(state["node-02"]["ratio"] - 0.7) < 0.01
    assert len(fake.lines) == 1 and fake.lines[0].startswith("node_ratio,node=node-02 ")
