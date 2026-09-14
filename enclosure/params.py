"""Every enclosure dimension in millimetres, plus the 2D layout derived from them.

Frame: X runs left to right, Y front to back, Z up, with the lid facing the sky.
Origin: the outer front-left bottom corner of the body walls. Corner columns
and mounting ears stick out past it.

There are no CAD imports here, so the layout rules test in milliseconds.
Values marked "measured" are the ones the fit coupon is meant to correct.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    """Axis-aligned rectangle in the XY plane."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def d(self) -> float:
        return self.y1 - self.y0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    def inset(self, m: float) -> "Rect":
        """Shrink by m on every side. A negative m grows the rectangle."""
        return Rect(self.x0 + m, self.y0 + m, self.x1 - m, self.y1 - m)

    def contains(self, other: "Rect", tol: float = 1e-6) -> bool:
        return (other.x0 >= self.x0 - tol and other.y0 >= self.y0 - tol
                and other.x1 <= self.x1 + tol and other.y1 <= self.y1 + tol)

    def contains_point(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    @staticmethod
    def centred(cx: float, cy: float, w: float, d: float) -> "Rect":
        return Rect(cx - w / 2, cy - d / 2, cx + w / 2, cy + d / 2)


# ---- print and fit -----------------------------------------------------------
WALL = 2.4          # outer walls and floor
VENT_WALL = 4.0     # sensor bay walls that carry vent slots, thickened inward
DIVIDER = 2.0       # internal walls
CLEARANCE = 0.3     # per side, for parts dropped into pockets

# ---- PCB panel with breakaway rails (measured from the board photo) ----------
PANEL_X, PANEL_Y, PANEL_T = 72.0, 71.4, 1.6
RAIL_LEFT, RAIL_RIGHT = 14.2, 13.9
RAIL_TOP, RAIL_BOTTOM = 6.2, 6.1     # "top" is the edge nearest U5 and J2; it faces the back wall
BOARD_X, BOARD_Y = 43.94, 59.05      # EasyEDA outline, exact
# Tooling hole centres in panel coordinates: x from the panel's left edge,
# y from its top edge.
TOOLING_HOLES = ((4.8, 3.2), (61.5, 3.1), (5.3, 68.4), (66.8, 68.1))
TOOLING_HOLE_D = 2.0

PANEL_STANDOFF = 4.0   # floor to panel underside, clears through-hole pins
ABOVE_BOARD = 28.0     # Dupont housings stand about 16.5 mm, plus wire bend room
LEDGE_W = 5.0
PEG_D, PEG_H, PEG_CHAMFER = 1.6, 2.0, 0.4
PEGS_ENABLED = True
POST_D = 6.0
POST_PANEL_Y = (26.0, 56.0)  # posts along the side rails, measured from the panel top edge
POST_FOAM = 2.0              # gap above the rail for 3 mm foam tape to compress into

# ---- supercapacitor pack -------------------------------------------------------
CAP_L, CAP_W, CAP_H = 65.0, 38.0, 18.0
CAP_BAY_X = CAP_W + 4.0
CAP_RAIL_W, CAP_RAIL_H, CAP_RAIL_L = 4.0, 3.0, 60.0
DIVIDER_H = 20.0

# ---- sensor bay ------------------------------------------------------------------
SENSOR_BAY_Y = 26.0
SHT41 = (25.0, 17.0)    # breakout size, x by y
ENS160 = (17.0, 18.0)
SENSOR_PAD_H = 3.0
VENT_SLOT_H, VENT_PITCH, VENT_Z0 = 1.6, 5.0, 8.0
VENT_SLOT_L, VENT_SLOT_WEB, VENT_END_SLOT_L = 18.0, 6.0, 16.0
WIRE_NOTCH_W, WIRE_NOTCH_DEPTH = 10.0, 6.0
DRAIN_D = 3.0

# ---- antenna -----------------------------------------------------------------------
SMA_D, SMA_FLAT = 6.5, 6.0
SMA_Y, SMA_Z = 42.0, 20.0

# ---- lid, fasteners, mounting --------------------------------------------------------
LID_T = 3.0
SKIRT_T, SKIRT_DROP, SKIRT_GAP = 1.6, 4.0, 0.4
COLUMN = 9.0                        # square corner column; WALL of it overlaps the wall
INSERT_D, INSERT_DEPTH = 4.0, 6.5   # M3 heat-set insert; set INSERT_D = 2.6 for self-tapping screws
SCREW_D, CSK_D = 3.4, 6.6
EAR_OUT, EAR_W = 12.0, 20.0
EAR_SLOT_L, EAR_SLOT_W = 8.0, 4.5

# ---- solar panels (PowerFilm MP3-37) ----------------------------------------------------
PV_L, PV_W = 114.0, 36.5
PV_RECESS_CLR, PV_RECESS_DEPTH = 0.3, 0.4
PV_GAP, PV_BACK_MARGIN, PV_MIN_EDGE = 3.0, 3.0, 1.0
PV_SLOT_W, PV_SLOT_L = 1.5, 8.0

# ================= derived: nothing below here is a free parameter =================

POCKET_X = PANEL_X + 2 * CLEARANCE
POCKET_Y = PANEL_Y + 2 * CLEARANCE
INNER_X = POCKET_X + DIVIDER + CAP_BAY_X
INNER_Y = SENSOR_BAY_Y + DIVIDER + POCKET_Y
INNER_Z = PANEL_STANDOFF + PANEL_T + ABOVE_BOARD
BODY_X = INNER_X + 2 * WALL
BODY_Y = INNER_Y + 2 * WALL
BODY_Z = WALL + INNER_Z
PANEL_BOTTOM_Z = WALL + PANEL_STANDOFF
PANEL_TOP_Z = PANEL_BOTTOM_Z + PANEL_T
POST_TIP_Z = PANEL_TOP_Z + POST_FOAM

CAVITY = Rect(WALL, WALL, BODY_X - WALL, BODY_Y - WALL)
SENSOR_BAY = Rect(WALL, WALL, BODY_X - WALL, WALL + SENSOR_BAY_Y)
SENSOR_BAY_INNER = Rect(VENT_WALL, VENT_WALL, BODY_X - VENT_WALL, SENSOR_BAY.y1)
SENSOR_WALL = Rect(WALL, SENSOR_BAY.y1, BODY_X - WALL, SENSOR_BAY.y1 + DIVIDER)
ELECTRONICS = Rect(WALL, SENSOR_WALL.y1, BODY_X - WALL, BODY_Y - WALL)
POCKET = Rect(WALL, SENSOR_WALL.y1, WALL + POCKET_X, SENSOR_WALL.y1 + POCKET_Y)
CAP_DIVIDER = Rect(POCKET.x1, POCKET.y0, POCKET.x1 + DIVIDER, POCKET.y1)
CAP_BAY = Rect(CAP_DIVIDER.x1, POCKET.y0, BODY_X - WALL, POCKET.y1)

# ---- PCB panel and the component side of the board ----
PANEL = POCKET.inset(CLEARANCE)
BOARD = Rect(PANEL.x0 + RAIL_LEFT, PANEL.y1 - RAIL_TOP - BOARD_Y,
             PANEL.x0 + RAIL_LEFT + BOARD_X, PANEL.y1 - RAIL_TOP)


def panel_to_body(px: float, py: float) -> tuple[float, float]:
    """Panel coordinates (x from its left edge, y from its top edge) to body XY."""
    return PANEL.x0 + px, PANEL.y1 - py


def eda_to_body(ex: float, ey: float) -> tuple[float, float]:
    """EasyEDA board coordinates (mm from the outline's top-left corner) to body XY."""
    return panel_to_body(RAIL_LEFT + ex, RAIL_TOP + ey)


PEG_XY = tuple(panel_to_body(x, y) for x, y in TOOLING_HOLES)
LEDGE_OUTER = POCKET
LEDGE_INNER = POCKET.inset(CLEARANCE + LEDGE_W)
POST_XY = tuple(panel_to_body(px, py)
                for px in (RAIL_LEFT / 2, PANEL_X - RAIL_RIGHT / 2)
                for py in POST_PANEL_Y)
J1_XY = eda_to_body(37.34, 37.97)
JP1_XY = eda_to_body(6.99, 56.52)

# ---- supercapacitor bay ----
CAP = Rect.centred(CAP_BAY.cx, CAP_BAY.cy, CAP_W, CAP_L)
CAP_RAILS = (
    Rect.centred(CAP.x0 + 2 + CAP_RAIL_W / 2, CAP.cy, CAP_RAIL_W, CAP_RAIL_L),
    Rect.centred(CAP.x1 - 2 - CAP_RAIL_W / 2, CAP.cy, CAP_RAIL_W, CAP_RAIL_L),
)
DIVIDER_NOTCH = Rect(CAP_DIVIDER.x0 - 1, POCKET.y1 - 10, CAP_DIVIDER.x1 + 1, POCKET.y1 - 2)
TIE_ANCHOR_YZ = (POCKET.y1 - 16, WALL + DIVIDER_H - 4)   # 3 x 1.5 mm slot through the divider

# ---- sensor bay ----
SHT41_PAD = Rect.centred(SENSOR_BAY_INNER.x0 + 2 + (SHT41[0] - 2) / 2, SENSOR_BAY_INNER.cy,
                         SHT41[0] - 2, SHT41[1] - 2)
ENS160_PAD = Rect.centred(SENSOR_BAY_INNER.x1 - 2 - (ENS160[0] - 2) / 2, SENSOR_BAY_INNER.cy,
                          ENS160[0] - 2, ENS160[1] - 2)
DRAIN_XY = ((BODY_X / 2 - 20, VENT_WALL + 4), (BODY_X / 2 + 20, VENT_WALL + 4))
WIRE_NOTCH_RECT = Rect.centred(J1_XY[0], SENSOR_WALL.cy, WIRE_NOTCH_W, DIVIDER + 2)


def _vent_rows() -> tuple[float, ...]:
    # A 45-degree slot centred in the wall reaches this far above its centre at the wall face.
    reach = VENT_SLOT_H / 2 / math.cos(math.radians(45)) + VENT_WALL / 2 + 1.0
    rows, z = [], VENT_Z0
    while z + reach <= BODY_Z - 1.0:
        rows.append(z)
        z += VENT_PITCH
    return tuple(rows)


def _vent_front_x() -> tuple[float, ...]:
    usable = SENSOR_BAY_INNER.w - 2 * VENT_SLOT_WEB
    n = int((usable + VENT_SLOT_WEB) // (VENT_SLOT_L + VENT_SLOT_WEB))
    span = n * VENT_SLOT_L + (n - 1) * VENT_SLOT_WEB
    first = SENSOR_BAY_INNER.cx - span / 2 + VENT_SLOT_L / 2
    return tuple(first + i * (VENT_SLOT_L + VENT_SLOT_WEB) for i in range(n))


VENT_ROWS_Z = _vent_rows()
VENT_FRONT_X = _vent_front_x()
VENT_END_Y = SENSOR_BAY_INNER.cy

# ---- corner columns, lid, ears ----
COLUMN_OUT = COLUMN - WALL
_CORNERS = ((0.0, 0.0, -1, -1), (BODY_X, 0.0, 1, -1), (0.0, BODY_Y, -1, 1), (BODY_X, BODY_Y, 1, 1))


def _column(cx: float, cy: float, sx: int, sy: int) -> Rect:
    xa, xb = cx + sx * COLUMN_OUT, cx - sx * WALL
    ya, yb = cy + sy * COLUMN_OUT, cy - sy * WALL
    return Rect(min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb))


COLUMNS = tuple(_column(*c) for c in _CORNERS)
INSERT_XY = tuple((c.cx, c.cy) for c in COLUMNS)
LID = Rect(0.0, 0.0, BODY_X, BODY_Y).inset(-(COLUMN_OUT + SKIRT_GAP + SKIRT_T))
EARS = (
    Rect(-EAR_OUT, BODY_Y / 2 - EAR_W / 2, 0.5, BODY_Y / 2 + EAR_W / 2),
    Rect(BODY_X - 0.5, BODY_Y / 2 - EAR_W / 2, BODY_X + EAR_OUT, BODY_Y / 2 + EAR_W / 2),
)
EAR_SLOTS = (
    Rect.centred(-EAR_OUT / 2, BODY_Y / 2, EAR_SLOT_L, EAR_SLOT_W),
    Rect.centred(BODY_X + EAR_OUT / 2, BODY_Y / 2, EAR_SLOT_L, EAR_SLOT_W),
)


# ---- solar panel recesses ----
def pv_recesses(count: int) -> tuple[Rect, ...]:
    """Panel recesses on the lid top, packed from the back edge toward the front."""
    length, width = PV_L + 2 * PV_RECESS_CLR, PV_W + 2 * PV_RECESS_CLR
    out, y1 = [], LID.y1 - PV_BACK_MARGIN
    for _ in range(count):
        out.append(Rect.centred(LID.cx, y1 - width / 2, length, width))
        y1 -= width + PV_GAP
    return tuple(out)


def pv_slots(recess: Rect) -> tuple[Rect, ...]:
    """Lead slots at both ends of a recess, placed over the electronics bay.

    Returns an empty tuple when the recess does not overlap the electronics bay
    enough to hold a slot, which is the case for a third panel over the sensor bay.
    """
    zone = ELECTRONICS.inset(1.0)
    cy = min(max(recess.cy, zone.y0 + PV_SLOT_L / 2), zone.y1 - PV_SLOT_L / 2)
    if cy - PV_SLOT_L / 2 < recess.y0 or cy + PV_SLOT_L / 2 > recess.y1:
        return ()
    y0, y1 = cy - PV_SLOT_L / 2, cy + PV_SLOT_L / 2
    left = Rect(recess.x0 + 1.0, y0, recess.x0 + 1.0 + PV_SLOT_W, y1)
    right = Rect(recess.x1 - 1.0 - PV_SLOT_W, y0, recess.x1 - 1.0, y1)
    return left, right


def max_panels() -> int:
    """How many recesses fit before one comes within PV_MIN_EDGE of the lid's front edge."""
    n = 0
    while pv_recesses(n + 1)[-1].y0 >= LID.y0 + PV_MIN_EDGE:
        n += 1
    return n
