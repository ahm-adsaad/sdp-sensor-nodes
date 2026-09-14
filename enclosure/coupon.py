"""Fit coupon: the panel ledge and pegs inside a low fence, an SMA test hole and one insert column.

Prints flat in about 20 minutes. Uses the same parameters as the body, so a
fix found on the coupon carries straight into the case.
"""
from __future__ import annotations

from build123d import Part, Pos

import params as p
from shapes import EPS, peg, rod, slab, sma_cutter

RING_T = 2.0          # ledge ring thickness
FENCE_T = 1.6
FENCE_ABOVE = 1.0     # fence top sits this far above the panel's top face
COLUMN_H = 8.0


def build_coupon() -> Part:
    ring = slab(p.LEDGE_OUTER.inset(-EPS), 0, RING_T).cut(slab(p.LEDGE_INNER, -1, RING_T + 1))
    fence_top = RING_T + p.PANEL_T + FENCE_ABOVE
    fence = slab(p.POCKET.inset(-FENCE_T), 0, fence_top).cut(slab(p.POCKET, -1, fence_top + 1))

    tab = p.Rect(p.POCKET.x0 - FENCE_T - 18.0, p.SMA_Y - 9.0, p.POCKET.x0 - FENCE_T + 0.6, p.SMA_Y + 9.0)
    column = p.Rect.centred(p.POCKET.x1 + FENCE_T - 0.6 + p.COLUMN / 2, p.POCKET.cy, p.COLUMN, p.COLUMN)

    additions = [fence, slab(tab, 0, p.WALL), slab(column, 0, COLUMN_H)]
    if p.PEGS_ENABLED:
        additions += [peg(x, y, RING_T) for x, y in p.PEG_XY]
    coupon = ring.fuse(*additions)

    cuts = [
        Pos(tab.x0 + 9.0, tab.cy, -1) * sma_cutter(p.WALL + 2),
        rod(column.cx, column.cy, p.INSERT_D, COLUMN_H - p.INSERT_DEPTH, COLUMN_H + 1),
    ]
    return coupon.cut(*cuts)
