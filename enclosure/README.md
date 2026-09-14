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
