"""Embed out/assembly.glb and the placement labels into one self-contained HTML viewer.

Writes out/viewer.html. Run from enclosure/ after build.py:  .venv/Scripts/python.exe viewer.py
"""
from __future__ import annotations

import base64
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import params as p  # noqa: E402

GLB_TOKEN = "__GLB_BASE64__"
LABELS_TOKEN = "__LABELS_JSON__"
LIFTED_TOKEN = "__LIFTED_JSON__"
DIMENSIONS_TOKEN = "__DIMENSIONS_HTML__"
LIMIT_BYTES = 15 * 1024 * 1024
PARTS = frozenset({"body", "lid", "wedge", "pcb", "cell", "sensors", "panel"})
LIFTED = frozenset({"lid", "wedge", "panel"})   # the stack that lifts off the body together


def _label(title: str, note: str, part: str, x: float, y: float, z: float,
           reach: float = 1.0, key: bool = False) -> dict:
    return {"title": title, "note": note, "part": part,
            "at": [round(x, 2), round(y, 2), round(z, 2)], "reach": reach, "key": key}


def _panel_centre() -> tuple[float, float, float]:
    a = math.radians(p.PANEL_ANGLE)
    x0, y0 = p.WEDGE_ORIGIN
    ly, lz = p.PLATE_W / 2, p.PLATE_T + p.PV_T
    return (x0 + p.PLATE_L / 2,
            y0 + ly * math.cos(a) - lz * math.sin(a),
            p.LID_Z1 + p.FRONT_LIFT + ly * math.sin(a) + lz * math.cos(a))


def labels() -> list[dict]:
    """Placement labels, anchored in body coordinates in millimetres.

    part: the model part a label belongs to. The label hides with that part, and
    labels on the lifted stack move with it. reach: how far the text sits from
    its anchor, so neighbouring labels stagger. key: highlighted, for the sensors.
    """
    sensor_top = p.SENSOR_BOARD_Z + p.SENSOR_BOARD_T
    insert_x, insert_y = p.INSERT_XY[0]
    front_notch = next(c for wall, c in p.NOTCHES if wall == "front")
    px, py, pz = _panel_centre()
    return [
        _label("SHT41 sensor", "Foam tape it onto this pad, in the shade", "sensors",
               p.SHT41_PAD.cx, p.SHT41_PAD.cy, sensor_top, reach=1.6, key=True),
        _label("ENS160 sensor", "Foam tape it onto this pad", "sensors",
               p.ENS160_PAD.cx, p.ENS160_PAD.cy, sensor_top, reach=1.6, key=True),
        _label("Sensor leads", "Down through this slot, one plug at a time, to J3", "body",
               p.CHANNEL_SLOT_RECT.cx, p.CHANNEL_SLOT_RECT.cy, p.Z_FLOOR, reach=1.2),
        _label("Louvres", "Air comes in here; keep them clear", "body",
               p.BODY_X / 2, 0.0, p.LOUVRE_ROWS_Z[0], reach=0.8),
        _label("Eave vents", "Warm air leaves under the lid", "body",
               front_notch, p.WALL / 2, p.BODY_Z - p.NOTCH_D / 2, reach=0.9),
        _label("Circuit board", "Terminal edge toward the wire bay", "pcb",
               p.BOARD.cx, p.BOARD.cy, p.BOARD_TOP_Z, reach=0.6),
        _label("Storage terminal U11", "Cell leads screw in here", "pcb",
               p.U11_XY[0], p.U11_XY[1], p.BOARD_TOP_Z + p.TERMINAL_H, reach=1.2),
        _label("Solar terminal U9", "Panel leads screw in here", "pcb",
               p.U9_XY[0], p.U9_XY[1], p.BOARD_TOP_Z + p.TERMINAL_H, reach=1.4),
        _label("Cell", "On the V-blocks, zip tie under it, leads to the back", "cell",
               p.CELL_X, (p.CELL_Y0 + p.CELL_Y1) / 2, p.CELL_AXIS_Z + p.CELL_R, reach=0.9),
        _label("SMA antenna jack", "Bolt it through this hole in the back wall", "body",
               p.SMA_X, p.BODY_Y, p.SMA_Z, reach=1.0),
        _label("M3 insert", "Melt one into each corner, and one into each lid boss", "body",
               insert_x, insert_y, p.BODY_Z, reach=0.8),
        _label("Solar lead hole", "Panel leads drop through here to U9", "lid",
               p.PV_HOLE_XY[0], p.PV_HOLE_XY[1], p.LID_Z1, reach=1.0),
        _label("Solar panel", "Stick it inside the rim, leads through a slot", "panel",
               px, py, pz, reach=1.0),
        _label("Wedge screws", "Four M3 x 12 into the lid bosses", "wedge",
               p.BOSS_XY[0][0], p.BOSS_XY[0][1], p.LID_Z1 + p.FOOT_T, reach=1.1),
    ]


def _size(*values: float) -> str:
    return " × ".join(f"{v:.1f}" for v in values)


def dimensions() -> list[tuple[str, str]]:
    """Rows for the viewer's dimension table, in millimetres, straight from params."""
    wedge_h = p.FRONT_LIFT + p.WEDGE_RISE
    return [
        ("Body walls", _size(p.BODY_X, p.BODY_Y, p.BODY_Z)),
        ("With ears and columns", _size(p.BODY_X + 2 * p.EAR_OUT, p.BODY_Y + 2 * p.COLUMN_OUT)),
        ("Height with lid and wedge", _size(p.LID_Z1 + wedge_h)),
        ("Electronics cavity", _size(p.INNER_X, p.INNER_Y, p.ABOVE_BOARD + p.BOARD_T + p.BOARD_STANDOFF)),
        ("Sensor shield", _size(p.SENSOR_INNER.w, p.SENSOR_INNER.d, p.Z_CEILING - p.Z_LOWER_FLOOR)),
        ("Lid", _size(p.LID.w, p.LID.d)),
        ("Board pocket", _size(p.POCKET_X, p.POCKET_Y)),
        ("Wire bay", _size(p.WIRE_BAY.w, p.WIRE_BAY.d)),
        ("Panel plate", f"{_size(p.PLATE_L, p.PLATE_W)} at {p.PANEL_ANGLE:.0f}°"),
        ("Wall", f"{p.WALL:.1f}"),
    ]


def _dimensions_html() -> str:
    rows = []
    for name, value in dimensions():
        rows.append(f'<tr><th scope="row">{name}</th><td>{value.replace("×", "&times;")}</td></tr>')
    return "\n".join(rows)


def main() -> Path:
    glb = (HERE / "out" / "assembly.glb").read_bytes()
    template = (HERE / "viewer_template.html").read_text(encoding="utf-8")
    for token in (GLB_TOKEN, LABELS_TOKEN, LIFTED_TOKEN, DIMENSIONS_TOKEN):
        if template.count(token) != 1:
            raise RuntimeError(f"viewer_template.html must contain {token} exactly once")
    html = (template.replace(GLB_TOKEN, base64.b64encode(glb).decode("ascii"))
                    .replace(LABELS_TOKEN, json.dumps(labels()))
                    .replace(LIFTED_TOKEN, json.dumps(sorted(LIFTED)))
                    .replace(DIMENSIONS_TOKEN, _dimensions_html()))
    if len(html.encode("utf-8")) > LIMIT_BYTES:
        raise RuntimeError("viewer is over 15 MB; raise linear_deflection for the GLB in build.py")
    out = HERE / "out" / "viewer.html"
    out.write_text(html, encoding="utf-8")
    print(f"{out.relative_to(HERE)}  {out.stat().st_size / 1024:.0f} KB")
    return out


if __name__ == "__main__":
    main()
