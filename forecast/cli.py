"""Commands the systemd timers run. Each returns a process exit code."""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

import archive
import config
import feeds

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forecast")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("fetch", help="fetch the live forecast and air-quality feeds into the archive")
    p.set_defaults(func=cmd_fetch)
    p = sub.add_parser("fetch-history", help="fetch the public training history (day-ahead runs, air quality, satellite)")
    p.add_argument("--start", default=config.HISTORY_START)
    p.add_argument("--end", default=None, help="ISO date, default yesterday")
    p.set_defaults(func=cmd_fetch_history)
    return parser


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
