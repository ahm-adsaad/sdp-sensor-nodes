"""Commands the systemd timers run. Each returns a process exit code."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

import pandas as pd
import requests

import archive
import backtest
import baselines
import config
import features
import feeds
import influx
import metrics
import model
import node
import ppk2
import simulate
import solar

log = logging.getLogger("forecast")


def now_utc() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").floor("min")


def load_site():
    return config.load_config()[0]


def load_nodes():
    return config.load_config()[1]


def cmd_fetch(args) -> int:
    site, issued = load_site(), now_utc()
    for feed, fetch in (("forecast", feeds.fetch_forecast), ("air_quality", feeds.fetch_air_quality)):
        try:
            frame = fetch(site)
        except feeds.FeedError as exc:
            log.error("%s: %s", feed, exc)
            return 1
        path = archive.append(feed, frame, issued, root=config.ARCHIVE)
        log.info("%s: %d hours -> %s", feed, len(frame), path)
    return 0


def cmd_fetch_history(args) -> int:
    site = load_site()
    end = args.end or (now_utc() - pd.Timedelta(days=1)).date().isoformat()
    jobs = (
        ("previous_runs", lambda s, e: feeds.fetch_previous_runs(site, s, e)),
        ("air_quality_history", lambda s, e: feeds.fetch_air_quality_history(site, s, e)),
        ("satellite", lambda s, e: feeds.fetch_satellite(site, s, e)),
    )
    for name, one in jobs:
        try:
            frame = feeds.fetch_range(one, args.start, end)
        except feeds.FeedError as exc:
            log.error("%s: %s", name, exc)
            return 1
        frame = frame.dropna(subset=frame.columns[1:], how="all")
        path = archive.save_history(name, frame, root=config.HISTORY)
        log.info("%s: %d hours, first %s -> %s", name, len(frame), frame["hour_start"].min(), path)
    return 0


def load_training_table(site) -> pd.DataFrame:
    return features.build_training_table(
        site,
        archive.load_history("previous_runs", root=config.HISTORY),
        archive.load_history("air_quality_history", root=config.HISTORY),
        archive.load_history("satellite", root=config.HISTORY),
    )


def choose_model(table: pd.DataFrame, days: int = 30) -> dict:
    """Score LightGBM against the raw-forecast baseline on the last `days`; publish LightGBM only if no worse at 10 %."""
    cut = table["hour_start"].max() - pd.Timedelta(days=days)
    train_rows, test_rows = table[table["hour_start"] < cut], table[table["hour_start"] >= cut]
    if len(test_rows) < 24 or len(train_rows) < 500:
        return {"model": "raw_forecast", "reason": "too little data to score", "pinball10": {}}
    sky = model.train(train_rows)
    lgb_p = model.predict(sky, test_rows)
    raw_p = baselines.raw_forecast(train_rows, test_rows)
    scores = {
        "lightgbm": metrics.pinball(test_rows["k"], lgb_p["q10"], 0.1),
        "raw_forecast": metrics.pinball(test_rows["k"], raw_p["q10"], 0.1),
    }
    chosen = "lightgbm" if scores["lightgbm"] <= scores["raw_forecast"] else "raw_forecast"
    return {"model": chosen, "pinball10": scores, "scored_hours": int(len(test_rows)), "scored_from": str(cut)}


def cmd_train(args) -> int:
    site = load_site()
    table = load_training_table(site)
    if len(table) < 500:
        log.error("only %d training rows; run fetch-history first", len(table))
        return 1
    config.MODELS.mkdir(parents=True, exist_ok=True)
    sky = model.train(table)
    model.save(sky, config.MODELS / "sky")
    table[["month", "hour", "k"]].to_parquet(config.MODELS / "climatology.parquet", index=False)
    (config.MODELS / "raw_forecast.json").write_text(json.dumps(baselines.residual_offsets(table)), encoding="utf-8")
    choice = {**choose_model(table), "trained_rows": len(table), "last_hour": sky.last_hour, "trained_at": str(now_utc())}
    (config.MODELS / "choice.json").write_text(json.dumps(choice, indent=2), encoding="utf-8")
    log.info("trained on %d rows to %s; publishing %s (%s)", len(table), sky.last_hour, choice["model"], choice.get("pinball10"))
    return 0


def cmd_backtest(args) -> int:
    table = load_training_table(load_site())
    if backtest.year_month(table["hour_start"]).nunique() < 8:
        log.error("need at least 8 months of history for a back-test")
        return 1
    preds = backtest.run(table)
    path = backtest.write_report(preds, config.OUT)
    log.info("wrote %s", path)
    print(backtest.summarize(preds).to_string(index=False))
    return 0


def cmd_dryrun(args) -> int:
    """28 simulated days: soiling from day 11, cleaning on day 18, the store full 10:00-13:00 UTC daily."""
    site = load_site()
    nd = config.Node("sim-01", 1, 0.0, 180.0)
    hs = pd.date_range("2025-06-01", periods=28 * 24, freq="h", tz="UTC")
    k = pd.Series(0.95, index=hs)
    day = pd.Series(((hs - hs[0]).days + 1), index=hs)
    ratio = pd.Series(0.9, index=hs).where(~day.between(11, 17), 0.6)
    full = pd.Series(hs.hour.isin([10, 11, 12]), index=hs)
    recs = simulate.harvest_records(site, nd, hs, k, ratio, store_full=full)
    expected = node.expected_energy_j(site, nd, k)
    elev = solar.sun_position(site, hs)["elevation"]
    previous = 1.0
    for d in range(7, 29):
        upto = recs[day.reindex(recs["hour_start"]).to_numpy() <= d]
        out = node.node_ratio(upto, expected, elev, previous=previous)
        previous = out.ratio
        print(f"day-{d:02d} {out.ratio:.3f} usable={out.usable_hours} default={out.is_default}")
    return 0


def cmd_import_ppk2(args) -> int:
    samples = ppk2.read_csv(args.path)
    records = ppk2.hourly_energy(samples, args.start, args.volts, args.node)
    path = archive.save_records(args.node, records, root=config.DATA / "harvest")
    log.info("%s: %d hours from %s -> %s", args.node, len(records), records["hour_start"].min(), path)
    if os.environ.get("INFLUX_URL"):
        try:
            influx.write_harvest(records, influx.from_env(), influx_session())
        except (influx.InfluxError, requests.RequestException) as exc:
            log.error("InfluxDB write failed, records kept locally: %s", exc)
            return 1
        log.info("wrote %d harvest rows to InfluxDB", len(records))
    return 0


STALE_FORECAST = pd.Timedelta(hours=12)


def influx_session():
    return requests.Session()


def load_ratio_state() -> dict:
    path = config.DATA / "node_ratio.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_ratio_state(state: dict) -> None:
    config.DATA.mkdir(parents=True, exist_ok=True)
    (config.DATA / "node_ratio.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def sky_levels(site, issued_at: pd.Timestamp):
    """Sky-ratio levels for the next HORIZON_H hours and the name of the method that produced them."""
    hours = pd.date_range(issued_at.floor("h"), periods=config.HORIZON_H, freq="h", tz="UTC")
    latest = archive.latest("forecast", root=config.ARCHIVE)
    air = archive.latest("air_quality", root=config.ARCHIVE)
    choice_path = config.MODELS / "choice.json"
    choice = json.loads(choice_path.read_text(encoding="utf-8"))["model"] if choice_path.exists() else "raw_forecast"
    if latest is None or issued_at - latest[0] > STALE_FORECAST:
        log.warning("no fresh forecast in the archive; publishing climatology")
        clim_path = config.MODELS / "climatology.parquet"
        if not clim_path.exists():
            raise RuntimeError("no forecast and no climatology; run fetch and train")
        clim = pd.read_parquet(clim_path)
        sun = solar.sun_position(site, hours)
        test = pd.DataFrame({"hour_start": hours, "month": hours.month, "hour": hours.hour, "k_fc": 0.0}, index=hours)
        test = test[sun["elevation"] > config.MIN_ELEVATION_DEG]
        return "climatology", baselines.climatology(clim, test)
    weather = latest[1]
    air_frame = air[1] if air is not None and issued_at - air[0] <= STALE_FORECAST else None
    if air_frame is None:
        log.warning("no fresh air-quality feed; dust features left empty")
    f = features.build_features(site, weather, air_frame)
    f = f[f["hour_start"].isin(hours)].set_index("hour_start", drop=False)
    sky_path = config.MODELS / "sky" / "meta.json"
    if choice == "lightgbm" and sky_path.exists():
        return "lightgbm", model.predict(model.load(config.MODELS / "sky"), f)
    offs_path = config.MODELS / "raw_forecast.json"
    offs = json.loads(offs_path.read_text(encoding="utf-8")) if offs_path.exists() else {"q10": -0.15, "q90": 0.05}
    mid = f["k_fc"].to_numpy(dtype=float)
    raw = pd.DataFrame({"q10": mid + offs["q10"], "q50": mid, "q90": mid + offs["q90"]}, index=f.index)
    return "raw_forecast", metrics.sort_quantiles(raw.clip(lower=0.0, upper=config.K_MAX))


def predict_frames(site, nodes, issued_at: pd.Timestamp):
    hours = pd.date_range(issued_at.floor("h"), periods=config.HORIZON_H, freq="h", tz="UTC")
    method, k_q = sky_levels(site, issued_at)
    state = load_ratio_state()
    frames = {}
    for nd in nodes:
        ratio = float(state.get(nd.id, {}).get("ratio", 1.0))
        frames[nd.id] = node.node_forecast(site, nd, hours, k_q, ratio)
    return method, frames


def cmd_predict(args) -> int:
    site, nodes, issued = load_site(), load_nodes(), now_utc()
    try:
        method, frames = predict_frames(site, nodes, issued)
    except RuntimeError as exc:
        log.error("%s", exc)
        return 1
    state = load_ratio_state()
    config.FORECASTS.mkdir(parents=True, exist_ok=True)
    all_rows = pd.concat([f.assign(node=n, model=method, issued_at=issued) for n, f in frames.items()], ignore_index=True)
    all_rows.to_parquet(config.FORECASTS / f"{issued:%Y%m%dT%H%M}.parquet", index=False)
    settings = influx.from_env()
    try:
        session = influx_session()
        for n, f in frames.items():
            is_default = bool(state.get(n, {}).get("is_default", True))
            influx.write_forecast(f, n, method, issued, is_default, settings, session)
    except (influx.InfluxError, requests.RequestException) as exc:
        log.error("InfluxDB write failed, forecast kept in %s: %s", config.FORECASTS, exc)
        return 1
    log.info("published %s levels for %d nodes issued %s", method, len(frames), issued)
    return 0


def cmd_ratio(args) -> int:
    site, nodes, now = load_site(), load_nodes(), now_utc()
    since = now - pd.Timedelta(days=9)
    try:
        sat = feeds.fetch_satellite(site, since.date().isoformat(), now.date().isoformat())
    except feeds.FeedError as exc:
        log.error("satellite feed: %s", exc)
        return 1
    sat = sat.dropna(subset=["sat_ghi"])
    hs = config.utc_ns(sat["hour_start"])
    cs = solar.clearsky(site, hs)
    k_actual = features.sky_ratio(pd.Series(sat["sat_ghi"].to_numpy(), index=hs), cs["cs_ghi"]).fillna(0.0)
    elev = solar.sun_position(site, hs)["elevation"]
    settings, session, state = influx.from_env(), influx_session(), load_ratio_state()
    for nd in nodes:
        try:
            records = influx.read_harvest(nd.id, since, settings, session)
        except (influx.InfluxError, requests.RequestException) as exc:
            log.error("%s: read failed: %s", nd.id, exc)
            return 1
        previous = float(state.get(nd.id, {}).get("ratio", 1.0))
        out = node.node_ratio(records, node.expected_energy_j(site, nd, k_actual), elev, previous=previous)
        state[nd.id] = {"ratio": out.ratio, "usable_hours": out.usable_hours, "is_default": out.is_default, "updated": str(now)}
        log.info("%s: ratio %.3f from %d usable hours%s", nd.id, out.ratio, out.usable_hours, " (default kept)" if out.is_default else "")
        try:
            influx.write_node_ratio(nd.id, now, out.ratio, out.usable_hours, settings, session)
        except (influx.InfluxError, requests.RequestException) as exc:
            log.error("%s: write failed: %s", nd.id, exc)
            return 1
    save_ratio_state(state)
    return 0


def cmd_selfcheck(args) -> int:
    now = now_utc()
    for feed in ("forecast", "air_quality"):
        latest = archive.latest(feed, root=config.ARCHIVE)
        print(f"{feed:14s} {'none' if latest is None else f'issued {latest[0]}  age {now - latest[0]}'}")
    meta = config.MODELS / "sky" / "meta.json"
    if meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        choice = json.loads((config.MODELS / "choice.json").read_text(encoding="utf-8")) if (config.MODELS / "choice.json").exists() else {}
        print(f"sky model      rows {m['trained_rows']} to {m['last_hour']}; publishing {choice.get('model', '?')}")
    else:
        print("sky model      none")
    state = load_ratio_state()
    for nd in load_nodes():
        s = state.get(nd.id)
        print(f"{nd.id:14s} {'ratio default 1.0' if not s else f'ratio {s['ratio']:.3f} usable {s['usable_hours']} updated {s['updated']}'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forecast")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("fetch", help="fetch the live forecast and air-quality feeds into the archive")
    p.set_defaults(func=cmd_fetch)
    p = sub.add_parser("fetch-history", help="fetch the public training history (day-ahead runs, air quality, satellite)")
    p.add_argument("--start", default=config.HISTORY_START)
    p.add_argument("--end", default=None, help="ISO date, default yesterday")
    p.set_defaults(func=cmd_fetch_history)
    p = sub.add_parser("train", help="train the sky model on the history and pick the model to publish")
    p.set_defaults(func=cmd_train)
    p = sub.add_parser("backtest", help="rolling monthly back-test on the public history; writes out/backtest.md")
    p.set_defaults(func=cmd_backtest)
    p = sub.add_parser("dryrun", help="simulated node: the node ratio must follow an injected soiling drop and a cleaning")
    p.set_defaults(func=cmd_dryrun)
    p = sub.add_parser("import-ppk2", help="turn a PPK2 CSV export (panel line, ampere-meter mode) into hourly harvest records")
    p.add_argument("path")
    p.add_argument("--node", required=True)
    p.add_argument("--start", required=True, help="UTC time of the first sample, e.g. 2026-10-14T06:00:00Z")
    p.add_argument("--volts", type=float, default=3.0, help="assumed panel-line voltage")
    p.set_defaults(func=cmd_import_ppk2)
    p = sub.add_parser("predict", help="publish 36 hours of q10/q50/q90 joules per node to InfluxDB")
    p.set_defaults(func=cmd_predict)
    p = sub.add_parser("ratio", help="update each node's ratio from the last week of harvest records")
    p.set_defaults(func=cmd_ratio)
    p = sub.add_parser("selfcheck", help="print the age of every feed, model and node ratio")
    p.set_defaults(func=cmd_selfcheck)
    return parser


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
