# Sensor Node Enclosure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate print-ready STL, 3MF and STEP files plus renders for the sensor node body, two lid variants and a fit coupon from one parametric build123d project.

**Architecture:** `params.py` holds every dimension and the derived 2D layout as plain Python, so layout rules are unit-tested without CAD. Each printed part lives in its own module that turns that layout into a build123d solid. `build.py` exports files and `render.py` draws PNG views. Pytest checks the layout, solid validity, and interference against reference models of the PCB panel and the supercapacitor pack.

**Tech Stack:** Python 3.13, build123d 0.11.1 on the OpenCASCADE kernel, pytest, matplotlib.

**Spec:** `docs/superpowers/specs/2026-09-14-enclosure-design.md`

## Global Constraints

- Units are millimetres. Frame: X left to right, Y front to back, Z up, lid facing the sky.
- Origin is the outer front-left bottom corner of the body walls. Corner columns and mounting ears extend past it.
- All code lives under `enclosure/`. Run Python as `enclosure/.venv/Scripts/python.exe`; run tests with `cd enclosure && .venv/Scripts/python.exe -m pytest`.
- Walls and floor 2.4 mm, vent walls 4.0 mm, internal walls 2.0 mm, fit clearance 0.3 mm per side.
- Printed parts must be valid closed solids that print without supports: no overhang flatter than 45 degrees except bridges shorter than 10 mm.
- Files in `enclosure/out/` are committed so the parts print without Python.
- Commit messages are short and plain, with no co-author trailer. Push to `origin main` after each task.

## File Structure

| File | Responsibility |
|---|---|
| `enclosure/requirements.txt` | pinned Python dependencies |
| `enclosure/pytest.ini` | test discovery and import path |
| `enclosure/params.py` | dimensions, `Rect`, derived layout, panel recess and slot rules; no CAD imports |
| `enclosure/shapes.py` | `slab`, `rod`, `peg` solid helpers; reference solids for the PCB panel, board keep-out and supercap pack |
| `enclosure/coupon.py` | `build_coupon()` |
| `enclosure/body.py` | `build_body()` |
| `enclosure/lid.py` | `build_lid(panel_count)` |
| `enclosure/build.py` | exports every part to `out/` in print orientation plus `assembly.glb` |
| `enclosure/render.py` | shaded PNG views to `out/renders/` |
| `enclosure/tests/test_params.py` | layout rules |
| `enclosure/tests/test_parts.py` | solid validity, key features, interference |
| `enclosure/README.md` | regenerate, print settings, hardware, assembly order |
| `.gitignore` | ignore the venv and test caches |

---

### Task 1: Toolchain and layout parameters

**Files:**
- Create: `enclosure/requirements.txt`, `enclosure/pytest.ini`, `enclosure/params.py`, `enclosure/tests/test_params.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: module `params` with `Rect(x0, y0, x1, y1)` exposing `w`, `d`, `cx`, `cy`, `inset(m) -> Rect`, `contains(other) -> bool`, `contains_point(x, y) -> bool`, `Rect.centred(cx, cy, w, d) -> Rect`. Size constants `BODY_X`, `BODY_Y`, `BODY_Z`, `INNER_Z`, `PANEL_BOTTOM_Z`, `PANEL_TOP_Z`, `POST_TIP_Z`. Layout rects `CAVITY`, `SENSOR_BAY`, `SENSOR_BAY_INNER`, `SENSOR_WALL`, `ELECTRONICS`, `POCKET`, `PANEL`, `BOARD`, `LEDGE_OUTER`, `LEDGE_INNER`, `CAP_DIVIDER`, `CAP_BAY`, `CAP`, `LID`. Tuples `CAP_RAILS`, `COLUMNS`, `EARS`, `EAR_SLOTS` of `Rect`; `PEG_XY`, `POST_XY`, `INSERT_XY`, `DRAIN_XY` of `(x, y)`; `VENT_ROWS_Z`, `VENT_FRONT_X` of floats; floats `VENT_END_Y`, `COLUMN_OUT`; points `J1_XY`, `JP1_XY`. Rects `DIVIDER_NOTCH`, `WIRE_NOTCH_RECT`, `SHT41_PAD`, `ENS160_PAD`; point `TIE_ANCHOR_YZ`. Functions `pv_recesses(count) -> tuple[Rect, ...]`, `pv_slots(recess) -> tuple[Rect, ...]`, `max_panels() -> int`.

- [ ] **Step 1: Pin dependencies and ignore local artefacts**

`enclosure/requirements.txt`:

```
build123d==0.11.1
pytest>=8
matplotlib>=3.9
```

`enclosure/pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = .
```

Append to `.gitignore`:

```
enclosure/.venv/
__pycache__/
.pytest_cache/
```

Create the environment if it does not exist:

```bash
python -m venv enclosure/.venv
enclosure/.venv/Scripts/python.exe -m pip install -r enclosure/requirements.txt
```

- [ ] **Step 2: Write the failing layout tests**

`enclosure/tests/test_params.py`:

```python
import math

import params as p


def test_internal_and_outer_sizes_match_spec():
    assert round(p.INNER_X, 1) == 116.6
    assert round(p.INNER_Y, 1) == 100.0
    assert round(p.INNER_Z, 1) == 33.6
    assert (round(p.BODY_X, 1), round(p.BODY_Y, 1), round(p.BODY_Z, 1)) == (121.4, 104.8, 36.0)


def test_lid_covers_columns_with_skirt_gap():
    assert (round(p.LID.w, 1), round(p.LID.d, 1)) == (138.6, 122.0)
    for col in p.COLUMNS:
        assert p.LID.inset(p.SKIRT_T + p.SKIRT_GAP).contains(col)


def test_panel_sits_in_pocket_against_sensor_wall():
    assert p.POCKET.contains(p.PANEL)
    assert math.isclose(p.PANEL.x0 - p.POCKET.x0, p.CLEARANCE)
    assert p.POCKET.y0 == p.SENSOR_WALL.y1
    assert (round(p.PANEL.w, 1), round(p.PANEL.d, 1)) == (p.PANEL_X, p.PANEL_Y)


def test_ledge_stops_short_of_v_scores():
    assert p.LEDGE_INNER.x0 <= p.BOARD.x0 - 1.0
    assert p.LEDGE_INNER.x1 >= p.BOARD.x1 + 1.0
    assert p.LEDGE_INNER.y0 <= p.BOARD.y0 - 1.0
    assert p.LEDGE_INNER.y1 >= p.BOARD.y1 + 1.0


def test_pegs_stand_on_the_ledge():
    r = p.PEG_D / 2
    for x, y in p.PEG_XY:
        assert p.LEDGE_OUTER.inset(r).contains_point(x, y)
        assert not p.LEDGE_INNER.inset(-r).contains_point(x, y)


def test_lid_posts_land_on_side_rails_only():
    r = p.POST_D / 2
    for x, y in p.POST_XY:
        assert p.PANEL.inset(r).contains_point(x, y)
        assert not p.BOARD.inset(-r).contains_point(x, y)


def test_supercap_fits_its_bay():
    assert p.CAP_BAY.inset(1.0).contains(p.CAP)
    assert p.CAP_RAIL_H + p.CAP_H <= p.INNER_Z
    for rail in p.CAP_RAILS:
        assert p.CAP.contains(rail)


def test_sensor_breakouts_fit_the_bay_far_apart():
    assert p.SENSOR_BAY_INNER.contains(p.SHT41_PAD.inset(-1.0))
    assert p.SENSOR_BAY_INNER.contains(p.ENS160_PAD.inset(-1.0))
    assert p.ENS160_PAD.x0 - p.SHT41_PAD.x1 >= 60.0


def test_sma_nut_clears_sensor_wall_and_board():
    assert p.SMA_Y - 5.0 >= p.POCKET.y0
    assert p.SMA_Z - 5.0 >= p.PANEL_TOP_Z


def test_three_panels_fit_and_only_back_two_get_slots():
    assert p.max_panels() == 3
    rec = p.pv_recesses(3)
    for r in rec[:2]:
        slots = p.pv_slots(r)
        assert len(slots) == 2
        for s in slots:
            assert p.ELECTRONICS.inset(1.0).contains(s)
            assert r.contains(s)
    assert p.pv_slots(rec[2]) == ()


def test_countersinks_clear_panel_recesses():
    for x, y in p.INSERT_XY:
        for r in p.pv_recesses(3):
            assert not r.inset(-p.CSK_D / 2).contains_point(x, y)


def test_vent_webs_and_rows_are_printable():
    web = p.VENT_PITCH * math.cos(math.radians(45)) - p.VENT_SLOT_H
    assert web >= 1.6
    assert len(p.VENT_ROWS_Z) >= 4
    assert len(p.VENT_FRONT_X) >= 3
    assert min(p.WALL, p.DIVIDER, p.SKIRT_T, p.VENT_WALL) >= 1.6
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `cd enclosure && .venv/Scripts/python.exe -m pytest tests/test_params.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'params'`.

- [ ] **Step 4: Write `params.py`**

`enclosure/params.py`:

```python
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
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `cd enclosure && .venv/Scripts/python.exe -m pytest tests/test_params.py -q`
Expected: `12 passed`.

- [ ] **Step 6: Commit**

```bash
git add .gitignore enclosure/requirements.txt enclosure/pytest.ini enclosure/params.py enclosure/tests/test_params.py
git commit -m "Add enclosure layout parameters with tests"
git push origin main
```

---

### Task 2: Solid helpers, reference models and the fit coupon

**Files:**
- Create: `enclosure/shapes.py`, `enclosure/coupon.py`, `enclosure/tests/test_parts.py`

**Interfaces:**
- Consumes: `params` from Task 1.
- Produces: in `shapes`: constants `EPS = 0.05`, `MIN`, `CENTRE_BASE`; `slab(r: Rect, z0, z1) -> Part`; `rod(x, y, d, z0, z1) -> Part`; `peg(x, y, z0) -> Part`; `sma_cutter(length) -> Part` (double-D cutter, axis +Z, base at z=0, centred on the origin); `pcb_panel() -> Part`; `board_keepout() -> Part`; `supercap() -> Part`; `overlap(a, b) -> float`. In `coupon`: `build_coupon() -> Part`.

- [ ] **Step 1: Write the failing tests**

`enclosure/tests/test_parts.py`:

```python
import pytest
from build123d import Vector

import params as p
from coupon import RING_T, build_coupon
from shapes import board_keepout, overlap, pcb_panel, supercap


@pytest.fixture(scope="module")
def coupon():
    return build_coupon()


def test_reference_models_have_expected_volumes():
    hole_area = 4 * 3.14159 * (p.TOOLING_HOLE_D / 2) ** 2
    assert pcb_panel().volume == pytest.approx((p.PANEL.w * p.PANEL.d - hole_area) * p.PANEL_T, rel=1e-3)
    assert board_keepout().volume == pytest.approx(p.BOARD_X * p.BOARD_Y * p.ABOVE_BOARD, rel=1e-6)
    assert supercap().volume == pytest.approx(p.CAP_L * p.CAP_W * p.CAP_H, rel=1e-6)
    assert overlap(pcb_panel(), supercap()) < 1e-9


def test_coupon_is_one_valid_solid(coupon):
    assert coupon.is_valid()
    assert len(coupon.solids()) == 1


def test_coupon_has_pegs_and_open_test_holes(coupon):
    for x, y in p.PEG_XY:
        assert coupon.is_inside(Vector(x, y, RING_T + p.PEG_H / 2))
    ring_mid = p.LEDGE_OUTER.x0 + p.LEDGE_W / 2
    assert coupon.is_inside(Vector(ring_mid, p.POCKET.cy, RING_T / 2))
    assert not coupon.is_inside(Vector(p.POCKET.cx, p.POCKET.cy, RING_T / 2))


def test_coupon_fits_a_small_bed(coupon):
    size = coupon.bounding_box().size
    assert size.X < 110 and size.Y < 90 and size.Z < 8.5
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd enclosure && .venv/Scripts/python.exe -m pytest tests/test_parts.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'coupon'`.

- [ ] **Step 3: Write `shapes.py`**

`enclosure/shapes.py`:

```python
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
```

- [ ] **Step 4: Write `coupon.py`**

`enclosure/coupon.py`:

```python
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
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `cd enclosure && .venv/Scripts/python.exe -m pytest tests/test_parts.py -q`
Expected: `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add enclosure/shapes.py enclosure/coupon.py enclosure/tests/test_parts.py
git commit -m "Add solid helpers, reference models and the fit coupon"
git push origin main
```

---

### Task 3: The body

**Files:**
- Create: `enclosure/body.py`
- Modify: `enclosure/tests/test_parts.py` (append)

**Interfaces:**
- Consumes: `params` (Task 1); `EPS`, `slab`, `rod`, `peg`, `sma_cutter`, `pcb_panel`, `board_keepout`, `supercap`, `overlap` from `shapes` (Task 2).
- Produces: `body.build_body() -> Part`, in the body frame with the floor on z=0.

- [ ] **Step 1: Append the failing body tests**

Append to `enclosure/tests/test_parts.py`:

```python
from body import build_body


@pytest.fixture(scope="module")
def body():
    return build_body()


def test_body_is_one_valid_solid(body):
    assert body.is_valid()
    assert len(body.solids()) == 1


def test_body_overall_size(body):
    bb = body.bounding_box()
    assert bb.min.X == pytest.approx(-p.EAR_OUT, abs=0.01)
    assert bb.max.X == pytest.approx(p.BODY_X + p.EAR_OUT, abs=0.01)
    assert bb.min.Y == pytest.approx(-p.COLUMN_OUT, abs=0.01)
    assert bb.max.Y == pytest.approx(p.BODY_Y + p.COLUMN_OUT, abs=0.01)
    assert bb.min.Z == pytest.approx(0.0, abs=0.01)
    assert bb.max.Z == pytest.approx(p.BODY_Z, abs=0.01)


def test_body_leaves_room_for_board_and_supercap(body):
    assert overlap(body, pcb_panel()) < 1e-3
    assert overlap(body, board_keepout()) < 1e-3
    assert overlap(body, supercap()) < 1e-3


def test_body_supports_are_solid(body):
    for x, y in p.PEG_XY:
        assert body.is_inside(Vector(x, y, p.PANEL_BOTTOM_Z + p.PEG_H / 2))
    assert body.is_inside(Vector(p.POCKET.x0 + p.LEDGE_W / 2, p.POCKET.cy, p.PANEL_BOTTOM_Z - 1.0))
    for rail in p.CAP_RAILS:
        assert body.is_inside(Vector(rail.cx, rail.cy, p.WALL + p.CAP_RAIL_H / 2))
    for pad in (p.SHT41_PAD, p.ENS160_PAD):
        assert body.is_inside(Vector(pad.cx, pad.cy, p.WALL + p.SENSOR_PAD_H / 2))


def test_body_openings_are_open(body):
    assert not body.is_inside(Vector(p.WALL / 2, p.SMA_Y, p.SMA_Z))
    for x, y in p.DRAIN_XY:
        assert not body.is_inside(Vector(x, y, p.WALL / 2))
    z = p.VENT_ROWS_Z[0]
    for x in p.VENT_FRONT_X:
        assert not body.is_inside(Vector(x, p.VENT_WALL / 2, z))
    assert not body.is_inside(Vector(p.VENT_WALL / 2, p.VENT_END_Y, z))
    assert not body.is_inside(Vector(p.BODY_X - p.VENT_WALL / 2, p.VENT_END_Y, z))
    assert not body.is_inside(Vector(p.WIRE_NOTCH_RECT.cx, p.SENSOR_WALL.cy, p.BODY_Z - 1.0))
    assert not body.is_inside(Vector(p.CAP_DIVIDER.cx, p.DIVIDER_NOTCH.cy, p.WALL + p.DIVIDER_H - 1.0))
    for x, y in p.INSERT_XY:
        assert not body.is_inside(Vector(x, y, p.BODY_Z - 1.0))


def test_front_vents_have_no_straight_horizontal_path(body):
    x, z0 = p.VENT_FRONT_X[0], p.VENT_ROWS_Z[1]
    for i in range(41):
        h = z0 - 4.0 + i * 0.2
        assert any(body.is_inside(Vector(x, y, h)) for y in (0.1, 1.0, 2.0, 3.0, 3.9)), h
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd enclosure && .venv/Scripts/python.exe -m pytest tests/test_parts.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'body'`.

- [ ] **Step 3: Write `body.py`**

`enclosure/body.py`:

```python
"""The body: shell, corner columns and ears, panel ledge and pegs, supercap rails,
sensor bay with angled vents, and every hole and notch."""
from __future__ import annotations

from build123d import Box, Part, Pos, Rot

import params as p
from shapes import EPS, peg, rod, slab, sma_cutter

Rect = p.Rect


def _additions() -> list[Part]:
    top = p.BODY_Z
    floor = p.WALL - EPS
    solids = [slab(c, 0, top) for c in p.COLUMNS]
    solids += [slab(e, 0, p.WALL) for e in p.EARS]
    # sensor bay walls thickened inward to carry vents, and the wall that seals the bay
    solids += [
        slab(Rect(p.WALL - EPS, p.WALL - EPS, p.BODY_X - p.WALL + EPS, p.VENT_WALL), floor, top),
        slab(Rect(p.WALL - EPS, p.WALL - EPS, p.VENT_WALL, p.SENSOR_WALL.y0 + EPS), floor, top),
        slab(Rect(p.BODY_X - p.VENT_WALL, p.WALL - EPS, p.BODY_X - p.WALL + EPS, p.SENSOR_WALL.y0 + EPS),
             floor, top),
        slab(Rect(p.WALL - EPS, p.SENSOR_WALL.y0, p.BODY_X - p.WALL + EPS, p.SENSOR_WALL.y1), floor, top),
        slab(Rect(p.CAP_DIVIDER.x0, p.CAP_DIVIDER.y0 - EPS, p.CAP_DIVIDER.x1, p.CAP_DIVIDER.y1 + EPS),
             floor, p.WALL + p.DIVIDER_H),
    ]
    ledge = slab(p.LEDGE_OUTER.inset(-EPS), floor, p.PANEL_BOTTOM_Z).cut(
        slab(p.LEDGE_INNER, 0, p.PANEL_BOTTOM_Z + 1))
    solids.append(ledge)
    if p.PEGS_ENABLED:
        solids += [peg(x, y, p.PANEL_BOTTOM_Z) for x, y in p.PEG_XY]
    solids += [slab(r, floor, p.WALL + p.CAP_RAIL_H) for r in p.CAP_RAILS]
    solids += [slab(pad, floor, p.WALL + p.SENSOR_PAD_H) for pad in (p.SHT41_PAD, p.ENS160_PAD)]
    return solids


def _vent_cutters() -> list[Part]:
    through = 12.0   # long enough to pass through a 4 mm wall at 45 degrees
    cutters = []
    for z in p.VENT_ROWS_Z:
        # every slot slopes down toward the outside, so rain cannot fly straight in
        cutters += [Pos(x, p.VENT_WALL / 2, z) * Rot(45, 0, 0) * Box(p.VENT_SLOT_L, through, p.VENT_SLOT_H)
                    for x in p.VENT_FRONT_X]
        cutters.append(Pos(p.VENT_WALL / 2, p.VENT_END_Y, z) * Rot(0, -45, 0)
                       * Box(through, p.VENT_END_SLOT_L, p.VENT_SLOT_H))
        cutters.append(Pos(p.BODY_X - p.VENT_WALL / 2, p.VENT_END_Y, z) * Rot(0, 45, 0)
                       * Box(through, p.VENT_END_SLOT_L, p.VENT_SLOT_H))
    return cutters


def _cutters() -> list[Part]:
    top = p.BODY_Z
    tie_y, tie_z = p.TIE_ANCHOR_YZ
    cutters = _vent_cutters()
    cutters += [
        Pos(-1, p.SMA_Y, p.SMA_Z) * Rot(0, 90, 0) * sma_cutter(p.WALL + 2),
        slab(p.WIRE_NOTCH_RECT, top - p.WIRE_NOTCH_DEPTH, top + 1),
        slab(p.DIVIDER_NOTCH, p.WALL + p.DIVIDER_H - 6.0, p.WALL + p.DIVIDER_H + 1),
        slab(Rect(p.CAP_DIVIDER.x0 - 1, tie_y - 1.5, p.CAP_DIVIDER.x1 + 1, tie_y + 1.5), tie_z - 0.75, tie_z + 0.75),
    ]
    cutters += [rod(x, y, p.DRAIN_D, -1, p.WALL + 1) for x, y in p.DRAIN_XY]
    cutters += [rod(x, y, p.INSERT_D, top - p.INSERT_DEPTH, top + 1) for x, y in p.INSERT_XY]
    cutters += [slab(s, -1, p.WALL + 1) for s in p.EAR_SLOTS]
    return cutters


def build_body() -> Part:
    shell = slab(Rect(0.0, 0.0, p.BODY_X, p.BODY_Y), 0, p.BODY_Z)
    hollow = shell.cut(slab(p.CAVITY, p.WALL, p.BODY_Z + 1))
    return hollow.fuse(*_additions()).cut(*_cutters())
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd enclosure && .venv/Scripts/python.exe -m pytest tests/test_parts.py -q`
Expected: `10 passed`.

- [ ] **Step 5: Commit**

```bash
git add enclosure/body.py enclosure/tests/test_parts.py
git commit -m "Model the enclosure body"
git push origin main
```

---

### Task 4: The lid

**Files:**
- Create: `enclosure/lid.py`
- Modify: `enclosure/tests/test_parts.py` (append)

**Interfaces:**
- Consumes: `params` (Task 1); `CENTRE_BASE`, `EPS`, `rod`, `slab`, `overlap`, reference models from `shapes` (Task 2); the `body` fixture from Task 3's tests.
- Produces: `lid.build_lid(panel_count: int = 2) -> Part` in the body frame, underside on `z = BODY_Z`. Raises `ValueError` unless `1 <= panel_count <= params.max_panels()`.

- [ ] **Step 1: Append the failing lid tests**

Append to `enclosure/tests/test_parts.py`:

```python
from lid import build_lid


@pytest.fixture(scope="module", params=[2, 3], ids=["2panel", "3panel"])
def lid(request):
    return request.param, build_lid(request.param)


def test_lid_is_one_valid_solid(lid):
    _, part = lid
    assert part.is_valid()
    assert len(part.solids()) == 1


def test_lid_clears_body_board_and_supercap(lid, body):
    _, part = lid
    for other in (body, pcb_panel(), board_keepout(), supercap()):
        assert overlap(part, other) < 1e-3


def test_lid_recesses_slots_and_screw_holes_are_open(lid):
    count, part = lid
    top = p.BODY_Z + p.LID_T
    for r in p.pv_recesses(count):
        assert not part.is_inside(Vector(r.cx, r.cy, top - p.PV_RECESS_DEPTH / 2))
        assert part.is_inside(Vector(r.cx, r.cy, top - p.PV_RECESS_DEPTH - 0.5))
        for s in p.pv_slots(r):
            assert not part.is_inside(Vector(s.cx, s.cy, p.BODY_Z + p.LID_T / 2))
    for x, y in p.INSERT_XY:
        assert not part.is_inside(Vector(x, y, p.BODY_Z + 0.5))


def test_lid_posts_stop_just_above_the_rails(lid):
    _, part = lid
    for x, y in p.POST_XY:
        assert part.is_inside(Vector(x, y, p.POST_TIP_Z + 0.5))
        assert not part.is_inside(Vector(x, y, p.POST_TIP_Z - 0.5))


def test_lid_rejects_more_panels_than_fit():
    with pytest.raises(ValueError):
        build_lid(p.max_panels() + 1)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd enclosure && .venv/Scripts/python.exe -m pytest tests/test_parts.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'lid'`.

- [ ] **Step 3: Write `lid.py`**

`enclosure/lid.py`:

```python
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
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd enclosure && .venv/Scripts/python.exe -m pytest tests/test_parts.py -q`
Expected: `19 passed`.

- [ ] **Step 5: Commit**

```bash
git add enclosure/lid.py enclosure/tests/test_parts.py
git commit -m "Model the lid for two or three solar panels"
git push origin main
```

---

### Task 5: Export, renders and README

**Files:**
- Create: `enclosure/build.py`, `enclosure/render.py`, `enclosure/tests/test_build.py`, `enclosure/README.md`
- Generated and committed: `enclosure/out/*.stl`, `*.3mf`, `*.step`, `assembly.glb`, `renders/*.png`

**Interfaces:**
- Consumes: `build_body`, `build_lid`, `build_coupon`, `pcb_panel`, `supercap`.
- Produces: in `build`: `OUT: Path`, `print_ready(part, flip: bool) -> Part`, `parts() -> dict[str, tuple[Part, bool]]`, `export_all() -> list[Path]`. `render.py` writes `out/renders/<name>_<view>.png`.

- [ ] **Step 1: Write the failing export tests**

`enclosure/tests/test_build.py`:

```python
import pytest

import build
import params as p


def test_lid_prints_top_face_down_on_the_bed():
    lid = build.print_ready(build.build_lid(2), flip=True)
    bb = lid.bounding_box()
    assert bb.min.Z == pytest.approx(0.0, abs=1e-6)
    assert bb.size.Z == pytest.approx(p.BODY_Z + p.LID_T - p.POST_TIP_Z, abs=0.01)


def test_export_writes_every_file(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "OUT", tmp_path)
    written = {path.name: path for path in build.export_all()}
    for part in ("body", "lid_2panel", "lid_3panel", "fit_coupon"):
        for suffix in (".stl", ".3mf", ".step"):
            assert written[f"{part}{suffix}"].stat().st_size > 1000
    assert written["assembly.glb"].stat().st_size > 1000
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd enclosure && .venv/Scripts/python.exe -m pytest tests/test_build.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'build'`.

- [ ] **Step 3: Write `build.py`**

`enclosure/build.py`:

```python
"""Export every printable part to out/ in print orientation, plus an assembly GLB for the viewer.

Run from enclosure/:  .venv/Scripts/python.exe build.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build123d import Color, Compound, Mesher, Part, Pos, Rot, export_gltf, export_step, export_stl  # noqa: E402

from body import build_body  # noqa: E402
from coupon import build_coupon  # noqa: E402
from lid import build_lid  # noqa: E402
from shapes import pcb_panel, supercap  # noqa: E402

OUT = HERE / "out"
LID_LIFT = 40.0   # how far the lid floats above the body in the assembly view


def print_ready(part: Part, flip: bool) -> Part:
    """Optionally turn the part upside down, then centre it on the bed with its lowest point on z=0."""
    if flip:
        part = Rot(180, 0, 0) * part
    bb = part.bounding_box()
    return Pos(-bb.center().X, -bb.center().Y, -bb.min.Z) * part


def parts() -> dict[str, tuple[Part, bool]]:
    """Printable parts by file name, each with whether it prints upside down."""
    return {
        "body": (build_body(), False),
        "lid_2panel": (build_lid(2), True),
        "lid_3panel": (build_lid(3), True),
        "fit_coupon": (build_coupon(), False),
    }


def _write_3mf(part: Part, path: Path) -> None:
    mesher = Mesher()
    mesher.add_shape(part, linear_deflection=0.01, angular_deflection=0.2)
    mesher.write(str(path))


def _write_assembly(body: Part, lid: Part) -> Path:
    body = Pos(0, 0, 0) * body
    body.label, body.color = "body", Color(0.92, 0.92, 0.89)
    lid = Pos(0, 0, LID_LIFT) * lid
    lid.label, lid.color = "lid", Color(0.80, 0.84, 0.88)
    board = pcb_panel()
    board.label, board.color = "pcb", Color(0.08, 0.32, 0.66)
    cap = supercap()
    cap.label, cap.color = "supercap", Color(0.18, 0.18, 0.20)
    path = OUT / "assembly.glb"
    export_gltf(Compound(children=[body, lid, board, cap]), str(path), binary=True,
                linear_deflection=0.05, angular_deflection=0.3)
    return path


def export_all() -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    models = parts()
    written: list[Path] = []
    for name, (model, flip) in models.items():
        if not model.is_valid():
            raise RuntimeError(f"{name} is not a valid solid")
        printable = print_ready(model, flip)
        export_stl(printable, str(OUT / f"{name}.stl"), tolerance=0.01, angular_tolerance=0.2)
        _write_3mf(printable, OUT / f"{name}.3mf")
        export_step(printable, str(OUT / f"{name}.step"))
        written += [OUT / f"{name}{suffix}" for suffix in (".stl", ".3mf", ".step")]
    written.append(_write_assembly(models["body"][0], models["lid_2panel"][0]))
    return written


if __name__ == "__main__":
    for path in export_all():
        print(f"{path.name:22} {path.stat().st_size / 1024:8.0f} KB")
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd enclosure && .venv/Scripts/python.exe -m pytest tests/test_build.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Write `render.py`**

`enclosure/render.py`:

```python
"""Shaded PNG views of every part for visual review. Writes out/renders/<name>_<view>.png.

Run from enclosure/:  .venv/Scripts/python.exe render.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from build123d import Part, Pos  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

from build import LID_LIFT, OUT, parts  # noqa: E402
from shapes import pcb_panel, supercap  # noqa: E402

LIGHT = np.array([0.45, -0.55, 0.70]) / np.linalg.norm([0.45, -0.55, 0.70])
VIEWS = {"front": (24, -62), "back": (30, 118), "top": (88, -90), "under": (-35, -62)}
BODY_RGB, LID_RGB, PCB_RGB, CAP_RGB = (0.90, 0.88, 0.84), (0.78, 0.83, 0.88), (0.10, 0.35, 0.70), (0.25, 0.25, 0.28)


def _triangles(part: Part) -> np.ndarray:
    verts, tris = part.tessellate(0.05, 0.3)
    v = np.array([(q.X, q.Y, q.Z) for q in verts])
    return v[np.array(tris)]


def _render(name: str, items: list[tuple[Part, tuple[float, float, float]]], out_dir: Path) -> list[Path]:
    tris, colours = [], []
    for part, rgb in items:
        t = _triangles(part)
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        shade = 0.30 + 0.70 * np.clip(n @ LIGHT, 0.0, 1.0)
        tris.append(t)
        colours.append(np.clip(np.outer(shade, rgb), 0.0, 1.0))
    tris_all, colours_all = np.concatenate(tris), np.concatenate(colours)
    lo, hi = tris_all.reshape(-1, 3).min(0), tris_all.reshape(-1, 3).max(0)
    written = []
    for view, (elev, azim) in VIEWS.items():
        fig = plt.figure(figsize=(9, 7), dpi=120)
        ax = fig.add_subplot(projection="3d")
        ax.add_collection3d(Poly3DCollection(tris_all, facecolors=colours_all, edgecolors="none"))
        ax.set_xlim(lo[0], hi[0])
        ax.set_ylim(lo[1], hi[1])
        ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect(tuple(hi - lo))
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.set_title(f"{name}, {view}")
        path = out_dir / f"{name}_{view}.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        written.append(path)
    return written


def main() -> None:
    out_dir = OUT / "renders"
    out_dir.mkdir(parents=True, exist_ok=True)
    models = parts()
    body, lid = models["body"][0], models["lid_2panel"][0]
    jobs = {
        "body": [(body, BODY_RGB)],
        "lid_2panel": [(lid, LID_RGB)],
        "lid_3panel": [(models["lid_3panel"][0], LID_RGB)],
        "fit_coupon": [(models["fit_coupon"][0], BODY_RGB)],
        "assembly": [(body, BODY_RGB), (pcb_panel(), PCB_RGB), (supercap(), CAP_RGB),
                     (Pos(0, 0, LID_LIFT) * lid, LID_RGB)],
    }
    for name, items in jobs.items():
        for path in _render(name, items, out_dir):
            print(path.relative_to(HERE))


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Generate the files and inspect every render**

Run: `cd enclosure && .venv/Scripts/python.exe build.py && .venv/Scripts/python.exe render.py`
Expected: 12 part files plus `assembly.glb` listed with sizes, then 20 PNG paths.

Open each PNG and confirm:
- body: angled vent slots on the front and both end walls, SMA hole on the left wall, four corner columns with holes, two ears, ledge and pegs in the pocket, divider with notch, supercap rails, sensor pads, wire notch in the sensor wall
- lids: panel recesses on top, lead slots only over the electronics bay, four countersinks, skirt, four posts
- coupon: ring with four pegs inside the fence, SMA tab, insert column
- assembly: board seated in the pocket, supercap on its rails, lid clear above

Fix anything that looks wrong in the module that owns it, rerun the full test suite, regenerate.

- [ ] **Step 7: Write `README.md`**

`enclosure/README.md`:

````markdown
# Sensor node enclosure

Parametric 3D-printed case for the rev 1.0 sensor node. Every dimension lives in
`params.py`. The design reasoning is in
`docs/superpowers/specs/2026-09-14-enclosure-design.md`.

## Files to print

| File | Part | Notes |
|---|---|---|
| `out/fit_coupon.3mf` | fit coupon | print this first, about 20 minutes |
| `out/body.3mf` | body | open side up |
| `out/lid_2panel.3mf` | lid for two MP3-37 panels | exported top face down |
| `out/lid_3panel.3mf` | lid for three panels | exported top face down |

STL and STEP copies sit next to each 3MF. Shaded views are in `out/renders/`.

Print in PETG or ASA, in a light colour. PLA softens in direct sun.
Use 0.2 mm layers, 4 perimeters and 20 to 25 percent infill. No supports.

## Check the fit coupon

Press the PCB panel, rails still attached, onto the coupon ring. Then try the
SMA bulkhead jack in the tab and melt one insert into the column.

| What you see | Change in `params.py` |
|---|---|
| Pegs do not line up with the tooling holes | adjust `TOOLING_HOLES`, or set `PEGS_ENABLED = False` |
| Panel binds against the fence | raise `PANEL_X` or `PANEL_Y` by the overlap |
| Panel slides more than 1 mm | lower `PANEL_X` or `PANEL_Y` |
| SMA jack does not pass | raise `SMA_D` and `SMA_FLAT` by 0.2 |
| Insert drops in loose, or will not start | change `INSERT_D` by 0.2 |

Then regenerate and print the body and a lid.

## Regenerate

```bash
python -m venv enclosure/.venv
enclosure/.venv/Scripts/python.exe -m pip install -r enclosure/requirements.txt
cd enclosure
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe build.py
.venv/Scripts/python.exe render.py
```

## Hardware per node

| Part | Qty |
|---|---|
| M3 x 8 countersunk screw | 4 |
| M3 heat-set insert, 5.7 mm long | 4 |
| SMA bulkhead jack to U.FL pigtail | 1 |
| Small zip tie | 2 |
| 3 mm closed-cell foam tape | about 50 cm |
| Thin double-sided tape | for panels and sensors |
| Neutral-cure silicone | for notches and spare slots |

## Assembly

1. Melt the four inserts into the corner columns with a soldering iron.
2. Fit the SMA jack through the left wall and plug the pigtail into JP1.
3. Stick the SHT41 on the left pad and the ENS160 on the right pad with foam tape.
4. Run the jumper wires through the notch in the sensor wall to J1, then seal the notch with silicone.
5. Lay the supercapacitor on its rails, pass a zip tie under it and around it, and route its leads through the divider notch to C9. Tie the leads to the anchor slot.
6. Press the PCB panel onto the pegs.
7. Stick foam tape along the top of every wall, including the sensor wall, and a foam square on each lid post.
8. Stick the panels into the lid recesses. Feed their leads through the slots to U5 and seal the slots. On the three-panel lid, bridge the front panel's tabs to the middle panel on top of the lid.
9. Screw the lid down.
````

- [ ] **Step 8: Run the whole suite and commit**

Run: `cd enclosure && .venv/Scripts/python.exe -m pytest -q`
Expected: `33 passed`.

```bash
git add enclosure/build.py enclosure/render.py enclosure/tests/test_build.py enclosure/README.md enclosure/out
git commit -m "Export print files and renders for the enclosure"
git push origin main
```

---

### Task 6: Browser viewer and hand-over

**Files:**
- Create: `enclosure/viewer.py`, `enclosure/viewer_template.html`
- Generated and committed: `enclosure/out/viewer.html`
- Modify: `docs/superpowers/specs/2026-09-14-enclosure-design.md` (status line)

**Interfaces:**
- Consumes: `enclosure/out/assembly.glb` from Task 5, whose top-level nodes are named `body`, `lid`, `pcb`, `supercap`.
- Produces: `viewer.main() -> Path`, which writes `out/viewer.html` with the GLB embedded as base64 in place of the single token `__GLB_BASE64__` in the template.

- [ ] **Step 1: Load the artifact design guidance**

Invoke the `artifact-design` skill. The Artifact tool requires it before any page is written.

- [ ] **Step 2: Write `viewer.py`**

`enclosure/viewer.py`:

```python
"""Embed out/assembly.glb into one self-contained HTML viewer at out/viewer.html.

Run from enclosure/ after build.py:  .venv/Scripts/python.exe viewer.py
"""
from __future__ import annotations

import base64
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOKEN = "__GLB_BASE64__"
LIMIT_BYTES = 15 * 1024 * 1024


def main() -> Path:
    glb = (HERE / "out" / "assembly.glb").read_bytes()
    template = (HERE / "viewer_template.html").read_text(encoding="utf-8")
    if template.count(TOKEN) != 1:
        raise RuntimeError(f"viewer_template.html must contain {TOKEN} exactly once")
    html = template.replace(TOKEN, base64.b64encode(glb).decode("ascii"))
    if len(html.encode("utf-8")) > LIMIT_BYTES:
        raise RuntimeError("viewer is over 15 MB; raise linear_deflection for the GLB in build.py")
    out = HERE / "out" / "viewer.html"
    out.write_text(html, encoding="utf-8")
    print(f"{out.relative_to(HERE)}  {out.stat().st_size / 1024:.0f} KB")
    return out


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write `viewer_template.html`**

The visual treatment follows the artifact-design guidance loaded in Step 1, so the markup is written at that point. The page must:

- set `<title>Sensor Node Enclosure</title>` in its first lines
- load `https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js`, then `https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js` and `https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js`, before any inline script
- hold the model as `const GLB = "__GLB_BASE64__";`, decode it with `Uint8Array.from(atob(GLB), c => c.charCodeAt(0)).buffer`, and load it with `new THREE.GLTFLoader().parse(buffer, "", onLoad, onError)`
- find nodes with `gltf.scene.getObjectByName(name)` for `lid`, `pcb` and `supercap`, and offer a lid control with three states, lifted, seated and hidden, where seated moves the lid down by 40 mm, plus show and hide toggles for the PCB and the supercap
- orbit, zoom and pan with `THREE.OrbitControls`, with a reset-view button that frames the whole model from its bounding box
- list the overall size, internal size and panel capacity next to the canvas: 121.4 x 104.8 x 39.0 mm overall, 116.6 x 100.0 x 33.6 mm inside, two or three MP3-37 panels
- show a readable error message in place of the canvas if WebGL or the loader fails
- define light and dark colour tokens and work at 400 px wide

If the model appears lying on its side, glTF's Y-up convention was not applied on export: rotate `gltf.scene` by `-Math.PI / 2` about X once after loading.

- [ ] **Step 4: Generate and check the page**

Run: `cd enclosure && .venv/Scripts/python.exe viewer.py`
Expected: `out\viewer.html` with a size under 15 000 KB.

- [ ] **Step 5: Publish the viewer**

Publish `enclosure/out/viewer.html` with the Artifact tool, favicon `📦`, icon `model`, description "Interactive 3D preview of the 3D-printed sensor node enclosure with lid, PCB and supercap toggles."

- [ ] **Step 6: Mark the spec as modelled and commit**

In `docs/superpowers/specs/2026-09-14-enclosure-design.md` replace the line
`Status: draft, waiting for review before any geometry is modelled`
with
`Status: approved 2026-09-14, modelled in enclosure/`.

```bash
git add enclosure/viewer.py enclosure/viewer_template.html enclosure/out/viewer.html docs/superpowers/specs/2026-09-14-enclosure-design.md
git commit -m "Add a browser viewer for the enclosure assembly"
git push origin main
```
