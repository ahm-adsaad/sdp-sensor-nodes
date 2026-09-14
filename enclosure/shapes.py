"""Solid helpers and reference models of the parts that sit inside the case."""
from __future__ import annotations

from build123d import Align, Box, Cone, Cylinder, Part, Pos

import params as p

EPS = 0.05   # overlap used when fusing touching solids, so booleans never meet face-to-face
MIN = (Align.MIN, Align.MIN, Align.MIN)
CENTRE_BASE = (Align.CENTER, Align.CENTER, Align.MIN)


def slab(r: p.Rect, z0: float, z1: float) -> Part:
    """Box over rectangle r from height z0 to z1."""
    return Pos(r.x0, r.y0, z0) * Box(r.w, r.d, z1 - z0, align=MIN)


def rod(x: float, y: float, d: float, z0: float, z1: float) -> Part:
    """Vertical cylinder of diameter d centred on (x, y) from height z0 to z1."""
    return Pos(x, y, z0) * Cylinder(d / 2, z1 - z0, align=CENTRE_BASE)


def peg(x: float, y: float, z0: float) -> Part:
    """Locating peg standing on height z0 with a chamfered tip; its root sinks 0.2 mm below z0."""
    tip_z = z0 + p.PEG_H - p.PEG_CHAMFER
    shaft = rod(x, y, p.PEG_D, z0 - 0.2, tip_z + EPS)
    tip = Pos(x, y, tip_z) * Cone(p.PEG_D / 2, p.PEG_D / 2 - p.PEG_CHAMFER, p.PEG_CHAMFER,
                                  align=CENTRE_BASE)
    return shaft + tip


def sma_cutter(length: float) -> Part:
    """Double-D cutter for an SMA bulkhead jack: axis +Z, base at z=0, centred on the origin."""
    round_hole = Cylinder(p.SMA_D / 2, length, align=CENTRE_BASE)
    flats = Box(p.SMA_D + 1, p.SMA_FLAT, length, align=CENTRE_BASE)
    return round_hole & flats


def pcb_panel() -> Part:
    """The PCB panel resting on the ledge, with its four tooling holes."""
    panel = slab(p.PANEL, p.PANEL_BOTTOM_Z, p.PANEL_TOP_Z)
    holes = [rod(x, y, p.TOOLING_HOLE_D, p.PANEL_BOTTOM_Z - 1, p.PANEL_TOP_Z + 1) for x, y in p.PEG_XY]
    return panel.cut(*holes)


def board_keepout() -> Part:
    """Space above the populated board, including jumper wire housings, that the case must leave empty."""
    return slab(p.BOARD, p.PANEL_TOP_Z, p.PANEL_TOP_Z + p.ABOVE_BOARD)


def supercap() -> Part:
    """The supercapacitor pack lying on its floor rails."""
    return slab(p.CAP, p.WALL + p.CAP_RAIL_H, p.WALL + p.CAP_RAIL_H + p.CAP_H)


def overlap(a: Part, b: Part) -> float:
    """Volume two solids share. Zero when they are apart or only touch."""
    common = a & b
    return 0.0 if common is None else common.volume
