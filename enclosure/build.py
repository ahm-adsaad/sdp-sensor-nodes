"""Export every printable part to out/ in print orientation, plus an assembly GLB for the viewer.

Run from enclosure/:  .venv/Scripts/python.exe build.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build123d import Color, Compound, Mesher, Part, Pos, export_gltf, export_step, export_stl  # noqa: E402

from body import build_body  # noqa: E402
from coupon import build_coupon  # noqa: E402
from lid import build_lid  # noqa: E402
from shapes import cell, pcb_board, print_ready, sensor_boards, solar_panel  # noqa: E402
from wedge import build_wedge  # noqa: E402

__all__ = ["build_body", "build_coupon", "build_lid", "build_wedge", "print_ready", "parts", "export_all", "OUT", "LID_LIFT"]

OUT = HERE / "out"
LID_LIFT = 45.0   # how far the lid, wedge and panel float above the body in the assembly view

COLOURS = {
    "body": Color(0.92, 0.92, 0.89),
    "lid": Color(0.80, 0.84, 0.88),
    "wedge": Color(0.80, 0.84, 0.88),
    "pcb": Color(0.08, 0.32, 0.66),
    "cell": Color(0.18, 0.18, 0.20),
    "sensors": Color(0.12, 0.55, 0.45),
    "panel": Color(0.12, 0.12, 0.16),
}


def parts() -> dict[str, tuple[Part, bool]]:
    """Printable parts by file name, each with whether it prints upside down."""
    return {
        "body": (build_body(), False),
        "lid": (build_lid(), True),
        "wedge": (build_wedge(), False),
        "fit_coupon": (build_coupon(), False),
    }


def assembly_parts(body: Part, lid: Part, wedge: Part) -> list[Part]:
    """Labelled, coloured parts for the viewer, with the lid stack lifted off the body."""
    items = {
        "body": body,
        "lid": Pos(0, 0, LID_LIFT) * lid,
        "wedge": Pos(0, 0, LID_LIFT) * wedge,
        "pcb": pcb_board(),
        "cell": cell(),
        "sensors": sensor_boards(),
        "panel": Pos(0, 0, LID_LIFT) * solar_panel(),
    }
    out = []
    for name, part in items.items():
        part.label, part.color = name, COLOURS[name]
        out.append(part)
    return out


def _write_3mf(part: Part, path: Path) -> None:
    mesher = Mesher()
    mesher.add_shape(part, linear_deflection=0.01, angular_deflection=0.2)
    mesher.write(str(path))


def _write_assembly(body: Part, lid: Part, wedge: Part) -> Path:
    path = OUT / "assembly.glb"
    export_gltf(Compound(children=assembly_parts(body, lid, wedge)), str(path), binary=True,
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
    written.append(_write_assembly(models["body"][0], models["lid"][0], models["wedge"][0]))
    return written


if __name__ == "__main__":
    for path in export_all():
        print(f"{path.name:22} {path.stat().st_size / 1024:8.0f} KB")
