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


from body import build_body


@pytest.fixture(scope="module")
def body():
    return build_body()


def test_body_is_one_valid_solid(body):
    assert body.is_valid
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


from lid import build_lid


@pytest.fixture(scope="module", params=[2, 3], ids=["2panel", "3panel"])
def lid(request):
    return request.param, build_lid(request.param)


def test_lid_is_one_valid_solid(lid):
    _, part = lid
    assert part.is_valid
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
