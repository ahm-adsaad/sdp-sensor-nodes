import pandas as pd

import config


def test_default_config_has_site_and_five_nodes():
    site, nodes = config.load_config()
    assert (site.lat, site.lon) == (25.29, 55.48)
    assert [n.id for n in nodes] == ["node-01", "node-02", "node-03", "node-04", "node-05"]
    assert all(n.panels == 1 and n.tilt_deg == 0 for n in nodes)


def test_load_config_from_path(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[site]\nname="x"\nlat=1.5\nlon=2.5\n[[nodes]]\nid="a"\npanels=2\ntilt_deg=20\n')
    site, nodes = config.load_config(p)
    assert site == config.Site("x", 1.5, 2.5, 0.0)
    assert nodes == [config.Node("a", 2, 20.0, 180.0)]


def test_utc_ns_normalises_strings_and_index():
    idx = config.utc_ns(["2025-06-10T00:00", "2025-06-10T01:00"])
    assert str(idx.dtype) == "datetime64[ns, UTC]"
    assert idx[1] - idx[0] == pd.Timedelta(hours=1)
    again = config.utc_ns(pd.DatetimeIndex(["2025-06-10 00:00"], tz="UTC").as_unit("s"))
    assert str(again.dtype) == "datetime64[ns, UTC]"
