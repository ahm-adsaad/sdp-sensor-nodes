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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forecast")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("fetch", help="fetch the live forecast and air-quality feeds into the archive")
    p.set_defaults(func=cmd_fetch)
    return parser


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
