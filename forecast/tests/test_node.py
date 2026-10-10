import numpy as np
import pandas as pd

import config
import node
import simulate
import solar


def june_hours(days=1, start="2025-06-10"):
    return pd.date_range(start, periods=24 * days, freq="h", tz="UTC")


def elevation(site, hs):
    return solar.sun_position(site, hs)["elevation"]


def records_for(site, nd, days, ratio, store_full_hours=()):
    """Simulated week(s) at k = 0.95 with the given node ratio; returns (records, k)."""
    hs = june_hours(days)
    k = pd.Series(0.95, index=hs)
    full = pd.Series([h.hour in store_full_hours for h in hs], index=hs)
    return simulate.harvest_records(site, nd, hs, k, ratio, store_full=full), k


def test_clear_sky_energy_scales_with_panels_and_rating(site):
    hs = june_hours()
    one = node.clear_sky_energy_j(site, config.Node("a", 1, 0, 180), hs)
    two = node.clear_sky_energy_j(site, config.Node("b", 2, 0, 180), hs)
    assert one.name == "e_clear_j" and one.index.equals(hs)
    noon = pd.Timestamp("2025-06-10 08:00", tz="UTC")
    assert abs(one[noon] - 0.150 * 1022 / 1000 * 3600) < 12       # about 552 J
    assert np.allclose(two, 2 * one)
    assert one[pd.Timestamp("2025-06-10 20:00", tz="UTC")] == 0
    assert 4000 < one.sum() < 4600                                  # 8.23 kWh/m2 x 0.15 W x 3.6


def test_expected_energy_is_clear_sky_times_k(site, node_cfg):
    hs = june_hours()
    k = pd.Series(0.5, index=hs)
    exp = node.expected_energy_j(site, node_cfg, k)
    assert exp.name == "expected_j" and exp.index.equals(hs)
    assert np.allclose(exp, node.clear_sky_energy_j(site, node_cfg, hs) * 0.5)


def test_node_ratio_recovers_the_simulated_ratio(site, node_cfg):
    recs, k = records_for(site, node_cfg, 7, 0.8)
    out = node.node_ratio(recs, node.expected_energy_j(site, node_cfg, k), elevation(site, k.index))
    assert abs(out.ratio - 0.8) < 0.01 and out.usable_hours >= 5 * 7 and not out.is_default


def test_node_ratio_excludes_store_full_hours(site, node_cfg):
    clean, k = records_for(site, node_cfg, 7, 0.8)
    recs, _ = records_for(site, node_cfg, 7, 0.8, store_full_hours=(8, 9, 10))
    expected = node.expected_energy_j(site, node_cfg, k)
    base = node.node_ratio(clean, expected, elevation(site, k.index))
    out = node.node_ratio(recs, expected, elevation(site, k.index))
    assert abs(out.ratio - 0.8) < 0.01
    assert out.usable_hours == base.usable_hours - 3 * 7


def test_node_ratio_infers_store_full_from_dark_hours(site, node_cfg):
    recs, k = records_for(site, node_cfg, 7, 0.8)
    recs = recs.copy()
    midday = recs["hour_start"].dt.hour.between(7, 11)
    recs.loc[midday, "energy_j"] = 0.0                               # panel current gone while the sun is up
    out = node.node_ratio(recs, node.expected_energy_j(site, node_cfg, k), elevation(site, k.index))
    base = node.node_ratio(records_for(site, node_cfg, 7, 0.8)[0], node.expected_energy_j(site, node_cfg, k), elevation(site, k.index))
    assert abs(out.ratio - 0.8) < 0.01
    assert out.usable_hours == base.usable_hours - 5 * 7


def test_node_ratio_ignores_short_hours(site, node_cfg):
    clean, k = records_for(site, node_cfg, 7, 0.8)
    expected = node.expected_energy_j(site, node_cfg, k)
    base = node.node_ratio(clean, expected, elevation(site, k.index))
    recs = clean.copy()
    at_five = recs["hour_start"].dt.hour == 5                        # a daylight hour, 7 rows
    recs.loc[at_five, "seconds"] = 300.0                             # under the 600 s minimum
    recs.loc[at_five, "energy_j"] = recs.loc[at_five, "energy_j"] * 300 / 3600   # would drag the ratio down if counted
    out = node.node_ratio(recs, expected, elevation(site, k.index))
    assert abs(out.ratio - 0.8) < 0.01
    assert out.usable_hours == base.usable_hours - 7


def test_node_ratio_keeps_previous_when_too_few_hours(site, node_cfg):
    recs, k = records_for(site, node_cfg, 1, 0.8)
    recs = recs.head(3)
    out = node.node_ratio(recs, node.expected_energy_j(site, node_cfg, k), elevation(site, k.index), previous=0.9)
    assert out.ratio == 0.9 and out.is_default


def test_node_ratio_uses_only_the_window(site, node_cfg):
    old, k_old = records_for(site, node_cfg, 7, 0.5)
    new, _ = records_for(site, node_cfg, 7, 0.8)
    new = new.assign(hour_start=new["hour_start"] + pd.Timedelta(days=7))
    k = pd.concat([k_old, pd.Series(0.95, index=k_old.index + pd.Timedelta(days=7))])
    recs = pd.concat([old, new], ignore_index=True)
    out = node.node_ratio(recs, node.expected_energy_j(site, node_cfg, k), elevation(site, k.index), window_days=7)
    assert abs(out.ratio - 0.8) < 0.01


def test_node_forecast_scales_and_fills_night_with_zero(site, node_cfg):
    hs = june_hours()
    sun = elevation(site, hs).to_numpy()
    day, night = hs[sun > config.MIN_ELEVATION_DEG], hs[sun <= config.MIN_ELEVATION_DEG]
    k_q = pd.DataFrame({"q10": 0.5, "q50": 0.8, "q90": 1.0}, index=day)
    f = node.node_forecast(site, node_cfg, hs, k_q, 0.9)
    assert list(f.columns) == ["hour_start", "q10_j", "q50_j", "q90_j"] and len(f) == 24
    e = node.clear_sky_energy_j(site, node_cfg, hs)
    noon = pd.Timestamp("2025-06-10 08:00", tz="UTC")
    by_hour = f.set_index("hour_start")
    assert abs(by_hour.loc[noon, "q50_j"] - e[noon] * 0.8 * 0.9) < 1e-6
    assert (by_hour.loc[night] == 0).all().all()
    assert (f["q10_j"] <= f["q50_j"]).all() and (f["q50_j"] <= f["q90_j"]).all()


def test_node_ratio_measures_power_when_the_store_fills_mid_hour(site, node_cfg):
    clean, k = records_for(site, node_cfg, 7, 0.8)
    expected = node.expected_energy_j(site, node_cfg, k)
    base = node.node_ratio(clean, expected, elevation(site, k.index))
    recs = clean.copy()
    at_nine = recs["hour_start"].dt.hour == 9                        # store full after twenty minutes
    recs.loc[at_nine, "seconds"] = 1200.0
    recs.loc[at_nine, "energy_j"] = recs.loc[at_nine, "energy_j"] * 1200 / 3600
    out = node.node_ratio(recs, expected, elevation(site, k.index))
    assert abs(out.ratio - 0.8) < 0.01 and out.usable_hours == base.usable_hours
