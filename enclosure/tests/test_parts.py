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
    assert coupon.is_valid
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
