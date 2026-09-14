"""The lid: plate with a drip skirt, solar panel recesses and lead slots,
countersunk screw holes, and posts that clamp the PCB panel's side rails."""
from __future__ import annotations

from build123d import Cone, Part, Pos

import params as p
from shapes import CENTRE_BASE, EPS, rod, slab


def build_lid(panel_count: int = 2) -> Part:
    """Lid in the body frame, underside on z = BODY_Z, with recesses for panel_count panels."""
    if not 1 <= panel_count <= p.max_panels():
        raise ValueError(f"panel_count must be between 1 and {p.max_panels()}, got {panel_count}")
    bottom, top = p.BODY_Z, p.BODY_Z + p.LID_T

    plate = slab(p.LID, bottom, top)
    skirt = slab(p.LID, bottom - p.SKIRT_DROP, bottom + EPS).cut(
        slab(p.LID.inset(p.SKIRT_T), bottom - p.SKIRT_DROP - 1, bottom + 1))
    posts = [rod(x, y, p.POST_D, p.POST_TIP_Z, bottom + EPS) for x, y in p.POST_XY]
    lid = plate.fuse(skirt, *posts)

    csk_depth = (p.CSK_D - p.SCREW_D) / 2     # 90 degree countersink
    cutters = []
    for x, y in p.INSERT_XY:
        cutters.append(rod(x, y, p.SCREW_D, bottom - 1, top + 1))
        cutters.append(Pos(x, y, top - csk_depth)
                       * Cone(p.SCREW_D / 2, p.CSK_D / 2, csk_depth + EPS, align=CENTRE_BASE))
    for recess in p.pv_recesses(panel_count):
        cutters.append(slab(recess, top - p.PV_RECESS_DEPTH, top + 1))
        cutters += [slab(s, bottom - 1, top + 1) for s in p.pv_slots(recess)]
    return lid.cut(*cutters)
