import pytest

import build
import params as p


def test_lid_prints_top_face_down_on_the_bed():
    lid = build.print_ready(build.build_lid(2), flip=True)
    bb = lid.bounding_box()
    assert bb.min.Z == pytest.approx(0.0, abs=1e-6)
    assert bb.size.Z == pytest.approx(p.BODY_Z + p.LID_T - p.POST_TIP_Z, abs=0.01)


def test_export_writes_every_file(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "OUT", tmp_path)
    written = {path.name: path for path in build.export_all()}
    for part in ("body", "lid_1panel", "lid_2panel", "lid_3panel", "fit_coupon"):
        for suffix in (".stl", ".3mf", ".step"):
            assert written[f"{part}{suffix}"].stat().st_size > 1000
    assert written["assembly.glb"].stat().st_size > 1000
