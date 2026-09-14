"""The body: shell, corner columns and ears, panel ledge and pegs, supercap rails,
sensor bay with angled vents, and every hole and notch."""
from __future__ import annotations

from build123d import Box, Part, Pos, Rot

import params as p
from shapes import EPS, peg, rod, slab, sma_cutter

Rect = p.Rect


def _additions() -> list[Part]:
    top = p.BODY_Z
    floor = p.WALL - EPS
    solids = [slab(c, 0, top) for c in p.COLUMNS]
    solids += [slab(e, 0, p.WALL) for e in p.EARS]
    # sensor bay walls thickened inward to carry vents, and the wall that seals the bay
    solids += [
        slab(Rect(p.WALL - EPS, p.WALL - EPS, p.BODY_X - p.WALL + EPS, p.VENT_WALL), floor, top),
        slab(Rect(p.WALL - EPS, p.WALL - EPS, p.VENT_WALL, p.SENSOR_WALL.y0 + EPS), floor, top),
        slab(Rect(p.BODY_X - p.VENT_WALL, p.WALL - EPS, p.BODY_X - p.WALL + EPS, p.SENSOR_WALL.y0 + EPS),
             floor, top),
        slab(Rect(p.WALL - EPS, p.SENSOR_WALL.y0, p.BODY_X - p.WALL + EPS, p.SENSOR_WALL.y1), floor, top),
        slab(Rect(p.CAP_DIVIDER.x0, p.CAP_DIVIDER.y0 - EPS, p.CAP_DIVIDER.x1, p.CAP_DIVIDER.y1 + EPS),
             floor, p.WALL + p.DIVIDER_H),
    ]
    ledge = slab(p.LEDGE_OUTER.inset(-EPS), floor, p.PANEL_BOTTOM_Z).cut(
        slab(p.LEDGE_INNER, 0, p.PANEL_BOTTOM_Z + 1))
    solids.append(ledge)
    if p.PEGS_ENABLED:
        solids += [peg(x, y, p.PANEL_BOTTOM_Z) for x, y in p.PEG_XY]
    solids += [slab(r, floor, p.WALL + p.CAP_RAIL_H) for r in p.CAP_RAILS]
    solids += [slab(pad, floor, p.WALL + p.SENSOR_PAD_H) for pad in (p.SHT41_PAD, p.ENS160_PAD)]
    return solids


def _vent_cutters() -> list[Part]:
    through = 12.0   # long enough to pass through a 4 mm wall at 45 degrees
    cutters = []
    for z in p.VENT_ROWS_Z:
        # every slot slopes down toward the outside, so rain cannot fly straight in
        cutters += [Pos(x, p.VENT_WALL / 2, z) * Rot(45, 0, 0) * Box(p.VENT_SLOT_L, through, p.VENT_SLOT_H)
                    for x in p.VENT_FRONT_X]
        cutters.append(Pos(p.VENT_WALL / 2, p.VENT_END_Y, z) * Rot(0, -45, 0)
                       * Box(through, p.VENT_END_SLOT_L, p.VENT_SLOT_H))
        cutters.append(Pos(p.BODY_X - p.VENT_WALL / 2, p.VENT_END_Y, z) * Rot(0, 45, 0)
                       * Box(through, p.VENT_END_SLOT_L, p.VENT_SLOT_H))
    return cutters


def _cutters() -> list[Part]:
    top = p.BODY_Z
    tie_y, tie_z = p.TIE_ANCHOR_YZ
    cutters = _vent_cutters()
    cutters += [
        Pos(-1, p.SMA_Y, p.SMA_Z) * Rot(0, 90, 0) * sma_cutter(p.WALL + 2),
        slab(p.WIRE_NOTCH_RECT, top - p.WIRE_NOTCH_DEPTH, top + 1),
        slab(p.DIVIDER_NOTCH, p.WALL + p.DIVIDER_H - 6.0, p.WALL + p.DIVIDER_H + 1),
        slab(Rect(p.CAP_DIVIDER.x0 - 1, tie_y - 1.5, p.CAP_DIVIDER.x1 + 1, tie_y + 1.5), tie_z - 0.75, tie_z + 0.75),
    ]
    cutters += [rod(x, y, p.DRAIN_D, -1, p.WALL + 1) for x, y in p.DRAIN_XY]
    cutters += [rod(x, y, p.INSERT_D, top - p.INSERT_DEPTH, top + 1) for x, y in p.INSERT_XY]
    cutters += [slab(s, -1, p.WALL + 1) for s in p.EAR_SLOTS]
    return cutters


def build_body() -> Part:
    shell = slab(Rect(0.0, 0.0, p.BODY_X, p.BODY_Y), 0, p.BODY_Z)
    hollow = shell.cut(slab(p.CAVITY, p.WALL, p.BODY_Z + 1))
    return hollow.fuse(*_additions()).cut(*_cutters())
