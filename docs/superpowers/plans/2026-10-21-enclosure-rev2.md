# Sensor Node Enclosure Rev 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the September enclosure model with a rev-2 case (louvred sensor shield under a chimney-vented electronics body, lid, 45-degree panel wedge, two-outline fit coupon) and export print files, renders and a viewer from the same parametric build123d project.

**Architecture:** `params.py` holds every dimension and the derived 2D/Z layout as plain Python with no CAD imports, so the layout rules test in milliseconds. One module per printed part turns that layout into a build123d solid. `build.py` exports in print orientation and `render.py` draws views; pytest checks layout, validity, interference against reference solids of the board, cell, sensors and panel, the louvre line-of-sight rule, and an overhang check on every part in its print orientation.

**Tech Stack:** Python 3.13, build123d 0.11.1 (OpenCASCADE), pytest, matplotlib. Existing venv at `enclosure/.venv`.

**Spec:** `docs/superpowers/specs/2026-10-21-enclosure-rev2-design.md`

## Global Constraints

- Units mm. Frame: X left to right along the panel, Y front (panel low edge, sun side) to back, Z up. Origin: outer front-left bottom corner of the body walls at ground level.
- Run Python as `enclosure/.venv/Scripts/python.exe`; tests with `cd enclosure && .venv/Scripts/python.exe -m pytest`.
- Walls and floors 2.4 mm, louvre walls 4.0 mm, fences 2.0 mm, pocket clearance 0.3 mm a side, inserts 4.0 x 6.5 mm.
- Board modelled at 53 x 38 x 1.6 mm (ruler), export outline 58.0 x 42.4 kept for the coupon's second fence. Board feature positions are measured from the nearest board edge, as in the spec's feature table.
- No supports: every downward face in print orientation is on the bed, slopes 45 degrees or steeper, or spans at most 10 mm in one horizontal direction. A test enforces this on every exported part.
- `enclosure/out/` stays committed. The September `lid_1panel`, `lid_2panel`, `lid_3panel` files are removed.
- Commits short and plain, no co-author trailer, pushed to `origin main` after each task.

## Review Focus

1. A real board 58.0 x 42.4 instead of 53 x 38: the coupon's second fence must take it and the body must regenerate from two parameter changes with every test still passing. Test in Task 1 (`test_export_outline_regenerates`) and Task 2 (`test_coupon_has_two_fences`).
2. A cell at Eaton's maximum, 10.5 dia x 42 long: it must clear the fence, the back wall, the V-blocks and the lid. Test in Task 3 (`test_body_leaves_room_for_cell`) with the reference cell built at maximum size.
3. The three hold-down posts must land on bare board: the terminal posts above the 10 mm terminal bodies, the board post inside the bare bottom-edge strip and clear of the wall. Test in Task 1 (`test_posts_land_on_bare_board`) and Task 4 (`test_lid_clears_body_and_board_keepout`).
4. Rain: no horizontal line of sight through any louvre slot, and no straight vertical path from the lid's eave gap into the cavity. Test in Task 3 (`test_louvres_have_no_horizontal_path`).
5. A hinged whip on the SMA must stand past the back eave: the back eave is at most 10 mm from the wall face. Test in Task 1 (`test_back_eave_clears_a_hinged_whip`).

---

### Task 1: Layout parameters

**Files:**
- Rewrite: `enclosure/params.py`
- Rewrite: `enclosure/tests/test_params.py`

**Interfaces:**
- Consumes: nothing.
- Produces: module `params` keeping `Rect` unchanged (`x0 y0 x1 y1 w d cx cy inset contains contains_point centred`). Free values named exactly: `WALL LOUVRE_WALL DIVIDER CLEARANCE BOARD_X BOARD_Y BOARD_T BOARD_X_EXPORT BOARD_Y_EXPORT TERMINAL_H HEADER_H ABOVE_BOARD BOARD_STANDOFF LEDGE_BOTTOM LEDGE_TOP LEDGE_FRONT FENCE_H FRONT_CHANNEL WIRE_BAY CELL_BEND_ROOM CELL_D CELL_L CELL_LEAD_P CELL_LEAD_D VBLOCK_T SHT41 ENS160 SENSOR_PAD_H SENSOR_FOAM_T SENSOR_BOARD_T SENSOR_HOUSING_H LOUVRE_BAND SLOT_H SLOT_PITCH SLOT_L_LONG SLOT_L_END SLOT_WEB DRAIN_D CHIMNEY_D CHANNEL_SLOT CHANNEL_CHIMNEY_D GABLE_ANGLE EAVE_X EAVE_FRONT EAVE_BACK LID_T SKIRT_T SKIRT_DROP LABYRINTH_GAP NOTCH_W NOTCH_D NOTCH_PITCH COLUMN INSERT_D INSERT_DEPTH SCREW_D CSK_D EAR_OUT EAR_W EAR_T EAR_SLOT POST_FOAM POST_D_BOARD POST_D_TERMINAL BOSS_D BOSS_H PV_HOLE_D SMA_D SMA_FLAT SMA_X SMA_BELOW_TOP PANEL_ANGLE PLATE_L PLATE_W PLATE_T FRONT_LIFT CHEEK_T FOOT_L FOOT_W FOOT_T RIM_W RIM_H PV_L PV_W PV_T PV_CLR PV_SLOT DIAMOND DIAMOND_PITCH`, with the values in the spec (board 53/38, terminals 10 tall, `HEADER_H = 26`, `ABOVE_BOARD = 26`, `LEDGE_BOTTOM/TOP/FRONT = 3.5/2.2/2.2`, `FENCE_H = 8`, `FRONT_CHANNEL = 6`, `WIRE_BAY = 20`, `CELL_BEND_ROOM = 5`, cell 10.5 x 42, `LOUVRE_BAND = 20`, slots 2.5 tall on 8.5 pitch, 14 and 12 long with 5 webs, `GABLE_ANGLE = 45`, eaves 21.8 / 15 / 9, notches 10 x 4 on 16, `SMA_X = 10`, `SMA_BELOW_TOP = 7`, plate 120 x 42 x 2.4, `FRONT_LIFT = 8`, feet 10 x 8 x 4, rim 1.5 x 0.6, panel 114 x 36.5 x 0.22, diamonds 5 on 9).
- Board feature offsets, from the export: `TERMINAL_PIN_IN = 4.19`, `TERMINAL_ALONG = ((6.14, 11.14), (32.3, 37.3))` (U11, U9 pins from the left corner), `TERMINAL_BODY = (10.0, 7.6)`, `J3_IN = (18.16, 20.70)` (from the top, on the right edge), `J4_IN = (23.62, 26.16)` (left edge), `UFL_FROM_LEFT = 6.1`, `UFL_FROM_BOTTOM = 2.4`, `LORA = (11.4, 27.0, 36.8, 54.1)` (left, right, top, bottom from the top-left corner), `POST_BOARD_IN = 2.0` (from the bottom edge), `POST_BOARD_ALONG = 11.4` (from the right corner), `BARE_BOTTOM_STRIP = (22.0, 40.0, 3.9)` (from the left corner, depth).
- Derived Z: `Z_LOWER_FLOOR = WALL`, `Z_BAND_TOP`, `GABLE_RISE`, `Z_RIDGE`, `Z_FLOOR` (top of the upper floor), `BOARD_BOTTOM_Z`, `BOARD_TOP_Z`, `BODY_Z`, `CELL_R`, `CELL_AXIS_Z = Z_FLOOR + CELL_R * sqrt(2)`, `POST_TIP_BOARD_Z = BOARD_TOP_Z + POST_FOAM`, `POST_TIP_TERMINAL_Z = BOARD_TOP_Z + TERMINAL_H + POST_FOAM`, `SMA_Z = BODY_Z - SMA_BELOW_TOP`, `LID_Z0 = BODY_Z`, `LID_Z1 = BODY_Z + LID_T`.
- Derived XY: `POCKET_X POCKET_Y INNER_X INNER_Y BODY_X BODY_Y`; rects `CAVITY CHANNEL FRONT_FENCE TERMINAL_FENCE POCKET BOARD WIRE_BAY SENSOR_INNER SHT41_PAD ENS160_PAD SHT41_BOARD ENS160_BOARD LID COLUMN_ENV LABYRINTH`; tuples `LEDGES` (three rects), `COLUMNS`, `INSERT_XY`, `EARS`, `EAR_SLOTS`, `VBLOCKS` (two rects spanning the wire bay, 4 mm in Y, at `CELL_Y0 + 8` and `CELL_Y0 + 34`), `CHIMNEY_XY` (three in the wire bay at the ridge), `CHANNEL_CHIMNEY_XY` (two), `CHANNEL_DRAIN_XY` (two), `SENSOR_DRAIN_YZ` (two per end wall), `NOTCHES` (list of `(wall, centre)` with wall in `front back left right`), `LOUVRE_ROWS_Z`, `LOUVRE_LONG_X`, `LOUVRE_END_Y`, `POSTS` (three `(x, y, d, tip_z)`), `TERMINAL_XY` (two U-centres), `U9_XY`, `U11_XY`, `J3_XY`, `UFL_XY`, `BOSS_XY` (four), `CELL_X`, `CELL_Y0`, `CELL_Y1`, `CELL_LEAD_END = "back"`, `CHANNEL_SLOT_RECT`, `PV_HOLE_XY`, `WEDGE_ORIGIN = (x, y)` (front-left foot corner on the lid, centred on the body), `WEDGE_SPAN_Y`, `WEDGE_RISE`, `SMA_Y = BODY_Y`.
- Functions: `board_to_body(bx, by) -> (x, y)` with `x = BOARD.x1 - by`, `y = BOARD.y1 - bx`; `board_zone(left, right, top, bottom) -> Rect` clipped to `BOARD`; `coupon_fences() -> ((Rect, ledges), (Rect, ledges))` for the ruler and export outlines side by side front to back.

- [ ] **Step 1: Write the failing layout tests** in `tests/test_params.py`, replacing the September file:

```python
def test_body_size_matches_spec():
    assert (round(p.BODY_X, 1), round(p.BODY_Y, 1), round(p.BODY_Z, 1)) == (80.4, 51.4, 78.1)
    assert round(p.INNER_X, 1) == 75.6 and round(p.INNER_Y, 1) == 46.6
    assert round(p.GABLE_RISE, 1) == 21.7 and round(p.Z_FLOOR, 1) == 46.5

def test_layout_sums_front_to_back_and_left_to_right():
    assert p.CHANNEL.y0 == p.WALL and p.FRONT_FENCE.y0 == p.CHANNEL.y1
    assert p.POCKET.y0 == p.FRONT_FENCE.y1 and math.isclose(p.POCKET.y1, p.BODY_Y - p.WALL)
    assert p.POCKET.x0 == p.WALL and p.TERMINAL_FENCE.x0 == p.POCKET.x1
    assert p.WIRE_BAY.x0 == p.TERMINAL_FENCE.x1 and math.isclose(p.WIRE_BAY.w, p.WIRE_BAY_W if hasattr(p, "WIRE_BAY_W") else 20.0)

def test_board_frame_puts_terminals_at_the_wire_bay_and_ufl_at_the_back_left():
    assert math.isclose(p.U11_XY[0], p.BOARD.x1 - p.TERMINAL_PIN_IN)
    assert p.U11_XY[1] > p.U9_XY[1]
    assert p.UFL_XY[0] < p.BOARD.x0 + 5 and p.UFL_XY[1] > p.BOARD.y1 - 8
    assert abs(p.SMA_X - p.UFL_XY[0]) < 10

def test_ledges_clear_through_hole_pads():
    assert p.LEDGE_TOP + 2 * p.CLEARANCE < 3.09 and p.LEDGE_FRONT + 2 * p.CLEARANCE < 3.28
    for ledge in p.LEDGES:
        assert p.POCKET.contains(ledge)

def test_posts_land_on_bare_board():
    (xt1, yt1, _, zt), (xt2, yt2, _, _), (xb, yb, db, zb) = p.POSTS
    assert zt == p.BOARD_TOP_Z + p.TERMINAL_H + p.POST_FOAM and zb == p.BOARD_TOP_Z + p.POST_FOAM
    for x, y in ((xt1, yt1), (xt2, yt2)):
        assert p.BOARD.contains_point(x, y)
    strip_x0 = p.BOARD.x0
    assert strip_x0 <= xb - db / 2 + 0.01 and xb + db / 2 <= strip_x0 + 3.9
    assert xb - db / 2 >= p.WALL + 0.25
    assert p.BOARD.y0 + 22.0 - p.BOARD_Y + p.BOARD_Y <= yb <= p.BOARD.y1  # inside the 22..40 strip measured from the right corner

def test_cell_fits_the_wire_bay_and_reaches_u11():
    assert p.WIRE_BAY.inset(0.5).contains_point(p.CELL_X - p.CELL_R, p.CELL_Y0) and p.CELL_X + p.CELL_R <= p.WIRE_BAY.x1 - 0.5
    assert p.CELL_Y0 >= p.WALL + 0.5 and p.CELL_Y1 <= p.BODY_Y - p.WALL - 0.5
    assert math.isclose(p.CELL_X - p.WIRE_BAY.x0, p.CELL_BEND_ROOM + p.CELL_R)
    run = (p.CELL_X - p.BOARD.x1) + 5.0 + 3.0
    assert run <= 22.0

def test_chimney_holes_avoid_the_board():
    for x, y in p.CHIMNEY_XY + p.CHANNEL_CHIMNEY_XY:
        assert not p.POCKET.inset(-p.CHIMNEY_D / 2).contains_point(x, y)
    for x, y in p.CHIMNEY_XY:
        assert math.isclose(y, p.SENSOR_INNER.cy)

def test_channel_slot_sits_over_the_sensor_cavity():
    assert p.SENSOR_INNER.contains(p.CHANNEL_SLOT_RECT) and p.CHANNEL.contains(p.CHANNEL_SLOT_RECT)
    assert abs(p.CHANNEL_SLOT_RECT.cx - p.J3_XY[0]) < 1.0

def test_louvres_two_rows_inside_the_band():
    assert len(p.LOUVRE_ROWS_Z) == 2
    reach = p.SLOT_H / 2 / math.cos(math.radians(45)) + p.LOUVRE_WALL / 2 + 1.0
    for z in p.LOUVRE_ROWS_Z:
        assert p.Z_LOWER_FLOOR + reach <= z <= p.Z_BAND_TOP - reach
    assert len(p.LOUVRE_LONG_X) == 3 and len(p.LOUVRE_END_Y) == 2

def test_sensor_pads_sit_far_apart_under_the_ridge():
    assert p.SENSOR_INNER.contains(p.SHT41_PAD.inset(-1)) and p.SENSOR_INNER.contains(p.ENS160_PAD.inset(-1))
    assert p.ENS160_PAD.x0 - p.SHT41_PAD.x1 >= 25.0
    for pad in (p.SHT41_PAD, p.ENS160_PAD):
        assert math.isclose(pad.cy, p.SENSOR_INNER.cy)

def test_notches_avoid_columns_and_count():
    assert len(p.NOTCHES) == 12
    for wall, c in p.NOTCHES:
        if wall in ("front", "back"):
            assert p.COLUMN - p.WALL + p.NOTCH_W / 2 <= c <= p.BODY_X - (p.COLUMN - p.WALL) - p.NOTCH_W / 2

def test_lid_eaves_and_skirts():
    assert (round(p.LID.w, 1), round(p.LID.d, 1)) == (124.0, 75.4)
    assert math.isclose(p.LID.y1 - p.BODY_Y, p.EAVE_BACK) and math.isclose(-p.LID.y0, p.EAVE_FRONT)
    assert p.LID.inset(p.SKIRT_T).contains(p.LABYRINTH)
    assert p.LABYRINTH.inset(p.SKIRT_T).x0 <= p.COLUMN_ENV.x0 - p.LABYRINTH_GAP + 1e-6
    assert p.COLUMN_ENV.y1 + 0.4 <= p.LID.y1 - p.SKIRT_T

def test_back_eave_clears_a_hinged_whip():
    assert p.EAVE_BACK <= 10.0 and p.SMA_Z + p.SMA_D / 2 + 1.0 <= p.BODY_Z
    assert p.SMA_Z - p.SMA_D / 2 >= p.BOARD_TOP_Z + p.TERMINAL_H

def test_wedge_sits_on_the_lid_over_the_body():
    x0, y0 = p.WEDGE_ORIGIN
    assert p.LID.inset(1.5).contains(p.Rect(x0, y0, x0 + p.PLATE_L, y0 + p.WEDGE_SPAN_Y))
    assert math.isclose(x0 + p.PLATE_L / 2, p.BODY_X / 2) and math.isclose(y0 + p.WEDGE_SPAN_Y / 2, p.BODY_Y / 2)
    for bx, by in p.BOSS_XY:
        assert p.LID.inset(p.SKIRT_T + 1.0).contains_point(bx, by)
    assert p.Rect(x0, y0, x0 + p.PLATE_L, y0 + p.WEDGE_SPAN_Y).contains_point(*p.PV_HOLE_XY)

def test_coupon_has_two_fences():
    (ruler, ledges_r), (export, ledges_e) = p.coupon_fences()
    assert (round(ruler.w, 1), round(ruler.d, 1)) == (53.6, 38.6)
    assert (round(export.w, 1), round(export.d, 1)) == (58.6, 43.0)
    assert ruler.y1 + 3.0 <= export.y0 or export.y1 + 3.0 <= ruler.y0
    assert len(ledges_r) == 3 and len(ledges_e) == 3

def test_export_outline_regenerates(monkeypatch):
    import importlib
    monkeypatch.setattr(p, "BOARD_X", p.BOARD_X_EXPORT)
    monkeypatch.setattr(p, "BOARD_Y", p.BOARD_Y_EXPORT)
    mod = importlib.reload(p)
    try:
        assert mod.BODY_X > 80.4 and mod.POSTS[2][0] - mod.POSTS[2][2] / 2 >= mod.WALL + 0.25
    finally:
        importlib.reload(p)
```

Note on the last test: `monkeypatch` on module attributes does not survive `reload`; implement the override by reading `os.environ.get("ENCLOSURE_BOARD", "ruler")` in `params.py` to pick the outline, and have the test set the environment variable before reloading and clear it after.

- [ ] **Step 2: Run them to see them fail**

Run: `cd enclosure && .venv/Scripts/python.exe -m pytest tests/test_params.py -q`
Expected: errors on missing names.

- [ ] **Step 3: Write `params.py`** with the names and values in the Interfaces block. Louvre rows: rows at `Z_LOWER_FLOOR + reach + 0.3` and every `SLOT_PITCH` after while `z <= Z_BAND_TOP - reach`. Long-wall slot centres from the same packing rule as September's `_vent_front_x` with `SLOT_L_LONG`/`SLOT_WEB` over `SENSOR_INNER.w`; end walls with `SLOT_L_END` over `SENSOR_INNER.d`. Notches: per wall, centres on `NOTCH_PITCH` symmetric about the wall's middle, keeping `COLUMN - WALL + NOTCH_W / 2` from each corner. Chimney holes at `x = WIRE_BAY.x0 + (5.5, 12.25, 19.0)`, `y = SENSOR_INNER.cy`. `CELL_X = WIRE_BAY.x0 + CELL_BEND_ROOM + CELL_R`, `CELL_Y0 = WALL + 1.0`, `CELL_Y1 = CELL_Y0 + CELL_L`. Posts: `(BOARD.x1 - TERMINAL_PIN_IN, y of each terminal centre, POST_D_TERMINAL, POST_TIP_TERMINAL_Z)` and `(BOARD.x0 + POST_BOARD_IN, BOARD.y0 + POST_BOARD_ALONG, POST_D_BOARD, POST_TIP_BOARD_Z)`. `BOSS_XY`: `WEDGE_ORIGIN` plus `(CHEEK_T + FOOT_L / 2, FOOT_W / 2)` and the three mirrors in `PLATE_L` and `WEDGE_SPAN_Y`. `PV_HOLE_XY = (WIRE_BAY.x0 + CELL_BEND_ROOM / 2, U9_XY[1])`. `LABYRINTH = COLUMN_ENV.inset(-(LABYRINTH_GAP + SKIRT_T))` clipped to `LID.inset(SKIRT_T)`.

- [ ] **Step 4: Run the tests until they pass**

Run: `cd enclosure && .venv/Scripts/python.exe -m pytest tests/test_params.py -q`
Expected: all pass.

- [ ] **Step 5: Commit** `enclosure/params.py enclosure/tests/test_params.py docs/superpowers/specs/2026-10-21-enclosure-rev2-design.md docs/superpowers/plans/2026-10-21-enclosure-rev2.md` with message `lay out the rev-2 enclosure: louvred sensor shield, chimney body, tilted panel`.

---

### Task 2: Solid helpers, reference solids, overhang check, fit coupon

**Files:**
- Rewrite: `enclosure/shapes.py`
- Rewrite: `enclosure/coupon.py`
- Rewrite: `enclosure/tests/test_parts.py` (coupon and reference parts only in this task; body, lid and wedge tests are added in Tasks 3 and 4)

**Interfaces:**
- Consumes: `params` from Task 1.
- Produces in `shapes.py`: `EPS`, `MIN`, `CENTRE_BASE`, `slab(r, z0, z1)`, `rod(x, y, d, z0, z1)`, `sma_cutter(length)`, `vee_cutter(x, y, z_bottom, half_diag, thickness)` (a 45-degree-rotated square prism along Y, bottom vertex at `z_bottom`), `pcb_board()` (slab of `BOARD` from `BOARD_BOTTOM_Z` to `BOARD_TOP_Z`), `board_keepout()` (union: `BOARD.inset(3.9)` x `TERMINAL_H`; both terminal zones x `TERMINAL_H`; J3 and J4 zones x `HEADER_H`; LoRa zone x 3; U.FL zone x 5, all zones via `board_zone` and `board_to_body`), `cell()` (cylinder along Y, diameter `CELL_D`, from `CELL_Y0` to `CELL_Y1`, axis at `CELL_X`, `CELL_AXIS_Z`), `cell_leads()` (two 0.6 mm rods from the back end, length 27 and 22, bent is not modelled: straight along +Y then clipped at the wall is wrong, so model them as a 12 x 10 x 2 mm box above the cell's back end for clearance only), `sensor_boards()`, `sensor_keepout()` (boards plus `SENSOR_HOUSING_H`), `solar_panel()` (box `PV_L x PV_W x PV_T` on the wedge rim window, in the use frame, computed with the same transform as `wedge.py`), `overlap(a, b)`, `unsupported_faces(part, bed_z=0.0, max_bridge=10.0, min_slope_deg=45.0) -> list[tuple]` returning `(nz, size_x, size_y, z_min, area)` for faces with `nz < -cos(90 - min_slope) - 2e-3`, above the bed, with both horizontal extents greater than `max_bridge`.
- Produces in `coupon.py`: `RING_T = 2.0`, `FENCE_T = 1.6`, `build_coupon() -> Part`: two pocket fences from `coupon_fences()` each with its three ledges as a ring at `RING_T` and the three post landing spots marked as 0.4 mm raised discs; an SMA tab; an insert column; the two V-blocks with a 2 mm floor between them.

- [ ] **Step 1: Write the failing tests**

```python
def test_reference_models_have_expected_volumes():
    assert pcb_board().volume == pytest.approx(p.BOARD.w * p.BOARD.d * p.BOARD_T, rel=1e-6)
    assert cell().volume == pytest.approx(math.pi * p.CELL_R ** 2 * p.CELL_L, rel=1e-3)
    assert overlap(pcb_board(), cell()) < 1e-9
    assert board_keepout().bounding_box().max.Z == pytest.approx(p.BOARD_TOP_Z + p.HEADER_H, abs=0.01)

def test_overhang_check_flags_a_flat_ceiling_and_passes_a_45_degree_one():
    flat = Box(30, 30, 10, align=MIN).cut(Pos(5, 5, -1) * Box(20, 20, 6, align=MIN))
    assert unsupported_faces(flat)
    gable = Box(30, 30, 20, align=MIN).cut(extrude(Plane.YZ.offset(-1) * Polygon((2, -1), (28, -1), (15, 12), align=None), amount=32))
    assert unsupported_faces(gable) == []

def test_coupon_is_one_valid_flat_solid_with_two_fences(coupon):
    assert coupon.is_valid and len(coupon.solids()) == 1
    (ruler, _), (export, _) = p.coupon_fences()
    for fence in (ruler, export):
        assert not coupon.is_inside(Vector(fence.cx, fence.cy, RING_T / 2))
        assert coupon.is_inside(Vector(fence.x0 + 1.0, fence.cy, RING_T / 2))
    size = coupon.bounding_box().size
    assert size.X <= 120 and size.Y <= 120 and size.Z <= 10
    assert unsupported_faces(coupon) == []
```

- [ ] **Step 2: Run to see them fail** — `pytest tests/test_parts.py -q`, expected import errors.
- [ ] **Step 3: Write `shapes.py` and `coupon.py`** per the Interfaces block. For `cell_leads` keep it the clearance box as stated.
- [ ] **Step 4: Run to pass** — `pytest tests/test_parts.py -q`.
- [ ] **Step 5: Commit** `enclosure/shapes.py enclosure/coupon.py enclosure/tests/test_parts.py`, message `add the rev-2 reference solids, overhang check and two-outline fit coupon`.

---

### Task 3: Body

**Files:**
- Rewrite: `enclosure/body.py`
- Modify: `enclosure/tests/test_parts.py` (append)

**Interfaces:**
- Consumes: `params`, `shapes`.
- Produces: `build_body() -> Part` in the body frame, ground at z = 0.

- [ ] **Step 1: Write the failing tests** (append to `test_parts.py`, module-scoped `body` fixture):

```python
def test_body_is_one_valid_solid(body):
    assert body.is_valid and len(body.solids()) == 1

def test_body_overall_size(body):
    bb = body.bounding_box()
    assert bb.min.X == pytest.approx(-p.EAR_OUT, abs=0.01) and bb.max.X == pytest.approx(p.BODY_X + p.EAR_OUT, abs=0.01)
    assert bb.min.Y == pytest.approx(-(p.COLUMN - p.WALL), abs=0.01) and bb.max.Y == pytest.approx(p.BODY_Y + p.COLUMN - p.WALL, abs=0.01)
    assert bb.min.Z == pytest.approx(0.0, abs=0.01) and bb.max.Z == pytest.approx(p.BODY_Z, abs=0.01)

def test_body_leaves_room_for_board_cell_and_sensors(body):
    for ref in (pcb_board(), board_keepout(), cell(), cell_leads(), sensor_keepout()):
        assert overlap(body, ref) < 1e-3

def test_body_leaves_room_for_cell(body):
    assert overlap(body, cell()) < 1e-3   # cell built at Eaton's maximum 10.5 x 42

def test_body_supports_are_solid(body):
    for ledge in p.LEDGES:
        assert body.is_inside(Vector(ledge.cx, ledge.cy, p.BOARD_BOTTOM_Z - 0.5))
    assert body.is_inside(Vector(p.FRONT_FENCE.cx, p.FRONT_FENCE.cy, p.Z_FLOOR + p.FENCE_H - 0.5))
    assert body.is_inside(Vector(p.TERMINAL_FENCE.cx, p.TERMINAL_FENCE.cy, p.Z_FLOOR + p.FENCE_H - 0.5))
    for v in p.VBLOCKS:
        assert body.is_inside(Vector(v.x0 + 1.0, v.cy, p.Z_FLOOR + 1.0))
        assert not body.is_inside(Vector(p.CELL_X, v.cy, p.CELL_AXIS_Z))
    for pad in (p.SHT41_PAD, p.ENS160_PAD):
        assert body.is_inside(Vector(pad.cx, pad.cy, p.WALL + p.SENSOR_PAD_H / 2))
    assert body.is_inside(Vector(p.SENSOR_INNER.cx, p.SENSOR_INNER.y0 + 2.0, p.Z_BAND_TOP + 5.0))     # gable solid near the wall
    assert not body.is_inside(Vector(p.SENSOR_INNER.cx, p.SENSOR_INNER.cy, p.Z_RIDGE - 1.0))         # open under the ridge

def test_body_openings_are_open(body):
    assert not body.is_inside(Vector(p.SMA_X, p.BODY_Y - p.WALL / 2, p.SMA_Z))
    for x, y in p.CHIMNEY_XY + p.CHANNEL_CHIMNEY_XY + p.CHANNEL_DRAIN_XY:
        assert not body.is_inside(Vector(x, y, p.Z_FLOOR - 0.5))
    assert not body.is_inside(Vector(p.CHANNEL_SLOT_RECT.cx, p.CHANNEL_SLOT_RECT.cy, p.Z_FLOOR - 10.0))
    for wall, c in p.NOTCHES:
        x, y = {"front": (c, p.WALL / 2), "back": (c, p.BODY_Y - p.WALL / 2), "left": (p.WALL / 2, c), "right": (p.BODY_X - p.WALL / 2, c)}[wall]
        assert not body.is_inside(Vector(x, y, p.BODY_Z - 1.0))
    for x, y in p.INSERT_XY:
        assert not body.is_inside(Vector(x, y, p.BODY_Z - 1.0))
    for y, z in p.SENSOR_DRAIN_YZ:
        assert not body.is_inside(Vector(p.LOUVRE_WALL / 2, y, z))

def test_louvres_have_no_horizontal_path(body):
    x, z0 = p.LOUVRE_LONG_X[1], p.LOUVRE_ROWS_Z[1]
    for i in range(61):
        h = z0 - 6.0 + i * 0.2
        assert any(body.is_inside(Vector(x, y, h)) for y in (0.1, 1.0, 2.0, 3.0, 3.9)), h
    y, z0 = p.LOUVRE_END_Y[0], p.LOUVRE_ROWS_Z[0]
    for i in range(61):
        h = z0 - 6.0 + i * 0.2
        assert any(body.is_inside(Vector(x, y, h)) for x in (0.1, 1.0, 2.0, 3.0, 3.9)), h

def test_body_prints_without_support(body):
    assert unsupported_faces(body) == []
```

- [ ] **Step 2: Run to see them fail.**
- [ ] **Step 3: Write `body.py`**: `build_body()` = shell slab minus (sensor cavity box over `SENSOR_INNER` from `Z_LOWER_FLOOR` to `Z_BAND_TOP`, gable prism from a `Polygon` in `Plane.YZ` extruded over `SENSOR_INNER.w`, upper cavity over `CAVITY` from `Z_FLOOR`), fused with columns, ears, fences, ledges, V-blocks (slabs minus `vee_cutter`), sensor pads, then cut by: louvre slots (two rows, four walls, `Rot(45,0,0)` boxes on the front sloping down outward, mirrored on the back, `Rot(0,-45,0)`/`Rot(0,45,0)` on the ends, as September's `_vent_cutters`), eave notches, SMA cutter through the back wall at `(SMA_X, BODY_Y, SMA_Z)` with axis Y, channel slot, channel drains and chimneys, wire-bay chimneys, sensor drains (rods along X through each end wall at `SENSOR_DRAIN_YZ`), insert holes, ear slots.
- [ ] **Step 4: Run to pass.** If `unsupported_faces` reports the gable at `nz = -0.7071`, the tolerance in `shapes.py` is wrong, not the body.
- [ ] **Step 5: Commit** `enclosure/body.py enclosure/tests/test_parts.py`, message `model the rev-2 body with the louvred shield and gable floor`.

---

### Task 4: Lid and panel wedge

**Files:**
- Rewrite: `enclosure/lid.py`
- Create: `enclosure/wedge.py`
- Modify: `enclosure/tests/test_parts.py` (append)

**Interfaces:**
- Consumes: `params`, `shapes`, `build_body` for interference tests.
- Produces: `build_lid() -> Part` in the body frame (underside on `LID_Z0`); `build_wedge() -> Part` in the body frame, feet on `LID_Z1`, origin at `WEDGE_ORIGIN`; `wedge_transform() -> Location` shared with `shapes.solar_panel()` so the panel sits in the rim window.

- [ ] **Step 1: Write the failing tests**

```python
def test_lid_is_one_valid_solid(lid):
    assert lid.is_valid and len(lid.solids()) == 1

def test_lid_clears_body_and_board_keepout(lid, body):
    for other in (body, pcb_board(), board_keepout(), cell(), cell_leads()):
        assert overlap(lid, other) < 1e-3

def test_lid_posts_reach_their_tips(lid):
    for x, y, d, tip in p.POSTS:
        assert lid.is_inside(Vector(x, y, tip + 0.5)) and not lid.is_inside(Vector(x, y, tip - 0.5))

def test_lid_holes_and_bosses(lid):
    for x, y in p.INSERT_XY:
        assert not lid.is_inside(Vector(x, y, p.LID_Z0 + p.LID_T / 2))
    for x, y in p.BOSS_XY:
        assert lid.is_inside(Vector(x + p.BOSS_D / 2 - 0.5, y, p.LID_Z0 - p.BOSS_H / 2))
        assert not lid.is_inside(Vector(x, y, p.LID_Z1 - 1.0))
    assert not lid.is_inside(Vector(*p.PV_HOLE_XY, p.LID_Z0 + 1.0))

def test_lid_prints_without_support():
    printed = build.print_ready(build_lid(), flip=True)
    assert unsupported_faces(printed) == []

def test_wedge_is_valid_and_sits_on_the_lid(wedge, lid):
    assert wedge.is_valid and len(wedge.solids()) == 1
    bb = wedge.bounding_box()
    assert bb.min.Z == pytest.approx(p.LID_Z1, abs=0.01)
    assert overlap(wedge, lid) < 1e-3
    x0, y0 = p.WEDGE_ORIGIN
    assert wedge.is_inside(Vector(x0 + p.PLATE_L / 2, y0 + p.CHEEK_T / 2, p.LID_Z1 + 2.0))        # front wall
    assert not wedge.is_inside(Vector(x0 + p.PLATE_L / 2, y0 + p.WEDGE_SPAN_Y / 2, p.LID_Z1 + 3.0))  # air under the plate

def test_wedge_prints_without_support(wedge):
    assert unsupported_faces(build.print_ready(wedge, flip=False)) == []

def test_panel_sits_in_the_rim_window(wedge):
    panel = solar_panel()
    assert overlap(panel, wedge) < 1e-3
    assert panel.bounding_box().size.X == pytest.approx(p.PV_L, abs=0.01)
```

- [ ] **Step 2: Run to see them fail.**
- [ ] **Step 3: Write `lid.py` and `wedge.py`.** Lid: plate over `LID`, drip skirt ring at the edge, labyrinth ring over `LABYRINTH` (both `SKIRT_T` wide, `SKIRT_DROP` deep), posts from `POSTS`, bosses from `BOSS_XY` (`BOSS_D` x `BOSS_H` below `LID_Z0`), then cut countersunk screw holes at `INSERT_XY` (90-degree cone as in September), insert holes `INSERT_D x INSERT_DEPTH` from `LID_Z1` down at `BOSS_XY`, and the PV hole. Wedge: build in a local frame with the spike's construction (plate rotated by `PANEL_ANGLE` about X with its front-bottom edge at `(0, 0, FRONT_LIFT)`, trapezoid cheeks, front wall with diamonds, four feet, rim with the open low edge, two lead slots, countersunk foot holes), then `Pos(WEDGE_ORIGIN[0], WEDGE_ORIGIN[1], LID_Z1)`. Expose `wedge_transform()` and the plate's local frame so `solar_panel()` places `PV_L x PV_W x PV_T` on the plate's top face inside the rim.
- [ ] **Step 4: Run to pass.**
- [ ] **Step 5: Commit** `enclosure/lid.py enclosure/wedge.py enclosure/shapes.py enclosure/tests/test_parts.py`, message `model the rev-2 lid and the 45-degree panel wedge`.

---

### Task 5: Exports and renders

**Files:**
- Modify: `enclosure/build.py`, `enclosure/render.py`, `enclosure/tests/test_build.py`
- Delete: `enclosure/out/lid_1panel.*`, `lid_2panel.*`, `lid_3panel.*` and their renders
- Regenerate: `enclosure/out/*.stl|3mf|step`, `assembly.glb`, `out/renders/*.png`

**Interfaces:**
- Consumes: `build_body`, `build_lid`, `build_wedge`, `build_coupon`, reference solids.
- Produces: `parts() -> dict[str, tuple[Part, bool]]` with keys `body lid wedge fit_coupon` (only `lid` flips); `export_all() -> list[Path]`; assembly GLB with labelled, coloured children `body lid wedge pcb cell sensors panel`, lid, wedge and panel lifted by `LID_LIFT`.

- [ ] **Step 1: Update `test_build.py`**: expected part names `body lid wedge fit_coupon`; the lid test asserts `bb.size.Z == pytest.approx(p.LID_T + max post length)` where the longest post is `LID_Z0 - POST_TIP_BOARD_Z`.
- [ ] **Step 2: Update `build.py` and `render.py`** (jobs: `body lid wedge fit_coupon assembly`; assembly colours: body warm grey, lid blue-grey, wedge same as lid, pcb blue, cell dark, sensors green, panel near-black `(0.12, 0.12, 0.16)`).
- [ ] **Step 3: Run the full suite** — `pytest -q`, all pass.
- [ ] **Step 4: Export and render** — `git rm enclosure/out/lid_*panel.* enclosure/out/renders/lid_*panel_*.png`, then `.venv/Scripts/python.exe build.py` and `render.py`; look at `out/renders/assembly_front.png`, `body_under.png`, `wedge_front.png` and fix anything wrong before committing.
- [ ] **Step 5: Commit** `enclosure/build.py enclosure/render.py enclosure/tests/test_build.py enclosure/out`, message `export the rev-2 print files and renders`.

---

### Task 6: Viewer, docs, memory

**Files:**
- Modify: `enclosure/viewer.py`, `enclosure/viewer_template.html`, `enclosure/tests/test_viewer.py`, `enclosure/README.md`
- Rewrite: `enclosure/FIT_REVIEW.md` as the rev-2 fit review (what the coupon settles, what it cannot)

**Interfaces:**
- Consumes: `params`, `out/assembly.glb`.
- Produces: `viewer.PARTS = frozenset({"body", "lid", "wedge", "pcb", "cell", "sensors", "panel"})`, `labels()` with at least `SHT41 sensor`, `ENS160 sensor`, `Sensor leads`, `Circuit board`, `Cell`, `SMA antenna jack`, `Solar panel`, `Solar lead hole`, `Louvres`, `Eave vents`, `M3 insert`; template lifts lid, wedge and panel together; toggles for pcb, cell, sensors, panel; header reads rev 2, one panel at 45 degrees, issued 21 Oct 2026.

- [ ] **Step 1: Update `test_viewer.py`** for the new titles, parts and the body's bounds (`-EAR_OUT .. BODY_X + EAR_OUT`, `-(COLUMN - WALL) .. BODY_Y + COLUMN - WALL`, `0 .. LID_Z1 + WEDGE_RISE + FRONT_LIFT + 3`).
- [ ] **Step 2: Update `viewer.py` and the template**, run `pytest -q` (all pass), run `viewer.py`, publish `out/viewer.html` as a private artifact with the Artifact tool and check it renders by reading it back.
- [ ] **Step 3: Rewrite `README.md`** (files to print, coupon procedure with the two fences, regenerate, hardware with M3 x 12 for the wedge, assembly order from the spec) and `FIT_REVIEW.md`.
- [ ] **Step 4: Commit** `enclosure/viewer.py enclosure/viewer_template.html enclosure/tests/test_viewer.py enclosure/README.md enclosure/FIT_REVIEW.md enclosure/out/viewer.html`, message `add the rev-2 enclosure viewer and refresh the enclosure docs`, push.
- [ ] **Step 5: Update memory** `project-enclosure-inputs.md` with the rev-2 inputs, the ruler-versus-export conflict and the artifact URL.
