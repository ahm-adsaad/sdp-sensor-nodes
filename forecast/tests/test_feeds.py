import pandas as pd
import pytest

import feeds


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code, self.ok = payload, status, status < 400

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.responses.pop(0)


def test_get_json_returns_payload(fixture_json):
    s = FakeSession([FakeResponse(fixture_json("forecast"))])
    out = feeds.get_json(feeds.FORECAST_URL, {"a": 1}, session=s)
    assert "hourly" in out
    assert s.calls[0][1] == {"a": 1}


def test_get_json_retries_on_error_payload(fixture_json):
    s = FakeSession([FakeResponse({"error": True, "reason": "The service is overloaded"}), FakeResponse(fixture_json("forecast"))])
    out = feeds.get_json(feeds.FORECAST_URL, {}, session=s, pause_s=0)
    assert "hourly" in out and len(s.calls) == 2


def test_get_json_raises_after_retries():
    s = FakeSession([FakeResponse({"error": True, "reason": "x"})] * 3)
    with pytest.raises(feeds.FeedError, match="x"):
        feeds.get_json(feeds.FORECAST_URL, {}, session=s, retries=3, pause_s=0)


def test_hourly_frame_shifts_labels_to_hour_start(fixture_json):
    f = feeds.hourly_frame(fixture_json("forecast"))
    assert f.columns[0] == "hour_start"
    assert str(f["hour_start"].dtype) == "datetime64[ns, UTC]"
    first_label = pd.Timestamp(fixture_json("forecast")["hourly"]["time"][0], tz="UTC")
    assert f["hour_start"].iloc[0] == first_label - pd.Timedelta(hours=1)
    assert set(feeds.WEATHER_VARS) <= set(f.columns)


def test_fetch_forecast_requests_the_right_variables(site, fixture_json):
    calls = []

    def get(url, params):
        calls.append((url, params))
        return fixture_json("forecast")

    f = feeds.fetch_forecast(site, days=3, get=get)
    url, params = calls[0]
    assert url == feeds.FORECAST_URL
    assert params["latitude"] == site.lat and params["timezone"] == "UTC" and params["forecast_days"] == 3
    assert params["hourly"] == ",".join(feeds.WEATHER_VARS)
    assert list(f.columns) == ["hour_start"] + feeds.WEATHER_VARS


def test_fetch_air_quality(site, fixture_json):
    f = feeds.fetch_air_quality(site, get=lambda url, params: fixture_json("air_quality"))
    assert list(f.columns) == ["hour_start"] + feeds.AIR_VARS
    assert f["aerosol_optical_depth"].notna().sum() > 0


def test_fetch_previous_runs_renames_to_plain_names(site, fixture_json):
    calls = []

    def get(url, params):
        calls.append(params)
        return fixture_json("previous_runs")

    f = feeds.fetch_previous_runs(site, "2025-06-10", "2025-06-11", get=get)
    assert calls[0]["hourly"] == ",".join(v + "_previous_day1" for v in feeds.WEATHER_VARS)
    assert calls[0]["start_date"] == "2025-06-10"
    assert list(f.columns) == ["hour_start"] + feeds.WEATHER_VARS
    assert f["shortwave_radiation"].max() > 800


def test_fetch_satellite_uses_sarah3_and_renames(site, fixture_json):
    calls = []

    def get(url, params):
        calls.append((url, params))
        return fixture_json("satellite")

    f = feeds.fetch_satellite(site, "2025-06-10", "2025-06-11", get=get)
    assert calls[0][0] == feeds.SATELLITE_URL
    assert calls[0][1]["models"] == "eumetsat_sarah3"
    assert list(f.columns) == ["hour_start", "sat_ghi", "sat_direct", "sat_diffuse"]
    assert 950 < f["sat_ghi"].max() < 1100


def test_fetch_air_quality_history_asks_for_dates(site, fixture_json):
    calls = []

    def get(url, params):
        calls.append(params)
        return fixture_json("air_quality_history")

    f = feeds.fetch_air_quality_history(site, "2025-06-10", "2025-06-11", get=get)
    assert calls[0]["start_date"] == "2025-06-10" and calls[0]["end_date"] == "2025-06-11"
    assert list(f.columns) == ["hour_start"] + feeds.AIR_VARS


def test_fetch_range_chunks_and_concatenates():
    seen = []

    def one(start, end):
        seen.append((start, end))
        return pd.DataFrame({"hour_start": [pd.Timestamp(start, tz="UTC")], "x": [1.0]})

    out = feeds.fetch_range(one, "2024-01-01", "2024-04-15", step_days=50)
    assert seen == [("2024-01-01", "2024-02-19"), ("2024-02-20", "2024-04-09"), ("2024-04-10", "2024-04-15")]
    assert len(out) == 3
