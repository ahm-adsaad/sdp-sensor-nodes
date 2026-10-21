"""The panel wedge: a plate tilted at PANEL_ANGLE carrying the MP3-37 inside a raised rim,
on two trapezoid cheeks and a front wall with diamond air openings, with four screw feet.

Built in its own frame (front-left foot corner at the origin, on the lid's top face) and
then moved to WEDGE_ORIGIN on the lid. Printed feet down: the plate's underside is a
45-degree overhang and everything else is vertical or on the bed.
"""
from __future__ import annotations

import math

from build123d import Align, Box, Cone, Cylinder, Part, Plane, Polygon, Pos, Rot, extrude

import params as p
from shapes import CENTRE_BASE, EPS, MIN

SINK = 0.2   # how far the cheeks and front wall reach into the plate so they fuse


def _plate() -> Part:
    """The sloped plate with its rim and lead slots, in the wedge frame."""
    plate = Box(p.PLATE_L, p.PLATE_W, p.PLATE_T, align=MIN)
    win_l, win_w = p.PV_L + 2 * p.PV_CLR, p.PV_W + 2 * p.PV_CLR
    cx, cy = p.PLATE_L / 2, p.PLATE_W / 2
    rim = Pos(cx, cy, p.PLATE_T - EPS) * Box(win_l + 2 * p.RIM_W, win_w + 2 * p.RIM_W, p.RIM_H + EPS, align=CENTRE_BASE)
    rim = rim.cut(Pos(cx, cy, p.PLATE_T - 1) * Box(win_l, win_w, p.RIM_H + 3, align=CENTRE_BASE))
    # open the rim along the low edge, leaving 8 mm stubs at the corners, so water runs off the panel
    low_edge = Pos(cx, cy - win_w / 2 - p.RIM_W, p.PLATE_T - 1) * Box(win_l - 16.0, 2 * p.RIM_W + 0.2, p.RIM_H + 3, align=CENTRE_BASE)
    rim = rim.cut(low_edge)
    slot_w, slot_l = p.PV_SLOT
    slots = [Pos(x, cy, -1) * Box(slot_w, slot_l, p.PLATE_T + p.RIM_H + 2, align=CENTRE_BASE)
             for x in (cx - (p.PV_L / 2 - 1.0 - slot_w / 2), cx + (p.PV_L / 2 - 1.0 - slot_w / 2))]
    plate = plate.fuse(rim).cut(*slots)
    return Pos(0, 0, p.FRONT_LIFT) * Rot(p.PANEL_ANGLE, 0, 0) * plate


def _cheeks() -> list[Part]:
    top_back = p.FRONT_LIFT + p.WEDGE_RISE + SINK
    profile = Polygon((0, 0), (p.WEDGE_SPAN_Y, 0), (p.WEDGE_SPAN_Y, top_back), (0, p.FRONT_LIFT + SINK), align=None)
    left = extrude(Plane.YZ * profile, amount=p.CHEEK_T)
    right = Pos(p.PLATE_L - p.CHEEK_T, 0, 0) * extrude(Plane.YZ * profile, amount=p.CHEEK_T)
    return [left, right]


def _front_wall() -> Part:
    a = math.radians(p.PANEL_ANGLE)
    wall = Box(p.PLATE_L, p.CHEEK_T, p.FRONT_LIFT + p.PLATE_T * math.cos(a) + SINK, align=MIN)
    n = int((p.PLATE_L - 2 * p.CHEEK_T - p.DIAMOND) // p.DIAMOND_PITCH)
    start = p.PLATE_L / 2 - (n - 1) * p.DIAMOND_PITCH / 2
    side = p.DIAMOND / math.sqrt(2)
    diamonds = [Pos(start + i * p.DIAMOND_PITCH, -1, p.FRONT_LIFT / 2) * Rot(0, 45, 0)
                * Box(side, p.CHEEK_T + 2, side, align=(Align.CENTER, Align.MIN, Align.CENTER))
                for i in range(n)]
    return wall.cut(*diamonds)


def _feet() -> list[Part]:
    feet = []
    for x0 in (p.CHEEK_T - EPS, p.PLATE_L - p.CHEEK_T - p.FOOT_L + EPS):
        for y0 in (0.0, p.WEDGE_SPAN_Y - p.FOOT_W):
            feet.append(Pos(x0, y0, 0) * Box(p.FOOT_L, p.FOOT_W, p.FOOT_T, align=MIN))
    return feet


def _screw_cutters() -> list[Part]:
    csk_depth = (p.CSK_D - p.SCREW_D) / 2
    cutters = []
    for x in (p.CHEEK_T + p.FOOT_L / 2, p.PLATE_L - p.CHEEK_T - p.FOOT_L / 2):
        for y in (p.FOOT_W / 2, p.WEDGE_SPAN_Y - p.FOOT_W / 2):
            cutters.append(Pos(x, y, -1) * Cylinder(p.SCREW_D / 2, p.FOOT_T + 2, align=CENTRE_BASE))
            cutters.append(Pos(x, y, p.FOOT_T - csk_depth) * Cone(p.SCREW_D / 2, p.CSK_D / 2, csk_depth + EPS, align=CENTRE_BASE))
    return cutters


def build_wedge() -> Part:
    """The wedge in the body frame, feet on the lid's top face."""
    wedge = _plate().fuse(*_cheeks(), _front_wall(), *_feet()).cut(*_screw_cutters())
    x0, y0 = p.WEDGE_ORIGIN
    return Pos(x0, y0, p.LID_Z1) * wedge
