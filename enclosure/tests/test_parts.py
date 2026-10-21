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
