import math

import pytest
from build123d import Box, Plane, Polygon, Pos, Vector, extrude

import params as p
from coupon import RING_T, build_coupon
from shapes import MIN, board_keepout, cell, overlap, pcb_board, unsupported_faces


@pytest.fixture(scope="module")
def coupon():
    return build_coupon()


def test_reference_models_have_expected_volumes():
    assert pcb_board().volume == pytest.approx(p.BOARD.w * p.BOARD.d * p.BOARD_T, rel=1e-6)
    assert cell().volume == pytest.approx(math.pi * p.CELL_R ** 2 * p.CELL_L, rel=1e-3)
    assert overlap(pcb_board(), cell()) < 1e-9
    assert board_keepout().bounding_box().max.Z == pytest.approx(p.BOARD_TOP_Z + p.HEADER_H, abs=0.01)
    assert board_keepout().bounding_box().min.Z == pytest.approx(p.BOARD_TOP_Z, abs=0.01)


def test_board_keepout_leaves_the_post_landing_spots_free():
    keep = board_keepout()
    for x, y, _, tip in p.POSTS:
        assert not keep.is_inside(Vector(x, y, tip + 0.3))


def test_overhang_check_flags_a_flat_ceiling_and_passes_a_45_degree_one():
    flat = Box(30, 30, 10, align=MIN).cut(Pos(5, 5, -1) * Box(20, 20, 6, align=MIN))
    assert unsupported_faces(flat)
    prism = extrude(Plane.YZ.offset(-1) * Polygon((2, -1), (28, -1), (15, 12), align=None), amount=32)
    gable = Box(30, 30, 20, align=MIN).cut(prism)
    assert unsupported_faces(gable) == []
    bridge = Box(30, 30, 10, align=MIN).cut(Pos(5, 5, -1) * Box(20, 8, 6, align=MIN))
    assert unsupported_faces(bridge) == []


def test_coupon_is_one_valid_flat_solid_with_two_fences(coupon):
    assert coupon.is_valid and len(coupon.solids()) == 1
    (ruler, _), (export, _) = p.coupon_fences()
    for fence in (ruler, export):
        assert not coupon.is_inside(Vector(fence.cx, fence.cy, RING_T / 2))
        assert coupon.is_inside(Vector(fence.x0 + 1.0, fence.cy, RING_T / 2))
        assert coupon.is_inside(Vector(fence.x0 - 0.8, fence.cy, RING_T + p.BOARD_T))
    size = coupon.bounding_box().size
    assert size.X <= 120 and size.Y <= 120 and size.Z <= 12
    assert unsupported_faces(coupon) == []


from body import build_body  # noqa: E402
from shapes import cell_leads, sensor_keepout  # noqa: E402


@pytest.fixture(scope="module")
def body():
    return build_body()


def test_body_is_one_valid_solid(body):
    assert body.is_valid and len(body.solids()) == 1


def test_body_overall_size(body):
    bb = body.bounding_box()
    assert bb.min.X == pytest.approx(-p.EAR_OUT, abs=0.01) and bb.max.X == pytest.approx(p.BODY_X + p.EAR_OUT, abs=0.01)
    assert bb.min.Y == pytest.approx(-p.COLUMN_OUT, abs=0.01) and bb.max.Y == pytest.approx(p.BODY_Y + p.COLUMN_OUT, abs=0.01)
    assert bb.min.Z == pytest.approx(0.0, abs=0.01) and bb.max.Z == pytest.approx(p.BODY_Z, abs=0.01)


def test_body_leaves_room_for_board_cell_and_sensors(body):
    for ref in (pcb_board(), board_keepout(), cell(), cell_leads(), sensor_keepout()):
        assert overlap(body, ref) < 1e-3


def test_body_supports_are_solid(body):
    for ledge in p.LEDGES:
        assert body.is_inside(Vector(ledge.cx, ledge.cy, p.BOARD_BOTTOM_Z - 0.5))
    assert body.is_inside(Vector(p.FRONT_FENCE.cx, p.FRONT_FENCE.cy, p.Z_FLOOR + p.FENCE_H - 0.5))
    assert body.is_inside(Vector(p.TERMINAL_FENCE.cx, p.TERMINAL_FENCE.cy, p.Z_FLOOR + p.FENCE_H - 0.5))
    for v in p.VBLOCKS:
        assert body.is_inside(Vector(v.x0 + 1.0, v.cy, p.Z_FLOOR + 1.0))
        assert not body.is_inside(Vector(p.CELL_X, v.cy, p.CELL_AXIS_Z))
    for pad in (p.SHT41_PAD, p.ENS160_PAD):
        assert body.is_inside(Vector(pad.cx, pad.cy, p.Z_LOWER_FLOOR + p.SENSOR_PAD_H / 2))
    assert body.is_inside(Vector(p.SENSOR_INNER.cx + 20.0, p.SENSOR_INNER.y0 + 2.0, p.Z_BAND_TOP + 5.0))   # gable solid near the wall, clear of the lead slot
    assert not body.is_inside(Vector(p.SENSOR_INNER.cx, p.SENSOR_INNER.cy, p.Z_RIDGE - 1.0))         # open under the ridge
    assert body.is_inside(Vector(p.SENSOR_INNER.cx, p.SENSOR_INNER.cy, p.Z_RIDGE + 1.0))             # upper floor


def test_body_openings_are_open(body):
    assert not body.is_inside(Vector(p.SMA_X, p.BODY_Y - p.WALL / 2, p.SMA_Z))
    for x, y in p.CHIMNEY_XY + p.CHANNEL_CHIMNEY_XY + p.CHANNEL_DRAIN_XY:
        assert not body.is_inside(Vector(x, y, p.Z_FLOOR - 0.5))
    assert not body.is_inside(Vector(p.CHANNEL_SLOT_RECT.cx, p.CHANNEL_SLOT_RECT.cy, p.Z_FLOOR - 10.0))
    for wall, c in p.NOTCHES:
        x, y = {"front": (c, p.WALL / 2), "back": (c, p.BODY_Y - p.WALL / 2),
                "left": (p.WALL / 2, c), "right": (p.BODY_X - p.WALL / 2, c)}[wall]
        assert not body.is_inside(Vector(x, y, p.BODY_Z - 1.0))
    for x, y in p.INSERT_XY:
        assert not body.is_inside(Vector(x, y, p.BODY_Z - 1.0))
    for y, z in p.SENSOR_DRAIN_YZ:
        assert not body.is_inside(Vector(p.LOUVRE_WALL / 2, y, z))
        assert not body.is_inside(Vector(p.BODY_X - p.LOUVRE_WALL / 2, y, z))
    for slot in p.EAR_SLOTS:
        assert not body.is_inside(Vector(slot.cx, slot.cy, p.EAR_T / 2))


def test_louvres_have_no_horizontal_path(body):
    x, z0 = p.LOUVRE_LONG_X[1], p.LOUVRE_ROWS_Z[1]
    for i in range(61):
        h = z0 - 6.0 + i * 0.2
        assert any(body.is_inside(Vector(x, y, h)) for y in (0.1, 1.0, 2.0, 3.0, 3.9)), h
    y, z0 = p.LOUVRE_END_Y[0], p.LOUVRE_ROWS_Z[0]
    for i in range(61):
        h = z0 - 6.0 + i * 0.2
        assert any(body.is_inside(Vector(x, y, h)) for x in (0.1, 1.0, 2.0, 3.0, 3.9)), h


def test_louvre_slots_are_open_at_the_wall_middle(body):
    for z in p.LOUVRE_ROWS_Z:
        for x in p.LOUVRE_LONG_X:
            assert not body.is_inside(Vector(x, p.LOUVRE_WALL / 2, z))
            assert not body.is_inside(Vector(x, p.BODY_Y - p.LOUVRE_WALL / 2, z))
        for y in p.LOUVRE_END_Y:
            assert not body.is_inside(Vector(p.LOUVRE_WALL / 2, y, z))
            assert not body.is_inside(Vector(p.BODY_X - p.LOUVRE_WALL / 2, y, z))


def test_body_prints_without_support(body):
    assert unsupported_faces(body) == []
