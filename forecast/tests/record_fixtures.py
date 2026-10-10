"""Record real Open-Meteo responses for the tests. Run once, by hand, with network.

    cd forecast && .venv/Scripts/python.exe tests/record_fixtures.py
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # forecast/ on the path when run as a script

import config  # noqa: E402
import feeds  # noqa: E402

OUT = pathlib.Path(__file__).parent / "fixtures"
site, _ = config.load_config()


def save(name, payload):
    OUT.mkdir(exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    print(name, len(payload["hourly"]["time"]), "hours")


if __name__ == "__main__":
    save("forecast", feeds.get_json(feeds.FORECAST_URL, feeds.forecast_params(site, days=2)))
    save("air_quality", feeds.get_json(feeds.AIR_URL, feeds.air_params(site, days=5)))
    save("previous_runs", feeds.get_json(feeds.PREVIOUS_RUNS_URL, feeds.previous_runs_params(site, "2025-06-10", "2025-06-11")))
    save("air_quality_history", feeds.get_json(feeds.AIR_URL, feeds.air_history_params(site, "2025-06-10", "2025-06-11")))
    save("satellite", feeds.get_json(feeds.SATELLITE_URL, feeds.satellite_params(site, "2025-06-10", "2025-06-11")))
