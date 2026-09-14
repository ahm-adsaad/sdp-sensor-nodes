"""Export every printable part to out/ in print orientation, plus an assembly GLB for the viewer.

Run from enclosure/:  .venv/Scripts/python.exe build.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build123d import Color, Compound, Mesher, Part, Pos, Rot, export_gltf, export_step, export_stl  # noqa: E402

from body import build_body  # noqa: E402
from coupon import build_coupon  # noqa: E402
from lid import build_lid  # noqa: E402
from shapes import pcb_panel, sensor_boards, supercap  # noqa: E402

OUT = HERE / "out"
LID_LIFT = 40.0   # how far the lid floats above the body in the assembly view


def print_ready(part: Part, flip: bool) -> Part:
    """Optionally turn the part upside down, then centre it on the bed with its lowest point on z=0."""
    if flip:
        part = Rot(180, 0, 0) * part
    bb = part.bounding_box()
    return Pos(-bb.center().X, -bb.center().Y, -bb.min.Z) * part


def parts() -> dict[str, tuple[Part, bool]]:
    """Printable parts by file name, each with whether it prints upside down."""
    return {
        "body": (build_body(), False),
        "lid_2panel": (build_lid(2), True),
        "lid_3panel": (build_lid(3), True),
        "fit_coupon": (build_coupon(), False),
    }


def _write_3mf(part: Part, path: Path) -> None:
    mesher = Mesher()
    mesher.add_shape(part, linear_deflection=0.01, angular_deflection=0.2)
    mesher.write(str(path))


def _write_assembly(body: Part, lid: Part) -> Path:
    body = Pos(0, 0, 0) * body
    body.label, body.color = "body", Color(0.92, 0.92, 0.89)
    lid = Pos(0, 0, LID_LIFT) * lid
    lid.label, lid.color = "lid", Color(0.80, 0.84, 0.88)
    board = pcb_panel()
    board.label, board.color = "pcb", Color(0.08, 0.32, 0.66)
    cap = supercap()
    cap.label, cap.color = "supercap", Color(0.18, 0.18, 0.20)
    boards = sensor_boards()
    boards.label, boards.color = "sensors", Color(0.12, 0.55, 0.45)
    path = OUT / "assembly.glb"
    export_gltf(Compound(children=[body, lid, board, cap, boards]), str(path), binary=True,
                linear_deflection=0.05, angular_deflection=0.3)
    return path


def export_all() -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    models = parts()
    written: list[Path] = []
    for name, (model, flip) in models.items():
        if not model.is_valid:
            raise RuntimeError(f"{name} is not a valid solid")
        printable = print_ready(model, flip)
        export_stl(printable, str(OUT / f"{name}.stl"), tolerance=0.01, angular_tolerance=0.2)
        _write_3mf(printable, OUT / f"{name}.3mf")
        export_step(printable, str(OUT / f"{name}.step"))
        written += [OUT / f"{name}{suffix}" for suffix in (".stl", ".3mf", ".step")]
    written.append(_write_assembly(models["body"][0], models["lid_2panel"][0]))
    return written


if __name__ == "__main__":
    for path in export_all():
        print(f"{path.name:22} {path.stat().st_size / 1024:8.0f} KB")
