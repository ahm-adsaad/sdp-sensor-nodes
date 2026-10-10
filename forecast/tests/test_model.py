import json

import numpy as np
import pandas as pd

import features
import metrics
import model


def test_synthetic_table_has_the_expected_shape(site):
    t = model.synthetic_table(site, "2025-01-01", 30)
    assert set(["hour_start", "month", "k"] + features.FEATURES) <= set(t.columns)
    assert 250 < len(t) < 400 and t["k"].between(0, 1.5).all()


def test_train_predict_learns_the_rule_and_orders_levels(site):
    t = model.synthetic_table(site, "2024-06-01", 400)
    sky = model.train(t.iloc[:-500], max_rounds=400)
    test = t.iloc[-500:]
    p = model.predict(sky, test)
    assert list(p.columns) == ["q10", "q50", "q90"] and p.index.equals(test.index)
    assert (p["q10"] <= p["q50"]).all() and (p["q50"] <= p["q90"]).all()
    assert metrics.pinball(test["k"], p["q50"], 0.5) < metrics.pinball(test["k"], np.full(len(test), t["k"].median()), 0.5) * 0.7
    assert 0.03 < metrics.coverage_below(test["k"], p["q10"]) < 0.2
    assert all(b.num_trees() >= 10 for b in sky.boosters.values())


def test_predict_accepts_nan_dust(site):
    t = model.synthetic_table(site, "2024-06-01", 200)
    sky = model.train(t, max_rounds=100)
    test = t.iloc[-20:].copy()
    test[features.DUST_FEATURES] = np.nan
    p = model.predict(sky, test)
    assert p.notna().all().all()


def test_save_and_load_round_trip(site, tmp_path):
    t = model.synthetic_table(site, "2024-06-01", 120)
    sky = model.train(t, max_rounds=100)
    model.save(sky, tmp_path / "sky")
    assert (tmp_path / "sky" / "q50.txt").exists()
    meta = json.loads((tmp_path / "sky" / "meta.json").read_text())
    assert meta["features"] == features.FEATURES and meta["trained_rows"] == len(t)
    back = model.load(tmp_path / "sky")
    pd.testing.assert_frame_equal(model.predict(back, t.iloc[:30]), model.predict(sky, t.iloc[:30]))
