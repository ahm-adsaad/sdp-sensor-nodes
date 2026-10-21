import importlib
import math
import os

import pytest

import params as p

EXPORT = os.environ.get("ENCLOSURE_BOARD") == "export"
pinned = pytest.mark.skipif(EXPORT, reason="numbers pinned to the ruler outline")


@pinned
def test_body_size_matches_spec():
    assert (round(p.BODY_X, 1), round(p.BODY_Y, 1), round(p.BODY_Z, 1)) == (80.4, 51.4, 78.1)
    assert round(p.INNER_X, 1) == 75.6 and round(p.INNER_Y, 1) == 46.6
    assert round(p.GABLE_RISE, 1) == 21.7 and round(p.Z_FLOOR, 1) == 46.5


def test_layout_sums_front_to_back_and_left_to_right():
    assert p.CHANNEL.y0 == p.WALL and p.FRONT_FENCE.y0 == p.CHANNEL.y1
    assert p.POCKET.y0 == p.FRONT_FENCE.y1 and math.isclose(p.POCKET.y1, p.BODY_Y - p.WALL)
    assert p.POCKET.x0 == p.WALL and p.TERMINAL_FENCE.x0 == p.POCKET.x1
    assert p.WIRE_BAY.x0 == p.TERMINAL_FENCE.x1 and math.isclose(p.WIRE_BAY.w, p.WIRE_BAY_W)
    assert math.isclose(p.WIRE_BAY.x1, p.BODY_X - p.WALL)


def test_board_frame_puts_terminals_at_the_wire_bay_and_ufl_at_the_back_left():
    assert math.isclose(p.U11_XY[0], p.BOARD.x1 - p.TERMINAL_PIN_IN)
    assert p.U11_XY[1] > p.U9_XY[1]
    assert p.UFL_XY[0] < p.BOARD.x0 + 5 and p.UFL_XY[1] > p.BOARD.y1 - 8
    assert abs(p.SMA_X - p.UFL_XY[0]) < 10
    assert p.board_to_body(0.0, 0.0) == (p.BOARD.x1, p.BOARD.y1)


def test_ledges_clear_through_hole_pads():
    assert p.LEDGE_TOP + 2 * p.CLEARANCE < 3.09 and p.LEDGE_FRONT + 2 * p.CLEARANCE < 3.28
    assert len(p.LEDGES) == 3
    for ledge in p.LEDGES:
        assert p.POCKET.contains(ledge)


def test_posts_land_on_bare_board():
    (xt1, yt1, _, zt), (xt2, yt2, _, _), (xb, yb, db, zb) = p.POSTS
    assert zt == p.BOARD_TOP_Z + p.TERMINAL_H + p.POST_FOAM and zb == p.BOARD_TOP_Z + p.POST_FOAM
    for x, y in ((xt1, yt1), (xt2, yt2)):
        assert p.BOARD.contains_point(x, y)
    assert p.BOARD.x0 <= xb - db / 2 + 0.01 and xb + db / 2 <= p.BOARD.x0 + 3.9
    assert xb - db / 2 >= p.WALL + 0.25
    assert p.BOARD.y1 - 40.0 <= yb <= p.BOARD.y1 - 22.0


def test_cell_fits_the_wire_bay_and_reaches_u11():
    assert p.CELL_X - p.CELL_R >= p.WIRE_BAY.x0 + 0.5 and p.CELL_X + p.CELL_R <= p.WIRE_BAY.x1 - 0.5
    assert p.CELL_Y0 >= p.WALL + 0.5 and p.CELL_Y1 <= p.BODY_Y - p.WALL - 0.5
    assert math.isclose(p.CELL_X - p.WIRE_BAY.x0, p.CELL_BEND_ROOM + p.CELL_R)
    run = (p.CELL_X - p.BOARD.x1) + 5.0 + 3.0
    assert run <= 22.0
    assert math.isclose(p.CELL_AXIS_Z - p.Z_FLOOR, p.CELL_R * math.sqrt(2))


def test_chimney_holes_avoid_the_board_and_leave_a_web_for_the_zip_tie():
    for x, y in p.CHIMNEY_XY + p.CHANNEL_CHIMNEY_XY:
        assert not p.POCKET.inset(-p.CHIMNEY_D / 2).contains_point(x, y)
    xs = sorted(x for x, _ in p.CHIMNEY_XY)
    assert len(xs) == 2
    for a, b in zip(xs, xs[1:]):
        assert b - a - p.CHIMNEY_D >= 3.0
    for x, y in p.CHIMNEY_XY:
        assert math.isclose(y, p.SENSOR_INNER.cy)
        assert p.WIRE_BAY.inset(p.CHIMNEY_D / 2 + 1.0).contains_point(x, y)


def test_channel_slot_sits_over_the_sensor_cavity():
    assert p.SENSOR_INNER.contains(p.CHANNEL_SLOT_RECT) and p.CHANNEL.contains(p.CHANNEL_SLOT_RECT)
    assert abs(p.CHANNEL_SLOT_RECT.cx - p.J3_XY[0]) < 1.0
    for x, y in p.CHANNEL_CHIMNEY_XY + p.CHANNEL_DRAIN_XY:
        assert p.SENSOR_INNER.contains_point(x, y) and p.CHANNEL.contains_point(x, y)


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


@pinned
def test_notches_avoid_columns_and_count():
    assert len(p.NOTCHES) == 12
    corner = p.COLUMN - p.WALL + p.NOTCH_W / 2
    for wall, c in p.NOTCHES:
        length = p.BODY_X if wall in ("front", "back") else p.BODY_Y
        assert corner <= c <= length - corner


@pinned
def test_lid_eaves_and_skirts():
    assert (round(p.LID.w, 1), round(p.LID.d, 1)) == (124.0, 75.4)
    assert math.isclose(p.LID.y1 - p.BODY_Y, p.EAVE_BACK) and math.isclose(-p.LID.y0, p.EAVE_FRONT)
    assert p.LID.inset(p.SKIRT_T).contains(p.LABYRINTH)
    assert p.LABYRINTH.inset(p.SKIRT_T).x0 <= p.COLUMN_ENV.x0 - p.LABYRINTH_GAP + 1e-6
    assert p.COLUMN_ENV.y1 + 0.4 <= p.LID.y1 - p.SKIRT_T


def test_back_eave_clears_a_hinged_whip():
    assert p.EAVE_BACK <= 10.0 and p.SMA_Z + p.SMA_D / 2 + 1.0 <= p.BODY_Z
    assert p.SMA_Z - p.SMA_D / 2 >= p.BOARD_TOP_Z + p.TERMINAL_H + 1.0


def test_sma_plug_nut_clears_the_lid_skirt():
    assert p.SMA_Z + p.SMA_PLUG_D / 2 + 0.5 <= p.LID_Z0 - p.SKIRT_DROP


def test_solar_lead_hole_sits_behind_the_wedge_front_wall():
    x, y = p.PV_HOLE_XY
    assert y - p.PV_HOLE_D / 2 >= p.WEDGE_ORIGIN[1] + p.CHEEK_T + 0.5
    assert p.WIRE_BAY.contains_point(x, y) and x + p.PV_HOLE_D / 2 < p.CELL_X - p.CELL_R


def test_wedge_sits_on_the_lid_over_the_body():
    x0, y0 = p.WEDGE_ORIGIN
    footprint = p.Rect(x0, y0 - p.FOOT_W, x0 + p.PLATE_L, y0 + p.WEDGE_SPAN_Y + p.FOOT_W)
    assert p.LID.inset(1.5).contains(footprint)
    assert math.isclose(x0 + p.PLATE_L / 2, p.BODY_X / 2) and math.isclose(y0 + p.WEDGE_SPAN_Y / 2, p.BODY_Y / 2)
    assert len(p.BOSS_XY) == 4
    for bx, by in p.BOSS_XY:
        assert p.LID.inset(p.SKIRT_T + 1.0).contains_point(bx, by)
        assert by < y0 or by > y0 + p.WEDGE_SPAN_Y        # feet turn outward, so the screws see open sky
    assert footprint.contains_point(*p.PV_HOLE_XY)


def test_coupon_has_two_fences():
    (ruler, ledges_r), (export, ledges_e) = p.coupon_fences()
    assert (round(ruler.w, 1), round(ruler.d, 1)) == (53.6, 38.6)
    assert (round(export.w, 1), round(export.d, 1)) == (58.6, 43.0)
    assert ruler.y1 + 3.0 <= export.y0 or export.y1 + 3.0 <= ruler.y0
    assert len(ledges_r) == 3 and len(ledges_e) == 3
    for ledge in ledges_e:
        assert export.contains(ledge)


def test_export_outline_regenerates():
    os.environ["ENCLOSURE_BOARD"] = "export"
    try:
        mod = importlib.reload(p)
        assert mod.BOARD_X == 58.0 and mod.BODY_X > 80.4
        assert mod.POSTS[2][0] - mod.POSTS[2][2] / 2 >= mod.WALL + 0.25
    finally:
        os.environ.pop("ENCLOSURE_BOARD")
        importlib.reload(p)
    assert p.BOARD_X == 53.0
