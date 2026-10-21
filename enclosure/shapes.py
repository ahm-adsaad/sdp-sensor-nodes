"""Solid helpers, reference models of the parts inside the case, and the print-orientation overhang check."""
from __future__ import annotations

import math

from build123d import Align, Box, Cylinder, Location, Part, Pos, Rot

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


def sma_cutter(length: float) -> Part:
    """Double-D cutter for an SMA bulkhead jack: axis +Z, base at z=0, centred on the origin."""
    round_hole = Cylinder(p.SMA_D / 2, length, align=CENTRE_BASE)
    flats = Box(p.SMA_D + 1, p.SMA_FLAT, length, align=CENTRE_BASE)
    return round_hole & flats


def vee_cutter(x: float, y: float, z_bottom: float, half_diag: float, thickness: float) -> Part:
    """A square prism along Y standing on one corner: a 90 degree V whose bottom vertex is at z_bottom.

    Both V faces slope at 45 degrees, so the cut prints without support.
    """
    side = half_diag * math.sqrt(2)
    return (Pos(x, y, z_bottom + half_diag) * Rot(0, 45, 0)
            * Box(side, thickness, side, align=(Align.CENTER, Align.CENTER, Align.CENTER)))


# ---- reference solids, in the body frame ----

def pcb_board() -> Part:
    """The bare rev-2 board resting on its ledges."""
    return slab(p.BOARD, p.BOARD_BOTTOM_Z, p.BOARD_TOP_Z)


def board_keepout() -> Part:
    """Space above the populated board that the case and lid must leave empty.

    The interior is kept clear to the terminal height, the terminals themselves to
    their own height, the sensor headers to the Dupont housings plus bend room, and
    the LoRa module and U.FL to theirs. The bare strip along the bottom edge is left
    out so the hold-down post can land on it.
    """
    z = p.BOARD_TOP_Z
    zones = [slab(p.INTERIOR_ZONE, z, z + p.TERMINAL_H)]
    zones += [slab(t, z, z + p.TERMINAL_H) for t in p.TERMINAL_ZONES]
    zones += [slab(j, z, z + p.HEADER_H) for j in (p.J3_ZONE, p.J4_ZONE)]
    zones.append(slab(p.LORA_ZONE, z, z + 3.0))
    zones.append(slab(p.UFL_ZONE, z, z + 5.0))
    return zones[0].fuse(*zones[1:])


def cell() -> Part:
    """The HS1040 at Eaton's maximum size, lying along Y on the V-blocks."""
    return Pos(p.CELL_X, p.CELL_Y0, p.CELL_AXIS_Z) * Rot(-90, 0, 0) * Cylinder(p.CELL_R, p.CELL_L, align=CENTRE_BASE)


def cell_leads() -> Part:
    """Clearance for the cell's leads on their way from its back end over the fence to U11."""
    return slab(p.Rect(p.BOARD.x1, p.CELL_Y1 - 1.0, p.CELL_X, p.CELL_Y1 + 2.5), p.CELL_AXIS_Z + 1.0, p.CELL_AXIS_Z + 5.0)


def sensor_boards() -> Part:
    """The SHT41 and ENS160 breakouts lying on their pads on foam tape."""
    z0, z1 = p.SENSOR_BOARD_Z, p.SENSOR_BOARD_Z + p.SENSOR_BOARD_T
    return slab(p.SHT41_BOARD, z0, z1) + slab(p.ENS160_BOARD, z0, z1)


def sensor_keepout() -> Part:
    """The breakouts plus the Dupont housings standing on their headers."""
    z0, z1 = p.SENSOR_BOARD_Z, p.SENSOR_BOARD_Z + p.SENSOR_BOARD_T + p.SENSOR_HOUSING_H
    return slab(p.SHT41_BOARD, z0, z1) + slab(p.ENS160_BOARD, z0, z1)


def plate_frame() -> Location:
    """Frame of the wedge's sloped plate: origin at the underside's front edge on the lid, tilted by PANEL_ANGLE."""
    x0, y0 = p.WEDGE_ORIGIN
    return Pos(x0, y0, p.LID_Z1 + p.FRONT_LIFT) * Rot(p.PANEL_ANGLE, 0, 0)


def solar_panel() -> Part:
    """The MP3-37 lying inside the rim on the wedge's plate."""
    return plate_frame() * Pos(p.PLATE_L / 2, p.PLATE_W / 2, p.PLATE_T) * Box(p.PV_L, p.PV_W, p.PV_T, align=CENTRE_BASE)


def overlap(a: Part, b: Part) -> float:
    """Volume two solids share. Zero when they are apart or only touch."""
    common = a & b
    return 0.0 if common is None else common.volume


def unsupported_faces(part: Part, bed_z: float = 0.0, max_bridge: float = 10.0,
                      min_slope_deg: float = 45.0) -> list[tuple[float, float, float, float, float]]:
    """Faces that would need support when printed with +Z up.

    A face is reported when it faces down more steeply than min_slope_deg allows,
    is not on the bed, and spans more than max_bridge in both horizontal directions.
    Each entry is (nz, size_x, size_y, z_min, area).
    """
    limit = -math.cos(math.radians(90 - min_slope_deg)) - 2e-3
    bad = []
    for f in part.faces():
        nz = f.normal_at().Z
        if nz >= limit:
            continue
        bb = f.bounding_box()
        if bb.max.Z <= bed_z + 1e-3:
            continue
        if min(bb.size.X, bb.size.Y) <= max_bridge:
            continue
        bad.append((round(nz, 3), round(bb.size.X, 1), round(bb.size.Y, 1), round(bb.min.Z, 1), round(f.area, 1)))
    return bad
