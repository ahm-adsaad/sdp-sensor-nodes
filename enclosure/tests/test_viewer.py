import json
import os

import pytest

import params as p
import viewer

pinned = pytest.mark.skipif(os.environ.get("ENCLOSURE_BOARD") == "export", reason="numbers pinned to the ruler outline")


def test_labels_cover_every_placement_and_stay_on_the_model():
    items = viewer.labels()
    titles = {i["title"] for i in items}
    for needed in ("SHT41 sensor", "ENS160 sensor", "Sensor leads", "Circuit board", "Cell",
                   "SMA antenna jack", "Solar panel", "Solar lead hole", "Louvres", "Eave vents", "M3 insert"):
        assert needed in titles
    top = p.LID_Z1 + p.FRONT_LIFT + p.WEDGE_RISE + 3.0
    for i in items:
        assert i["part"] in viewer.PARTS
        x, y, z = i["at"]
        assert -p.EAR_OUT - 1 <= x <= p.BODY_X + p.EAR_OUT + 1 or i["part"] in ("lid", "wedge", "panel")
        assert p.LID.x0 - 1 <= x <= p.LID.x1 + 1
        assert p.LID.y0 - 1 <= y <= p.LID.y1 + 1
        assert 0 <= z <= top
        assert 0.5 <= i["reach"] <= 2.0
    assert [i["key"] for i in items if i["title"].endswith("sensor")] == [True, True]


def test_sensor_labels_point_at_their_pads():
    by_title = {i["title"]: i for i in viewer.labels()}
    for title, pad in (("SHT41 sensor", p.SHT41_PAD), ("ENS160 sensor", p.ENS160_PAD)):
        x, y, _ = by_title[title]["at"]
        assert pad.contains_point(x, y)


def test_lid_stack_labels_ride_with_the_lid():
    by_title = {i["title"]: i for i in viewer.labels()}
    assert by_title["Solar panel"]["part"] == "panel"
    assert by_title["Solar lead hole"]["part"] == "lid"
    assert viewer.LIFTED == frozenset({"lid", "wedge", "panel"})


@pinned
def test_main_embeds_model_labels_and_dimensions(tmp_path, monkeypatch):
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "assembly.glb").write_bytes(b"glTF-test")
    (tmp_path / "viewer_template.html").write_text(
        'const GLB = "__GLB_BASE64__"; const LABELS = __LABELS_JSON__; const LIFTED = __LIFTED_JSON__;'
        '<tbody>__DIMENSIONS_HTML__</tbody>',
        encoding="utf-8")
    monkeypatch.setattr(viewer, "HERE", tmp_path)
    html = viewer.main().read_text(encoding="utf-8")
    for token in ("__GLB_BASE64__", "__LABELS_JSON__", "__LIFTED_JSON__", "__DIMENSIONS_HTML__"):
        assert token not in html
    labels_json = html.split("const LABELS = ", 1)[1].split("; const LIFTED")[0]
    assert json.loads(labels_json) == viewer.labels()
    assert "<tr><th scope=\"row\">Body walls</th><td>80.4 &times; 51.4 &times; 78.1</td></tr>" in html
    assert "145.4" not in html


@pinned
def test_dimension_rows_come_from_params():
    rows = dict(viewer.dimensions())
    assert rows["Body walls"] == "80.4 × 51.4 × 78.1"
    assert rows["Lid"] == "124.0 × 75.4"
    assert rows["Board pocket"] == "53.6 × 38.6"
    assert rows["Panel plate"].startswith("120.0 × 42.0")
    assert "Wall" in rows and rows["Wall"] == "2.4"


def test_template_lifts_the_whole_lid_stack():
    template = (viewer.HERE / "viewer_template.html").read_text(encoding="utf-8")
    assert template.count(viewer.LIFTED_TOKEN) == 1
    assert template.count(viewer.DIMENSIONS_TOKEN) == 1
    for name in sorted(viewer.PARTS):
        assert f'"{name}"' in template
    assert "rev 2" in template and "Two panels" not in template
    assert "lid_2panel" not in template and "wedge.3mf" in template
