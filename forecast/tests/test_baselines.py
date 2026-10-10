import numpy as np
import pandas as pd

import baselines


def table(start, days, k_fc, k):
    hs = pd.date_range(start, periods=days * 24, freq="h", tz="UTC")
    t = pd.DataFrame({"hour_start": hs, "month": hs.month, "hour": hs.hour})
    t = t[(t["hour"] >= 3) & (t["hour"] <= 13)].reset_index(drop=True)
    rng = np.random.default_rng(0)
    t["k_fc"] = k_fc
    t["k"] = np.clip(k + rng.normal(0, 0.05, len(t)), 0, 1.5)
    return t


def test_climatology_is_per_month_and_hour():
    train = pd.concat([table("2025-01-01", 20, 0.9, 0.7), table("2025-06-01", 20, 0.9, 1.0)], ignore_index=True)
    test = table("2025-06-21", 2, 0.9, 1.0)
    out = baselines.climatology(train, test)
    assert list(out.columns) == ["q10", "q50", "q90"] and len(out) == len(test)
    assert out["q50"].between(0.9, 1.1).all()
    assert (out["q10"] <= out["q50"]).all() and (out["q50"] <= out["q90"]).all()


def test_climatology_falls_back_to_overall_for_unseen_month():
    train = table("2025-06-01", 20, 0.9, 1.0)
    out = baselines.climatology(train, table("2025-12-01", 1, 0.9, 1.0))
    assert out["q50"].between(0.9, 1.1).all()


def test_raw_forecast_centres_on_k_fc_with_residual_band():
    train = table("2025-06-01", 30, 0.9, 1.0)       # actual sits 0.1 above the forecast
    test = table("2025-07-01", 2, 0.8, 0.9)
    out = baselines.raw_forecast(train, test)
    assert (out["q50"] == 0.8).all()
    offs = baselines.residual_offsets(train)
    assert 0.0 < offs["q10"] < offs["q90"] < 0.25
    assert np.allclose(out["q10"], 0.8 + offs["q10"]) and np.allclose(out["q90"], 0.8 + offs["q90"])


def test_persistence_uses_the_same_hour_yesterday():
    train = table("2025-06-01", 10, 0.9, 1.0)
    test = table("2025-06-11", 2, 0.9, 1.0)
    k_all = pd.concat([train, test]).set_index("hour_start")["k"]
    out = baselines.persistence(k_all, test, train)
    expected = k_all.reindex(test["hour_start"] - pd.Timedelta(hours=24)).to_numpy()
    assert np.allclose(out["q50"].to_numpy(), expected)
    assert (out["q10"] <= out["q50"]).all() and (out["q90"] >= out["q50"]).all()
