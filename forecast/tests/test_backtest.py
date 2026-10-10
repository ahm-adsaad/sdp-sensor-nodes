import pandas as pd

import backtest
import model


def test_rolling_months_trains_only_on_the_past(site):
    t = model.synthetic_table(site, "2024-01-01", 300)
    folds = list(backtest.rolling_months(t, min_train_months=6))
    assert len(folds) == 4                                   # Jul, Aug, Sep, Oct
    for train, test in folds:
        assert train["hour_start"].max() < test["hour_start"].min()
        assert test["hour_start"].dt.month.nunique() == 1
    assert folds[0][0]["hour_start"].max() < pd.Timestamp("2024-07-01", tz="UTC")


def test_run_and_summarize(site):
    t = model.synthetic_table(site, "2024-01-01", 250)
    preds = backtest.run(t, max_rounds=150)
    assert set(preds["method"]) == set(backtest.METHODS)
    s = backtest.summarize(preds)
    assert list(s.columns) == ["method", "hours", "pinball10", "pinball50", "pinball90", "cov10", "mae_wm2"]
    s = s.set_index("method")
    assert s.loc["lightgbm", "pinball50"] < s.loc["climatology", "pinball50"]
    assert s.loc["lightgbm", "pinball50"] < s.loc["lightgbm_nodust", "pinball50"]   # the synthetic rule uses aod
    assert (s["cov10"].between(0.0, 0.4)).all()
    by_month = backtest.summarize(preds, by="month")
    assert set(by_month.columns) >= {"method", "month", "pinball10"}
    by_aod = backtest.summarize(preds.assign(aod_band=backtest.aod_band(preds["aerosol_optical_depth"])), by="aod_band")
    assert set(by_aod["aod_band"]) <= {"low", "mid", "high"}


def test_write_report_produces_markdown_and_csv(site, tmp_path):
    t = model.synthetic_table(site, "2024-01-01", 230)
    preds = backtest.run(t, methods=("lightgbm", "raw_forecast"), max_rounds=50)
    path = backtest.write_report(preds, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "| method |" in text and "lightgbm" in text and "raw_forecast" in text
    assert (tmp_path / "backtest.csv").exists() and (tmp_path / "backtest_by_month.csv").exists()
