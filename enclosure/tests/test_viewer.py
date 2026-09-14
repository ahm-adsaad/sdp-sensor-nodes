import json

import params as p
import viewer


def test_labels_cover_every_placement_and_stay_on_the_model():
    items = viewer.labels()
    titles = {i["title"] for i in items}
    for needed in ("SHT41 sensor", "ENS160 sensor", "Sensor wires", "Circuit board",
                   "Supercapacitor", "SMA antenna jack", "Solar lead slot"):
        assert needed in titles
    for i in items:
        assert i["part"] in viewer.PARTS
        x, y, z = i["at"]
        assert -p.EAR_OUT - 1 <= x <= p.BODY_X + p.EAR_OUT + 1
        assert -p.COLUMN_OUT - 3 <= y <= p.BODY_Y + p.COLUMN_OUT + 3
        assert 0 <= z <= p.BODY_Z + p.LID_T + 1
        assert 0.5 <= i["reach"] <= 2.0
    assert [i["key"] for i in items if i["title"].endswith("sensor")] == [True, True]


def test_sensor_labels_point_at_their_pads():
    by_title = {i["title"]: i for i in viewer.labels()}
    for title, pad in (("SHT41 sensor", p.SHT41_PAD), ("ENS160 sensor", p.ENS160_PAD)):
        x, y, _ = by_title[title]["at"]
        assert pad.contains_point(x, y)


def test_main_embeds_model_and_labels(tmp_path, monkeypatch):
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "assembly.glb").write_bytes(b"glTF-test")
    (tmp_path / "viewer_template.html").write_text(
        'const GLB = "__GLB_BASE64__"; const LABELS = __LABELS_JSON__;', encoding="utf-8")
    monkeypatch.setattr(viewer, "HERE", tmp_path)
    html = viewer.main().read_text(encoding="utf-8")
    assert "__GLB_BASE64__" not in html and "__LABELS_JSON__" not in html
    labels_json = html.split("const LABELS = ", 1)[1].rstrip(";")
    assert json.loads(labels_json) == viewer.labels()
