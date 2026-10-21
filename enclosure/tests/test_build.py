import pytest

import build
import params as p


def test_parts_are_the_four_rev2_prints_with_only_the_lid_flipped():
    models = build.parts()
    assert set(models) == {"body", "lid", "wedge", "fit_coupon"}
    assert [name for name, (_, flip) in models.items() if flip] == ["lid"]


def test_lid_prints_top_face_down_on_the_bed():
    lid = build.print_ready(build.build_lid(), flip=True)
    bb = lid.bounding_box()
    assert bb.min.Z == pytest.approx(0.0, abs=1e-6)
    assert bb.size.Z == pytest.approx(p.LID_Z1 - p.POST_TIP_BOARD_Z, abs=0.01)


def test_export_writes_every_file(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "OUT", tmp_path)
    written = {path.name: path for path in build.export_all()}
    for part in ("body", "lid", "wedge", "fit_coupon"):
        for suffix in (".stl", ".3mf", ".step"):
            assert written[f"{part}{suffix}"].stat().st_size > 1000
    assert written["assembly.glb"].stat().st_size > 1000
    assert not any(name.startswith("lid_") for name in written)
