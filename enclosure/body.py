"""The body: louvred sensor cavity with a gable ceiling, the electronics cavity above it with
ledges, fences and V-blocks, corner columns, ears, and every hole and notch."""
from __future__ import annotations

from build123d import Box, Cylinder, Part, Plane, Polygon, Pos, Rot, extrude

import params as p
from shapes import CENTRE_BASE, EPS, rod, slab, sma_cutter, vee_cutter

Rect = p.Rect
VEE_SINK = 0.3        # the V's bottom vertex sits this far below the floor so the cell never binds
THROUGH = 12.0        # louvre cutter length, enough to pass a 4 mm wall at 45 degrees


def _cavities() -> list[Part]:
    band = slab(p.SENSOR_INNER, p.Z_LOWER_FLOOR, p.Z_BAND_TOP + EPS)
    y0, y1 = p.SENSOR_INNER.y0, p.SENSOR_INNER.y1
    profile = Polygon((y0, p.Z_BAND_TOP - EPS), (y1, p.Z_BAND_TOP - EPS), (p.SENSOR_INNER.cy, p.Z_RIDGE), align=None)
    gable = extrude(Plane.YZ.offset(p.SENSOR_INNER.x0) * profile, amount=p.SENSOR_INNER.w)
    upper = slab(p.CAVITY, p.Z_FLOOR, p.BODY_Z + 1)
    return [band, gable, upper]


def _additions() -> list[Part]:
    floor = p.Z_FLOOR - EPS
    solids = [slab(c, 0, p.BODY_Z) for c in p.COLUMNS]
    solids += [slab(e, 0, p.EAR_T) for e in p.EARS]
    solids += [slab(f.inset(-EPS), floor, p.Z_FLOOR + p.FENCE_H) for f in (p.FRONT_FENCE, p.TERMINAL_FENCE)]
    solids += [slab(ledge.inset(-EPS), floor, p.BOARD_BOTTOM_Z) for ledge in p.LEDGES]
    solids += [slab(v.inset(-EPS), floor, p.CELL_AXIS_Z) for v in p.VBLOCKS]
    solids += [slab(pad, p.Z_LOWER_FLOOR - EPS, p.Z_LOWER_FLOOR + p.SENSOR_PAD_H) for pad in (p.SHT41_PAD, p.ENS160_PAD)]
    return solids


def _louvre_cutters() -> list[Part]:
    # every slot slopes down toward the outside, so rain cannot fly straight in
    half = p.LOUVRE_WALL / 2
    cutters = []
    for z in p.LOUVRE_ROWS_Z:
        for x in p.LOUVRE_LONG_X:
            cutters.append(Pos(x, half, z) * Rot(45, 0, 0) * Box(p.SLOT_L_LONG, THROUGH, p.SLOT_H))
            cutters.append(Pos(x, p.BODY_Y - half, z) * Rot(-45, 0, 0) * Box(p.SLOT_L_LONG, THROUGH, p.SLOT_H))
        for y in p.LOUVRE_END_Y:
            cutters.append(Pos(half, y, z) * Rot(0, -45, 0) * Box(THROUGH, p.SLOT_L_END, p.SLOT_H))
            cutters.append(Pos(p.BODY_X - half, y, z) * Rot(0, 45, 0) * Box(THROUGH, p.SLOT_L_END, p.SLOT_H))
    return cutters


def _notch_cutters() -> list[Part]:
    z0, z1 = p.BODY_Z - p.NOTCH_D, p.BODY_Z + 1
    cutters = []
    for wall, c in p.NOTCHES:
        if wall == "front":
            r = Rect(c - p.NOTCH_W / 2, -1, c + p.NOTCH_W / 2, p.WALL + 1)
        elif wall == "back":
            r = Rect(c - p.NOTCH_W / 2, p.BODY_Y - p.WALL - 1, c + p.NOTCH_W / 2, p.BODY_Y + 1)
        elif wall == "left":
            r = Rect(-1, c - p.NOTCH_W / 2, p.WALL + 1, c + p.NOTCH_W / 2)
        else:
            r = Rect(p.BODY_X - p.WALL - 1, c - p.NOTCH_W / 2, p.BODY_X + 1, c + p.NOTCH_W / 2)
        cutters.append(slab(r, z0, z1))
    return cutters


def _x_rod(x0: float, x1: float, y: float, z: float, d: float) -> Part:
    """Cylinder along X from x0 to x1 centred on (y, z)."""
    return Pos(x0, y, z) * Rot(0, 90, 0) * Cylinder(d / 2, x1 - x0, align=CENTRE_BASE)


def _cutters() -> list[Part]:
    cutters = _louvre_cutters() + _notch_cutters()
    cutters.append(Pos(p.SMA_X, p.BODY_Y - p.WALL - 1, p.SMA_Z) * Rot(-90, 0, 0) * sma_cutter(p.WALL + 2))
    cutters.append(slab(p.CHANNEL_SLOT_RECT, p.Z_BAND_TOP - 1, p.Z_FLOOR + 1))
    cutters += [rod(x, y, p.CHANNEL_CHIMNEY_D, p.Z_BAND_TOP - 1, p.Z_FLOOR + 1) for x, y in p.CHANNEL_CHIMNEY_XY]
    cutters += [rod(x, y, p.DRAIN_D, p.Z_BAND_TOP - 1, p.Z_FLOOR + 1) for x, y in p.CHANNEL_DRAIN_XY]
    cutters += [rod(x, y, p.CHIMNEY_D, p.Z_RIDGE - 2, p.Z_FLOOR + 1) for x, y in p.CHIMNEY_XY]
    for y, z in p.SENSOR_DRAIN_YZ:
        cutters.append(_x_rod(-1, p.LOUVRE_WALL + 1, y, z, p.DRAIN_D))
        cutters.append(_x_rod(p.BODY_X - p.LOUVRE_WALL - 1, p.BODY_X + 1, y, z, p.DRAIN_D))
    cutters += [vee_cutter(p.CELL_X, v.cy, p.Z_FLOOR - VEE_SINK, 12.0, p.VBLOCK_T + 2) for v in p.VBLOCKS]
    cutters += [rod(x, y, p.INSERT_D, p.BODY_Z - p.INSERT_DEPTH, p.BODY_Z + 1) for x, y in p.INSERT_XY]
    cutters += [slab(s, -1, p.EAR_T + 1) for s in p.EAR_SLOTS]
    return cutters


def build_body() -> Part:
    shell = slab(Rect(0.0, 0.0, p.BODY_X, p.BODY_Y), 0, p.BODY_Z)
    hollow = shell.cut(*_cavities())
    return hollow.fuse(*_additions()).cut(*_cutters())
