import pandas as pd

import node
import simulate


def test_records_follow_schema_and_physics(site, node_cfg):
    hs = pd.date_range("2025-06-10", periods=24, freq="h", tz="UTC")
    k = pd.Series(0.9, index=hs)
    full = pd.Series(False, index=hs)
    full[hs[12]] = True
    r = simulate.harvest_records(site, node_cfg, hs, k, 0.7, store_full=full)
    assert set(r.columns) == {"node", "hour_start", "energy_j", "seconds", "source", "store_full"}
    assert (r["source"] == "sim").all() and (r["seconds"] == 3600).all() and (r["node"] == "node-01").all()
    e = node.clear_sky_energy_j(site, node_cfg, hs)
    noon = pd.Timestamp("2025-06-10 08:00", tz="UTC")
    by_hour = r.set_index("hour_start")
    assert abs(by_hour.loc[noon, "energy_j"] - e[noon] * 0.9 * 0.7) < 1e-6
    assert by_hour.loc[hs[12], "energy_j"] == 0 and by_hour.loc[hs[12], "store_full"]


def test_ratio_can_vary_by_hour(site, node_cfg):
    hs = pd.date_range("2025-06-10", periods=48, freq="h", tz="UTC")
    ratio = pd.Series([0.9] * 24 + [0.5] * 24, index=hs)
    r = simulate.harvest_records(site, node_cfg, hs, pd.Series(1.0, index=hs), ratio)
    day1 = r[r["hour_start"] < hs[24]]["energy_j"].sum()
    day2 = r[r["hour_start"] >= hs[24]]["energy_j"].sum()
    assert abs(day2 / day1 - 0.5 / 0.9) < 0.02
