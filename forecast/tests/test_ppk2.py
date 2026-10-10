import pathlib

import pandas as pd

import ppk2

SAMPLE = pathlib.Path(__file__).parent / "fixtures" / "ppk2_sample.csv"


def test_read_csv_parses_header_and_drops_blank_rows():
    s = ppk2.read_csv(SAMPLE)
    assert list(s.columns) == ["t_ms", "current_ua"]
    assert len(s) == 541 and s["t_ms"].is_monotonic_increasing
    assert s["current_ua"].iloc[0] == 10000.0 and s["current_ua"].iloc[-1] == 30000.0


def test_read_csv_accepts_digital_columns(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("Timestamp(ms),Current(uA),D0-D7\n0,5.000,00000000\n1000,6.000,00000000\n")
    s = ppk2.read_csv(p)
    assert list(s["current_ua"]) == [5.0, 6.0]


def test_hourly_energy_integrates_current_times_volts():
    s = ppk2.read_csv(SAMPLE)
    r = ppk2.hourly_energy(s, "2026-10-14T06:00:00Z", volts=3.0, node_id="node-01")
    assert set(r.columns) == {"node", "hour_start", "energy_j", "seconds", "source", "store_full"}
    r = r.set_index("hour_start")
    h0 = pd.Timestamp("2026-10-14 06:00", tz="UTC")
    assert abs(r.loc[h0, "energy_j"] - 0.010 * 3.0 * 3600) < 0.5          # 10 mA x 3 V x 1 h = 108 J
    assert abs(r.loc[h0, "seconds"] - 3600) <= 10
    assert (r["source"] == "ppk2").all() and (~r["store_full"]).all() and (r["node"] == "node-01").all()


def test_partial_hour_keeps_seconds():
    s = ppk2.read_csv(SAMPLE)
    r = ppk2.hourly_energy(s, "2026-10-14T06:00:00Z", volts=3.0, node_id="node-01").set_index("hour_start")
    h1 = pd.Timestamp("2026-10-14 07:00", tz="UTC")
    assert abs(r.loc[h1, "seconds"] - 1800) <= 10
    assert abs(r.loc[h1, "energy_j"] - 0.030 * 3.0 * 1800) < 2.0          # not scaled to a full hour


def test_negative_current_counts_as_zero_harvest():
    s = pd.DataFrame({"t_ms": [0, 1000, 2000], "current_ua": [-500.0, -500.0, -500.0]})
    r = ppk2.hourly_energy(s, "2026-10-14T06:00:00Z", volts=3.0, node_id="n")
    assert r["energy_j"].iloc[0] == 0.0 and r["seconds"].iloc[0] == 0.0


def test_recording_gap_adds_neither_seconds_nor_energy():
    s = pd.DataFrame({"t_ms": [0, 1000, 2000, 3000, 3_600_000 + 2000, 3_600_000 + 3000], "current_ua": [10000.0] * 6})
    r = ppk2.hourly_energy(s, "2026-10-14T06:00:00Z", volts=3.0, node_id="n").set_index("hour_start")
    h0, h1 = pd.Timestamp("2026-10-14 06:00", tz="UTC"), pd.Timestamp("2026-10-14 07:00", tz="UTC")
    assert abs(r.loc[h0, "seconds"] - 4.0) < 1e-9
    assert abs(r.loc[h1, "seconds"] - 1.0) < 1e-9                    # the 3,599 s pause is not credited
    assert abs(r.loc[h1, "energy_j"] - 0.010 * 3.0 * 1.0) < 1e-9


def test_seconds_count_only_the_time_the_panel_delivers_current():
    # 20 minutes at 30 mA (store charging), then 40 minutes of 50 uA trickle (store full), 10 s samples
    t_ms = [i * 10_000 for i in range(360)]
    current = [30000.0] * 120 + [50.0] * 240
    s = pd.DataFrame({"t_ms": t_ms, "current_ua": current})
    r = ppk2.hourly_energy(s, "2026-10-14T06:00:00Z", volts=3.0, node_id="n").set_index("hour_start")
    row = r.loc[pd.Timestamp("2026-10-14 06:00", tz="UTC")]
    assert abs(row["seconds"] - 1200) <= 10
    assert 108.0 <= row["energy_j"] <= 109.0           # 0.030 A x 3 V x 1200 s, plus a negligible trickle
