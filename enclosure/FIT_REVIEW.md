# Fit review, rev 2 — 21 October 2026

The model uses the user's ruler reading of the rev-2 board, 53 x 38 x 1.6 mm,
with no rails and no mounting holes. The fabrication export says 58.0 x
42.4 mm, and its solar terminal body alone spans 30 to 40 mm along the
terminal edge, which cannot sit on a 38 mm edge. One of the two numbers is
wrong, and the coupon's two pockets decide which before anything else is
printed.

## Layout and size

| Feature | Model dimensions (mm) |
|---|---|
| Body walls, excluding ears and corner columns | 80.4 x 51.4 x 78.1 |
| Lid | 124 x 75.4 x 3, eaves 21.8 at the ends, 15 at the front, 9 at the back |
| Panel wedge | 120 long, 29.7 deep, 37.7 tall at the back, 8 mm air under the front edge |
| Complete nominal envelope, lid and wedge fitted | 124 x 75.4 x 119 plus ears |
| Board pocket | 53.6 x 38.6, ledges 3.5 / 2.2 / 2.2 under three edges |
| Clearance above the board | 26 |
| Wire bay | 20 x 46.6, cell axis 10.5 mm from the terminal fence |
| Sensor cavity | 72.4 x 43.4, 20 mm at the walls, 37.7 at the ridge flat |
| Louvres | two rows, 2.5 mm slots at 45 degrees in 4 mm walls, about 660 mm² |
| Eave vents | twelve 10 x 4 mm notches under the lid |

## Check before a full print

- Print the coupon first and report which pocket takes the board. If it is
  the back one, change `BOARD_X` and `BOARD_Y` to 58.0 and 42.4 and
  regenerate; every other number follows.
- The ledges clear the through-hole pads by 0.3 mm (terminal edge) and
  0.2 mm (front edge) at the worst pocket position. A board that rocks on a
  pin tail wants a narrower ledge, not a deeper pocket.
- The hold-down posts land on the two screw terminals and on the bare strip
  along the bottom edge. Those positions were read off the export; check
  them on the real board before printing the lid.
- The cell's (-) lead is 19 to 25 mm long and the run into U11 is about
  21 mm. Have 15 mm of insulated wire and heat-shrink ready.
- The Dupont housings on J3 stand about 16.5 mm; the lid gives 26 mm above
  the board. Housings on the breakouts in the shield get 37.7 mm at the
  ridge and 20 mm at the walls; keep the breakouts under the ridge.
- The SMA hole assumes a 6.5 mm barrel with a 6.0 mm flat, 11.5 mm below
  the wall top, and a plug coupling nut no wider than 9 mm, which then
  passes 0.5 mm under the lid's drip skirt. A fatter nut needs a lower hole
  (`SMA_BELOW_TOP`). A hinged whip's pivot sits 15 to 20 mm off the wall and
  stands up past the 9 mm back eave; a straight whip lies under it.
- The board hold-down post clears the LoRa module's castellations by
  0.2 mm at nominal and the board can shift 0.3 mm in its pocket; look at
  where it lands on the coupon. The back drip skirt clears the back
  columns by 0.8 mm, tight for an untuned printer.
- The panel's terminal end is still unknown. Both ends of the rim window
  have a lead slot; seal the spare one.

## What the model does not verify

The vents, drains and eaves are rain mitigation, not a demonstrated ingress
rating. Keep the lid up and the drains down. The shield gives the SHT41
shaded outside air, but the reading should still be compared against a
reference thermometer in the sun before it is trusted, with the ENS160
running. Dust will come in through louvres this open; mesh is optional
hardware. The CAD tests cover solid validity, interference against
reference models of the board, cell, sensors and panel, the louvre
line-of-sight rule and print-orientation overhangs. They do not establish
printed fit, RF performance, sensor accuracy or the temperature the case
reaches in Sharjah sun; the first outdoor run does that.
