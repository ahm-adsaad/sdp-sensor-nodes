import numpy as np
import pandas as pd

import config
import feeds
import features


def weather_frame(fixture_json, name="previous_runs"):
    rename = {v + "_previous_day1": v for v in feeds.WEATHER_VARS} if name == "previous_runs" else None
    return feeds.hourly_frame(fixture_json(name), rename)[["hour_start"] + feeds.WEATHER_VARS]


def test_features_are_daylight_only_and_named(site, fixture_json):
    f = features.build_features(site, weather_frame(fixture_json), feeds.hourly_frame(fixture_json("air_quality_history")))
    assert list(f.columns) == ["hour_start", "month"] + features.FEATURES
    assert (f["elevation"] > config.MIN_ELEVATION_DEG).all()
    assert 20 <= len(f) <= 30                      # two June days of daylight
    assert f["hour_start"].is_monotonic_increasing
    assert set(f["doy"]) == {161, 162}


def test_forecast_sky_ratio_is_near_one_on_a_clear_day(site, fixture_json):
    f = features.build_features(site, weather_frame(fixture_json))
    noon = f[f["hour"] == 8]
    assert ((noon["k_fc"] > 0.8) & (noon["k_fc"] < 1.1)).all()
    assert ((f["direct_frac"] + f["diffuse_frac"]) - 1.0).abs().max() < 0.05


def test_features_keep_nan_dust(site, fixture_json):
    f = features.build_features(site, weather_frame(fixture_json))
    assert f[features.DUST_FEATURES].isna().all().all()
    assert len(f) > 0


def test_sky_ratio_is_clipped_and_nan_at_zero_clearsky():
    k = features.sky_ratio(pd.Series([500.0, 2000.0, 10.0]), pd.Series([1000.0, 1000.0, 0.0]))
    assert list(k.round(3)[:2]) == [0.5, config.K_MAX]
    assert np.isnan(k.iloc[2])


def test_training_table_has_target_and_drops_null_rows(site, fixture_json):
    w = weather_frame(fixture_json)
    w.loc[w.index[10:14], "shortwave_radiation"] = np.nan        # a gap in the day-ahead feed
    sat = feeds.hourly_frame(fixture_json("satellite"), feeds.SAT_RENAME)
    t = features.build_training_table(site, w, feeds.hourly_frame(fixture_json("air_quality_history")), sat)
    assert "k" in t.columns and t["k"].between(0, config.K_MAX).all()
    assert t["k_fc"].notna().all() and t["k"].notna().all()
    assert t[t["hour"] == 8]["k"].between(0.75, 1.1).all()      # SARAH-3 1015 vs TL=3 clear sky 1022 on 2025-06-10
    assert len(t) < len(features.build_features(site, weather_frame(fixture_json)))


def test_training_table_takes_nothing_but_the_target_from_the_satellite(site, fixture_json):
    w = weather_frame(fixture_json)
    air = feeds.hourly_frame(fixture_json("air_quality_history"))
    sat = feeds.hourly_frame(fixture_json("satellite"), feeds.SAT_RENAME)
    a = features.build_training_table(site, w, air, sat)
    b = features.build_training_table(site, w, air, sat.assign(sat_ghi=sat["sat_ghi"] * 2))
    pd.testing.assert_frame_equal(a[features.FEATURES], b[features.FEATURES])
    assert not a["k"].equals(b["k"])
    assert not any(c.startswith("sat_") for c in features.FEATURES)
