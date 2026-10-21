"""The lid: eaved plate with a drip skirt and a labyrinth skirt, posts that hold the board down,
bosses for the panel wedge, countersunk screw holes and the solar lead hole."""
from __future__ import annotations

from build123d import Cone, Part, Pos

import params as p
from shapes import CENTRE_BASE, EPS, rod, slab

Rect = p.Rect


def _ring(r: Rect, z0: float, z1: float) -> Part:
    return slab(r, z0, z1).cut(slab(r.inset(p.SKIRT_T), z0 - 1, z1 + 1))


def _labyrinth(z0: float, z1: float) -> list[Part]:
    """Front leg and two end legs; the drip skirt stands in for the back leg, where the eave is too short."""
    lab = p.LABYRINTH
    return [
        slab(Rect(lab.x0, lab.y0, lab.x1, lab.y0 + p.SKIRT_T), z0, z1),
        slab(Rect(lab.x0, lab.y0, lab.x0 + p.SKIRT_T, lab.y1 + EPS), z0, z1),
        slab(Rect(lab.x1 - p.SKIRT_T, lab.y0, lab.x1, lab.y1 + EPS), z0, z1),
    ]


def build_lid() -> Part:
    """Lid in the body frame, underside on LID_Z0."""
    bottom, top = p.LID_Z0, p.LID_Z1
    plate = slab(p.LID, bottom, top)
    skirt_z0, skirt_z1 = bottom - p.SKIRT_DROP, bottom + EPS
    drip = _ring(p.LID, skirt_z0, skirt_z1)
    posts = [rod(x, y, d, tip, bottom + EPS) for x, y, d, tip in p.POSTS]
    bosses = [rod(x, y, p.BOSS_D, bottom - p.BOSS_H, bottom + EPS) for x, y in p.BOSS_XY]
    lid = plate.fuse(drip, *_labyrinth(skirt_z0, skirt_z1), *posts, *bosses)

    csk_depth = (p.CSK_D - p.SCREW_D) / 2     # 90 degree countersink
    cutters = []
    for x, y in p.INSERT_XY:
        cutters.append(rod(x, y, p.SCREW_D, bottom - 1, top + 1))
        cutters.append(Pos(x, y, top - csk_depth) * Cone(p.SCREW_D / 2, p.CSK_D / 2, csk_depth + EPS, align=CENTRE_BASE))
    cutters += [rod(x, y, p.INSERT_D, top - p.INSERT_DEPTH, top + 1) for x, y in p.BOSS_XY]
    cutters.append(rod(*p.PV_HOLE_XY, p.PV_HOLE_D, bottom - p.BOSS_H - 1, top + 1))
    return lid.cut(*cutters)
