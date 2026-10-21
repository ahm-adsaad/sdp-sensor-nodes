"""Every enclosure dimension in millimetres, plus the layout derived from them.

Frame: X runs left to right along the solar panel, Y front to back (the front is
the panel's low edge and the sun side), Z up. Origin: the outer front-left bottom
corner of the body walls, at ground level. Corner columns and mounting ears stick
out past it.

The rev-2 board is modelled from the user's ruler (53 x 38 mm). The fabrication
export says 58.0 x 42.4 mm; set ENCLOSURE_BOARD=export in the environment to
regenerate for that outline. Board features are positioned from the nearest
board edge, as read off the export's pad list.

There are no CAD imports here, so the layout rules test in milliseconds.
"""
from __future__ import annotations

import math
import os
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

    def clip(self, other: "Rect") -> "Rect":
        return Rect(max(self.x0, other.x0), max(self.y0, other.y0), min(self.x1, other.x1), min(self.y1, other.y1))

    @staticmethod
    def centred(cx: float, cy: float, w: float, d: float) -> "Rect":
        return Rect(cx - w / 2, cy - d / 2, cx + w / 2, cy + d / 2)


# ---- print and fit -----------------------------------------------------------
WALL = 2.4            # outer walls and floors
LOUVRE_WALL = 4.0     # sensor cavity walls that carry the 45 degree slots, thickened inward
DIVIDER = 2.0         # fences inside the cavity
CLEARANCE = 0.3       # per side, for parts dropped into pockets

# ---- rev-2 board -------------------------------------------------------------
BOARD_X_EXPORT, BOARD_Y_EXPORT = 58.0, 42.4         # fabrication export, 2026-10-05
if os.environ.get("ENCLOSURE_BOARD", "ruler") == "export":
    BOARD_X, BOARD_Y = BOARD_X_EXPORT, BOARD_Y_EXPORT
else:
    BOARD_X, BOARD_Y = 53.0, 38.0                   # user's ruler, 2026-10-21
BOARD_T = 1.6
TERMINAL_H = 10.0       # KF301 screw terminals, the tallest parts
HEADER_H = 26.0         # Dupont housings on a 2x2 header plus wire bend room
ABOVE_BOARD = 26.0      # board top to lid underside
BOARD_STANDOFF = 4.0    # upper floor to board underside, clears pin tails
LEDGE_BOTTOM, LEDGE_TOP, LEDGE_FRONT = 3.5, 2.2, 2.2   # ledge contact under three board edges
FENCE_H = 8.0           # fences above the upper floor; terminal wire entries sit above
FRONT_CHANNEL = 6.0     # wire channel along the front wall for the sensor leads
WIRE_BAY_W = 20.0       # clear space beyond the terminal fence for the cell and wires
CELL_BEND_ROOM = 5.0    # terminal fence to the cell's near side

# Board features, measured from board edges. Board frame: bx along the terminal
# ("top") edge from the left corner, by from the top edge down. The top edge faces
# +X (the wire bay) and the left edge faces +Y (the back wall).
TERMINAL_PIN_IN = 4.19
TERMINAL_ALONG = ((6.14, 11.14), (32.3, 37.3))      # U11 (storage) and U9 (solar) pin pairs
TERMINAL_BODY = (10.0, 7.6)                         # along the edge, in from the edge
J3_IN = (18.16, 20.70)                               # right edge, from the top; bus A
J4_IN = (23.62, 26.16)                               # left edge, from the top; bus B
UFL_FROM_LEFT, UFL_FROM_BOTTOM = 6.1, 2.4
LORA_ALONG = (11.4, 27.0)                            # from the left corner
LORA_FROM_BOTTOM = (3.94, 21.24)                     # its near and far edges, up from the bottom edge
POST_BOARD_IN = 2.0                                  # hold-down post from the bottom edge
POST_BOARD_ALONG = 11.4                              # and from the right corner
BARE_BOTTOM_STRIP = (22.0, 40.0, 3.9)                # bare top-side strip along the bottom edge, depth

# ---- HS1040 cell (Eaton maxima) ------------------------------------------------
CELL_D, CELL_L = 10.5, 42.0
CELL_LEAD_P, CELL_LEAD_D = 5.0, 0.6
VBLOCK_T = 4.0

# ---- sensors -------------------------------------------------------------------
SHT41 = (25.0, 17.0)
ENS160 = (17.0, 18.0)
SENSOR_PAD_H, SENSOR_FOAM_T, SENSOR_BOARD_T = 3.0, 1.0, 1.6
SENSOR_HOUSING_H = 20.0   # Dupont housings standing on the breakout header

# ---- sensor cavity ----------------------------------------------------------------
LOUVRE_BAND = 20.0
SLOT_H, SLOT_PITCH = 2.5, 8.5
SLOT_L_LONG, SLOT_L_END, SLOT_WEB = 14.0, 12.0, 5.0
DRAIN_D, CHIMNEY_D = 3.0, 6.0
CHANNEL_SLOT = (12.0, 3.5)
CHANNEL_CHIMNEY_D = 5.0
GABLE_ANGLE = 45.0
RIDGE_FLAT = 8.0       # the gable is truncated to a flat ceiling this wide, so the chimney holes cut a plane; bridges at 8 mm

# ---- lid, eaves, fasteners, mounting ------------------------------------------------
EAVE_X, EAVE_FRONT, EAVE_BACK = 21.8, 15.0, 9.0
LID_T = 3.0
SKIRT_T, SKIRT_DROP, LABYRINTH_GAP = 1.6, 6.0, 2.5
NOTCH_W, NOTCH_D, NOTCH_PITCH = 10.0, 4.0, 16.0
COLUMN = 9.0                          # square corner column; WALL of it overlaps the wall
INSERT_D, INSERT_DEPTH = 4.0, 6.5     # M3 heat-set insert; set INSERT_D = 2.6 for self-tapping screws
SCREW_D, CSK_D = 3.4, 6.6
EAR_OUT, EAR_W, EAR_T = 12.0, 20.0, 3.0
EAR_SLOT = (8.0, 4.5)
POST_FOAM = 2.0                       # 3 mm foam compressed under each post
POST_D_BOARD, POST_D_TERMINAL = 3.5, 5.0
BOSS_D, BOSS_H = 8.0, 5.0
PV_HOLE_D = 4.0

# ---- antenna ----------------------------------------------------------------------------
SMA_D, SMA_FLAT = 6.5, 6.0
SMA_PLUG_D = 9.0        # the whip plug's coupling nut, which must pass under the lid's drip skirt
SMA_X = 10.0            # from the left end's outer face, along the back wall
SMA_BELOW_TOP = 11.5    # hole centre below the wall top: nut under the drip skirt, barrel above the terminals

# ---- panel wedge (PowerFilm MP3-37 at PANEL_ANGLE) ------------------------------------------
PANEL_ANGLE = 45.0
PLATE_L, PLATE_W, PLATE_T = 120.0, 42.0, 2.4
FRONT_LIFT = 8.0
CHEEK_T = 2.4
FOOT_L, FOOT_W, FOOT_T = 10.0, 8.0, 4.0
RIM_W, RIM_H = 1.5, 0.6
PV_L, PV_W, PV_T, PV_CLR = 114.0, 36.5, 0.22, 0.3
PV_SLOT = (1.5, 8.0)
DIAMOND, DIAMOND_PITCH = 5.0, 9.0

# ---- assembly view only ----------------------------------------------------------------------
ASSEMBLY_LIFT = 45.0    # how far the lid, wedge and panel float above the body in the GLB and viewer

# ================= derived: nothing below here is a free parameter =================

POCKET_X = BOARD_X + 2 * CLEARANCE
POCKET_Y = BOARD_Y + 2 * CLEARANCE
INNER_X = POCKET_X + DIVIDER + WIRE_BAY_W
INNER_Y = FRONT_CHANNEL + DIVIDER + POCKET_Y
BODY_X = INNER_X + 2 * WALL
BODY_Y = INNER_Y + 2 * WALL

# ---- heights, from the ground up ----
SENSOR_INNER = Rect(LOUVRE_WALL, LOUVRE_WALL, BODY_X - LOUVRE_WALL, BODY_Y - LOUVRE_WALL)
Z_LOWER_FLOOR = WALL
Z_BAND_TOP = Z_LOWER_FLOOR + LOUVRE_BAND
GABLE_RISE = SENSOR_INNER.d / 2 * math.tan(math.radians(GABLE_ANGLE))
Z_RIDGE = Z_BAND_TOP + GABLE_RISE
Z_CEILING = Z_RIDGE - RIDGE_FLAT / 2 * math.tan(math.radians(GABLE_ANGLE))   # flat strip where the apex would be
Z_FLOOR = Z_RIDGE + WALL
BOARD_BOTTOM_Z = Z_FLOOR + BOARD_STANDOFF
BOARD_TOP_Z = BOARD_BOTTOM_Z + BOARD_T
BODY_Z = BOARD_TOP_Z + ABOVE_BOARD
LID_Z0 = BODY_Z
LID_Z1 = BODY_Z + LID_T
CELL_R = CELL_D / 2
CELL_AXIS_Z = Z_FLOOR + CELL_R * math.sqrt(2)      # a 90 degree V with its bottom on the floor
POST_TIP_BOARD_Z = BOARD_TOP_Z + POST_FOAM
POST_TIP_TERMINAL_Z = BOARD_TOP_Z + TERMINAL_H + POST_FOAM
SMA_Z = BODY_Z - SMA_BELOW_TOP
SMA_Y = BODY_Y

# ---- electronics cavity, front to back and left to right ----
CAVITY = Rect(WALL, WALL, BODY_X - WALL, BODY_Y - WALL)
CHANNEL = Rect(WALL, WALL, BODY_X - WALL, WALL + FRONT_CHANNEL)
POCKET = Rect(WALL, CHANNEL.y1 + DIVIDER, WALL + POCKET_X, CHANNEL.y1 + DIVIDER + POCKET_Y)
FRONT_FENCE = Rect(WALL, CHANNEL.y1, POCKET.x1 + DIVIDER, POCKET.y0)
TERMINAL_FENCE = Rect(POCKET.x1, CHANNEL.y1, POCKET.x1 + DIVIDER, BODY_Y - WALL)
WIRE_BAY = Rect(TERMINAL_FENCE.x1, WALL, BODY_X - WALL, BODY_Y - WALL)
BOARD = POCKET.inset(CLEARANCE)


def board_to_body(bx: float, by: float) -> tuple[float, float]:
    """Board frame (bx along the terminal edge from the left corner, by down from it) to body XY."""
    return BOARD.x1 - by, BOARD.y1 - bx


def board_zone(left: float, right: float, top: float, bottom: float) -> Rect:
    """Rectangle on the board given by its edges in the board frame, clipped to the board."""
    x1, y1 = board_to_body(left, top)
    x0, y0 = board_to_body(right, bottom)
    return Rect(x0, y0, x1, y1).clip(BOARD)


LEDGES = (
    Rect(POCKET.x0, POCKET.y0, POCKET.x0 + LEDGE_BOTTOM + CLEARANCE, POCKET.y1),   # under the bottom edge (-X)
    Rect(POCKET.x1 - LEDGE_TOP - CLEARANCE, POCKET.y0, POCKET.x1, POCKET.y1),      # under the terminal edge (+X)
    Rect(POCKET.x0, POCKET.y0, POCKET.x1, POCKET.y0 + LEDGE_FRONT + CLEARANCE),    # under the front edge (-Y)
)
TERMINAL_XY = tuple(board_to_body(sum(pins) / 2, TERMINAL_PIN_IN) for pins in TERMINAL_ALONG)
U11_XY, U9_XY = TERMINAL_XY
TERMINAL_ZONES = tuple(board_zone(sum(pins) / 2 - TERMINAL_BODY[0] / 2, sum(pins) / 2 + TERMINAL_BODY[0] / 2,
                                  TERMINAL_PIN_IN - TERMINAL_BODY[1] / 2, TERMINAL_PIN_IN + TERMINAL_BODY[1] / 2)
                       for pins in TERMINAL_ALONG)
J3_XY = board_to_body(BOARD_Y, sum(J3_IN) / 2)
J4_XY = board_to_body(0.0, sum(J4_IN) / 2)
J3_ZONE = board_zone(BOARD_Y - 5.1, BOARD_Y, J3_IN[0] - 1.3, J3_IN[1] + 1.3)
J4_ZONE = board_zone(0.0, 5.1, J4_IN[0] - 1.3, J4_IN[1] + 1.3)
UFL_XY = board_to_body(UFL_FROM_LEFT, BOARD_X - UFL_FROM_BOTTOM)
UFL_ZONE = board_zone(UFL_FROM_LEFT - 2.0, UFL_FROM_LEFT + 2.0, BOARD_X - UFL_FROM_BOTTOM - 1.5, BOARD_X)
LORA_ZONE = board_zone(LORA_ALONG[0], LORA_ALONG[1], BOARD_X - LORA_FROM_BOTTOM[1], BOARD_X - LORA_FROM_BOTTOM[0])
INTERIOR_ZONE = BOARD.inset(BARE_BOTTOM_STRIP[2])
POSTS = (
    (U11_XY[0], U11_XY[1], POST_D_TERMINAL, POST_TIP_TERMINAL_Z),
    (U9_XY[0], U9_XY[1], POST_D_TERMINAL, POST_TIP_TERMINAL_Z),
    (BOARD.x0 + POST_BOARD_IN, BOARD.y0 + POST_BOARD_ALONG, POST_D_BOARD, POST_TIP_BOARD_Z),
)

# ---- wire bay: cell on two V-blocks, chimney holes between them ----
CELL_X = WIRE_BAY.x0 + CELL_BEND_ROOM + CELL_R
CELL_Y0 = WALL + 1.0
CELL_Y1 = CELL_Y0 + CELL_L
CELL_LEAD_END = "back"
VBLOCKS = tuple(Rect(WIRE_BAY.x0, y - VBLOCK_T / 2, WIRE_BAY.x1, y + VBLOCK_T / 2)
                for y in (CELL_Y0 + 8.0, CELL_Y0 + 34.0))
CHIMNEY_XY = tuple((WIRE_BAY.x0 + dx, SENSOR_INNER.cy) for dx in (5.0, 15.0))   # a 4 mm web between them takes the zip tie

# ---- front channel: sensor lead slot, drains, chimneys ----
CHANNEL_SLOT_RECT = Rect.centred(J3_XY[0], (SENSOR_INNER.y0 + 0.6 + CHANNEL.y1 - 0.3) / 2, *CHANNEL_SLOT)
_CHANNEL_MID_Y = (SENSOR_INNER.y0 + CHANNEL.y1) / 2
CHANNEL_CHIMNEY_XY = ((POCKET.x0 + 8.0, _CHANNEL_MID_Y), (POCKET.x1 - 6.0, _CHANNEL_MID_Y))
CHANNEL_DRAIN_XY = ((CHANNEL.x0 + 4.0, _CHANNEL_MID_Y), (CHANNEL.x1 - 4.0, _CHANNEL_MID_Y))

# ---- sensor cavity ----
SHT41_PAD = Rect.centred(SENSOR_INNER.x0 + 2 + (SHT41[0] - 2) / 2, SENSOR_INNER.cy, SHT41[0] - 2, SHT41[1] - 2)
ENS160_PAD = Rect.centred(SENSOR_INNER.x1 - 2 - (ENS160[0] - 2) / 2, SENSOR_INNER.cy, ENS160[0] - 2, ENS160[1] - 2)
SENSOR_BOARD_Z = Z_LOWER_FLOOR + SENSOR_PAD_H + SENSOR_FOAM_T
SHT41_BOARD = Rect.centred(SHT41_PAD.cx, SHT41_PAD.cy, *SHT41)
ENS160_BOARD = Rect.centred(ENS160_PAD.cx, ENS160_PAD.cy, *ENS160)
SENSOR_DRAIN_YZ = ((SENSOR_INNER.y0 + 8.0, Z_LOWER_FLOOR + 1.0), (SENSOR_INNER.y1 - 8.0, Z_LOWER_FLOOR + 1.0))   # cuts 0.5 into the floor so it drains dry


def _louvre_rows() -> tuple[float, ...]:
    # A 45 degree slot centred in the wall reaches this far above its centre at the wall face.
    reach = SLOT_H / 2 / math.cos(math.radians(45)) + LOUVRE_WALL / 2 + 1.0
    rows, z = [], Z_LOWER_FLOOR + reach + 1.3   # the lowest slot stays above the ears outside
    while z <= Z_BAND_TOP - reach:
        rows.append(z)
        z += SLOT_PITCH
    return tuple(rows)


def _pack(length: float, c0: float, slot: float) -> tuple[float, ...]:
    """Slot centres packed symmetrically along a wall of the given inner length, centred on c0."""
    usable = length - 2 * SLOT_WEB
    n = int((usable + SLOT_WEB) // (slot + SLOT_WEB))
    span = n * slot + (n - 1) * SLOT_WEB
    first = c0 - span / 2 + slot / 2
    return tuple(first + i * (slot + SLOT_WEB) for i in range(n))


LOUVRE_ROWS_Z = _louvre_rows()
LOUVRE_LONG_X = _pack(SENSOR_INNER.w, SENSOR_INNER.cx, SLOT_L_LONG)
LOUVRE_END_Y = _pack(SENSOR_INNER.d, SENSOR_INNER.cy, SLOT_L_END)

# ---- corner columns, ears, eave notches ----
COLUMN_OUT = COLUMN - WALL
_CORNERS = ((0.0, 0.0, -1, -1), (BODY_X, 0.0, 1, -1), (0.0, BODY_Y, -1, 1), (BODY_X, BODY_Y, 1, 1))


def _column(cx: float, cy: float, sx: int, sy: int) -> Rect:
    xa, xb = cx + sx * COLUMN_OUT, cx - sx * WALL
    ya, yb = cy + sy * COLUMN_OUT, cy - sy * WALL
    return Rect(min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb))


COLUMNS = tuple(_column(*c) for c in _CORNERS)
INSERT_XY = tuple((c.cx, c.cy) for c in COLUMNS)
COLUMN_ENV = Rect(-COLUMN_OUT, -COLUMN_OUT, BODY_X + COLUMN_OUT, BODY_Y + COLUMN_OUT)
EARS = (
    Rect(-EAR_OUT, BODY_Y / 2 - EAR_W / 2, 0.5, BODY_Y / 2 + EAR_W / 2),
    Rect(BODY_X - 0.5, BODY_Y / 2 - EAR_W / 2, BODY_X + EAR_OUT, BODY_Y / 2 + EAR_W / 2),
)
EAR_SLOTS = (
    Rect.centred(-EAR_OUT / 2, BODY_Y / 2, *EAR_SLOT),
    Rect.centred(BODY_X + EAR_OUT / 2, BODY_Y / 2, *EAR_SLOT),
)


def _notch_centres(length: float) -> tuple[float, ...]:
    corner = COLUMN_OUT + NOTCH_W / 2
    span = length - 2 * corner
    n = int(span // NOTCH_PITCH) + 1
    first = length / 2 - (n - 1) * NOTCH_PITCH / 2
    return tuple(first + i * NOTCH_PITCH for i in range(n))


NOTCHES = tuple([("front", c) for c in _notch_centres(BODY_X)] + [("back", c) for c in _notch_centres(BODY_X)]
                + [("left", c) for c in _notch_centres(BODY_Y)] + [("right", c) for c in _notch_centres(BODY_Y)])

# ---- lid ----
LID = Rect(-EAVE_X, -EAVE_FRONT, BODY_X + EAVE_X, BODY_Y + EAVE_BACK)
LABYRINTH = COLUMN_ENV.inset(-(LABYRINTH_GAP + SKIRT_T)).clip(LID.inset(SKIRT_T))

# ---- panel wedge, centred on the body ----
WEDGE_SPAN_Y = PLATE_W * math.cos(math.radians(PANEL_ANGLE))
WEDGE_RISE = PLATE_W * math.sin(math.radians(PANEL_ANGLE))
WEDGE_ORIGIN = (BODY_X / 2 - PLATE_L / 2, BODY_Y / 2 - WEDGE_SPAN_Y / 2)
# the feet turn outward, in front of the front wall and behind the open back, so every screw is driven from open sky
BOSS_XY = tuple((WEDGE_ORIGIN[0] + x, WEDGE_ORIGIN[1] + y)
                for x in (CHEEK_T + FOOT_L / 2, PLATE_L - CHEEK_T - FOOT_L / 2)
                for y in (-FOOT_W / 2, WEDGE_SPAN_Y + FOOT_W / 2))
# solar lead hole: over the bend gap between the terminal fence and the cell, behind the wedge's front wall so the
# wall dams the water that sheds off the panel's low edge
PV_HOLE_XY = (WIRE_BAY.x0 + CELL_BEND_ROOM / 2, max(U9_XY[1], WEDGE_ORIGIN[1] + CHEEK_T + 1.0 + PV_HOLE_D / 2))


def coupon_fences() -> tuple[tuple[Rect, tuple[Rect, ...]], tuple[Rect, tuple[Rect, ...]]]:
    """Two pocket fences in the coupon's own frame, ruler outline then export outline, front to back."""
    def fence(x0: float, y0: float, bx: float, by: float) -> tuple[Rect, tuple[Rect, ...]]:
        f = Rect(x0, y0, x0 + bx + 2 * CLEARANCE, y0 + by + 2 * CLEARANCE)
        ledges = (
            Rect(f.x0, f.y0, f.x0 + LEDGE_BOTTOM + CLEARANCE, f.y1),
            Rect(f.x1 - LEDGE_TOP - CLEARANCE, f.y0, f.x1, f.y1),
            Rect(f.x0, f.y0, f.x1, f.y0 + LEDGE_FRONT + CLEARANCE),
        )
        return f, ledges

    ruler = fence(0.0, 0.0, 53.0, 38.0)
    export = fence(0.0, ruler[0].y1 + 6.0, BOARD_X_EXPORT, BOARD_Y_EXPORT)
    return ruler, export
