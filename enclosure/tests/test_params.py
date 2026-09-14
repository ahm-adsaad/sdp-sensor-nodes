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
