"""Embed out/assembly.glb and the placement labels into one self-contained HTML viewer.

Writes out/viewer.html. Run from enclosure/ after build.py:  .venv/Scripts/python.exe viewer.py
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import params as p  # noqa: E402

GLB_TOKEN = "__GLB_BASE64__"
LABELS_TOKEN = "__LABELS_JSON__"
LIMIT_BYTES = 15 * 1024 * 1024
PARTS = frozenset({"body", "lid", "pcb", "supercap", "sensors"})


def _label(title: str, note: str, part: str, x: float, y: float, z: float,
           reach: float = 1.0, key: bool = False) -> dict:
    return {"title": title, "note": note, "part": part,
            "at": [round(x, 2), round(y, 2), round(z, 2)], "reach": reach, "key": key}


def labels() -> list[dict]:
    """Placement labels, anchored in body coordinates in millimetres.

    part: the model part a label belongs to. The label hides with that part, and
    labels on the lid move with it. reach: how far the text sits from its anchor,
    so neighbouring labels stagger. key: highlighted, used for the sensors.
    """
    u5_x, u5_y = p.eda_to_body(4.32, 5.71)
    slot = p.pv_slots(p.pv_recesses(2)[0])[0]
    insert_x, insert_y = p.INSERT_XY[0]
    sensor_top = p.SENSOR_BOARD_Z + p.SENSOR_BOARD_T
    return [
        _label("SHT41 sensor", "Foam tape it onto this pad", "body",
               p.SHT41_PAD.cx, p.SHT41_PAD.cy, sensor_top, reach=1.6, key=True),
        _label("ENS160 sensor", "Foam tape it onto this pad", "body",
               p.ENS160_PAD.cx, p.ENS160_PAD.cy, sensor_top, reach=1.6, key=True),
        _label("Sensor wires", "Through this notch to J1", "body",
               p.WIRE_NOTCH_RECT.cx, p.SENSOR_WALL.cy, p.BODY_Z - p.WIRE_NOTCH_DEPTH / 2, reach=1.0),
        _label("Air vents", "Keep them clear", "body",
               p.BODY_X / 2, 0.0, p.VENT_ROWS_Z[len(p.VENT_ROWS_Z) // 2], reach=0.8),
        _label("Circuit board", "Press it onto the four pegs", "pcb",
               p.PANEL.cx, p.PANEL.cy, p.PANEL_TOP_Z, reach=0.6),
        _label("Screw terminal U5", "Solar panel leads go here", "pcb",
               u5_x, u5_y, p.PANEL_TOP_Z + 10.0, reach=1.2),
        _label("SMA antenna jack", "Bolt it through this hole", "body",
               0.0, p.SMA_Y, p.SMA_Z, reach=1.0),
        _label("Supercapacitor", "On the rails, zip tie underneath", "supercap",
               p.CAP.cx, p.CAP.cy, p.WALL + p.CAP_RAIL_H + p.CAP_H, reach=0.9),
        _label("Supercap leads", "Through this notch to C9", "body",
               p.CAP_DIVIDER.cx, p.DIVIDER_NOTCH.cy, p.WALL + p.DIVIDER_H, reach=1.3),
        _label("M3 insert", "Melt one into each corner", "body",
               insert_x, insert_y, p.BODY_Z, reach=0.8),
        _label("Solar lead slot", "Feed the panel leads through", "lid",
               slot.cx, slot.cy, p.BODY_Z + p.LID_T, reach=1.0),
    ]


def main() -> Path:
    glb = (HERE / "out" / "assembly.glb").read_bytes()
    template = (HERE / "viewer_template.html").read_text(encoding="utf-8")
    for token in (GLB_TOKEN, LABELS_TOKEN):
        if template.count(token) != 1:
            raise RuntimeError(f"viewer_template.html must contain {token} exactly once")
    html = (template.replace(GLB_TOKEN, base64.b64encode(glb).decode("ascii"))
                    .replace(LABELS_TOKEN, json.dumps(labels())))
    if len(html.encode("utf-8")) > LIMIT_BYTES:
        raise RuntimeError("viewer is over 15 MB; raise linear_deflection for the GLB in build.py")
    out = HERE / "out" / "viewer.html"
    out.write_text(html, encoding="utf-8")
    print(f"{out.relative_to(HERE)}  {out.stat().st_size / 1024:.0f} KB")
    return out


if __name__ == "__main__":
    main()
