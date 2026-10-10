"""Commands the systemd timers run. Each returns a process exit code."""

from __future__ import annotations

import argparse
import json
import logging
import sys

import pandas as pd

import archive
import backtest
import baselines
import config
import features
import feeds
import metrics
import model
import node
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
    return parser


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
