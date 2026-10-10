import pandas as pd

import config
import solar


def hours(day):
    return pd.date_range(f"{day} 00:00", f"{day} 23:00", freq="h", tz="UTC")


def test_solar_noon_elevation_matches_noaa(site):
    # NOAA: 2025-06-10 solar noon at 55.48 E is 08:17 UTC, max elevation 87.7 deg.
    hs = config.utc_ns(["2025-06-10T07:47"])  # mid-hour = 08:17
    sp = solar.sun_position(site, hs)
    assert abs(sp["elevation"].iloc[0] - 87.7) < 0.5


def test_sun_is_down_before_sunrise_and_up_after(site):
    # sunrise 2025-06-10 is 01:28 UTC
    sp = solar.sun_position(site, config.utc_ns(["2025-06-10T00:30", "2025-06-10T01:30"]))
    assert sp["elevation"].iloc[0] < 0
    assert sp["elevation"].iloc[1] > 0


def test_december_noon_elevation(site):
    sp = solar.sun_position(site, hours("2025-12-21"))
    assert 40.0 <= sp["elevation"].max() <= 42.0


def test_clearsky_june_noon_and_night(site):
    cs = solar.clearsky(site, hours("2025-06-10"))
    noon = cs.loc[pd.Timestamp("2025-06-10 08:00", tz="UTC")]
    assert abs(noon["cs_ghi"] - 1022) < 15
    assert noon["cs_dni"] > 850 and 80 < noon["cs_dhi"] < 130
    assert cs.loc[pd.Timestamp("2025-06-10 20:00", tz="UTC"), "cs_ghi"] == 0
    assert (cs >= 0).all().all()


def test_clearsky_is_indexed_by_hour_start(site):
    hs = hours("2025-06-10")
    cs = solar.clearsky(site, hs)
    assert cs.index.equals(hs)


def test_flat_poa_equals_ghi_and_tilt_changes_it(site):
    hs = hours("2025-06-10")
    cs = solar.clearsky(site, hs)
    flat = solar.clearsky_poa(site, hs, 0.0, 180.0)
    assert flat.name == "cs_poa"
    assert (flat - cs["cs_ghi"]).abs().max() < 1.0
    tilted = solar.clearsky_poa(site, hs, 20.0, 180.0)
    noon = pd.Timestamp("2025-06-10 08:00", tz="UTC")
    assert tilted[noon] < flat[noon]          # June sun is nearly overhead
    assert tilted.sum() > 0
