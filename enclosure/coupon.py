"""Fit coupon: two pocket fences (ruler outline and export outline) with their ledges,
an SMA test hole, one insert column and the cell's pair of V-blocks.

Prints flat in about 25 minutes. Uses the same parameters as the body, so a fix
found on the coupon carries straight into the case.
"""
from __future__ import annotations

from build123d import Part, Pos

import params as p
from shapes import EPS, rod, slab, sma_cutter, vee_cutter

RING_T = 2.0          # ledge thickness
FENCE_T = 1.6
FENCE_ABOVE = 1.0     # fence top sits this far above the board's top face
COLUMN_H = 8.0
SIDE_X = 62.0         # the SMA tab, insert column and V-blocks start here
VEE_PLATE_T = 2.0
BASE_T = 1.2          # plate joining every feature into one print; open under the pockets


def _pocket(fence: p.Rect, ledges: tuple[p.Rect, ...]) -> list[Part]:
    fence_top = RING_T + p.BOARD_T + FENCE_ABOVE
    wall = slab(fence.inset(-FENCE_T), 0, fence_top).cut(slab(fence, -1, fence_top + 1))
    return [wall] + [slab(ledge.inset(-EPS), 0, RING_T) for ledge in ledges]


def build_coupon() -> Part:
    ruler, export = p.coupon_fences()
    tab = p.Rect(SIDE_X, 0.0, SIDE_X + 18.0, 18.0)
    column = p.Rect(SIDE_X, 22.0, SIDE_X + p.COLUMN, 22.0 + p.COLUMN)
    vee_plate = p.Rect(SIDE_X, 36.0, SIDE_X + p.WIRE_BAY_W, 36.0 + 42.0)
    vee_y = tuple(vee_plate.y0 + 1.0 + dy for dy in (8.0, 34.0))
    overall = p.Rect(-FENCE_T, -FENCE_T, vee_plate.x1, max(export[0].y1 + FENCE_T, vee_plate.y1))
    base = slab(overall, 0, BASE_T).cut(slab(ruler[0], -1, BASE_T + 1), slab(export[0], -1, BASE_T + 1))

    solids = [base] + _pocket(*ruler) + _pocket(*export)
    solids += [slab(tab, 0, p.WALL), slab(column, 0, COLUMN_H), slab(vee_plate, 0, VEE_PLATE_T)]
    vee_top = VEE_PLATE_T + (p.CELL_AXIS_Z - p.Z_FLOOR)
    solids += [slab(p.Rect(vee_plate.x0, y - p.VBLOCK_T / 2, vee_plate.x1, y + p.VBLOCK_T / 2), VEE_PLATE_T - EPS, vee_top)
               for y in vee_y]
    coupon = solids[0].fuse(*solids[1:])

    cuts = [
        Pos(tab.cx, tab.cy, -1) * sma_cutter(p.WALL + 2),
        rod(column.cx, column.cy, p.INSERT_D, COLUMN_H - p.INSERT_DEPTH, COLUMN_H + 1),
    ]
    cuts += [vee_cutter(vee_plate.cx, y, VEE_PLATE_T, 12.0, p.VBLOCK_T + 2) for y in vee_y]
    return coupon.cut(*cuts)
