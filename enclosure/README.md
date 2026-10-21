# Sensor node enclosure, rev 2

Parametric 3D-printed case for the rev-2 sensor node: a louvred sensor shield
under a chimney-vented electronics body, a lid with eaves, and a wedge that
carries one PowerFilm MP3-37 at 45 degrees. Every dimension lives in
`params.py`. The design reasoning is in
`docs/superpowers/specs/2026-10-21-enclosure-rev2-design.md`.

This is a prototype pending a fit print and outdoor testing. See
[fit review](FIT_REVIEW.md) for what the coupon settles and what it cannot.

## Files to print

| File | Part | Orientation | Notes |
|---|---|---|---|
| `out/fit_coupon.3mf` | fit coupon | flat | print this first, about 25 minutes |
| `out/body.3mf` | body | open side up | the tallest print, about 78 mm |
| `out/lid.3mf` | lid | exported top face down | |
| `out/wedge.3mf` | panel wedge | exported feet down | |

STL and STEP copies sit next to each 3MF. Shaded views are in `out/renders/`
and the browser viewer is `out/viewer.html`.

Print in PETG or ASA, in a light colour; PLA softens in direct sun. Use 0.2 mm
layers, four perimeters and 20 to 25 percent infill. No part needs support: a
test checks every downward face in print orientation is on the bed, slopes at
45 degrees or more, or bridges at most 10 mm. The panel wedge's underside and
the body's gable ceiling are exactly 45 degrees, so keep part cooling on.

## Check the fit coupon

The coupon has two board pockets because the board's size is in dispute: the
front pocket is the 53 x 38 mm ruler reading, the back pocket is the 58.0 x
42.4 mm fabrication export. Drop the bare board into whichever takes it, then
sit the cell on the V-blocks, try the SMA jack in the tab and melt one insert
into the column.

| What you see | Change in `params.py` |
|---|---|
| Only the back pocket takes the board | `BOARD_X, BOARD_Y = 58.0, 42.4` (or set `ENCLOSURE_BOARD=export` when regenerating) |
| Board binds in its pocket | raise `BOARD_X` or `BOARD_Y` by the overlap |
| Board slides more than 1 mm | lower `BOARD_X` or `BOARD_Y` |
| A ledge touches a pin tail | lower `LEDGE_TOP`, `LEDGE_FRONT` or `LEDGE_BOTTOM` |
| Cell rocks on the V-blocks or binds | `CELL_D` |
| SMA jack does not pass | raise `SMA_D` and `SMA_FLAT` by 0.2 |
| Insert drops in loose, or will not start | change `INSERT_D` by 0.2 |

Also look at where the lid's three posts will land on the real board: two on
top of the screw terminals, one on the bare strip along the bottom edge
(the U.FL edge), 2 mm in from the edge and 11 mm from the right corner. If a
part sits there, move `POST_BOARD_ALONG`.

Then regenerate and print the body, lid and wedge.

## Regenerate

```bash
python -m venv enclosure/.venv
enclosure/.venv/Scripts/python.exe -m pip install -r enclosure/requirements.txt
cd enclosure
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe build.py
.venv/Scripts/python.exe render.py
.venv/Scripts/python.exe viewer.py
```

## Hardware per node

| Part | Qty |
|---|---|
| M3 x 8 countersunk screw | 4, lid |
| M3 x 12 countersunk screw | 4, wedge |
| M3 heat-set insert, 5.7 mm long | 8 |
| SMA bulkhead jack to U.FL pigtail | 1 |
| Small zip tie | 1 |
| 3 mm closed-cell foam tape | about 10 cm, for the three lid posts |
| Thin double-sided tape | panel and sensor breakouts |
| Neutral-cure silicone | the spare lead slot in the wedge |
| Fibreglass insect mesh, optional | glued inside the louvres against dust and insects |

## Assembly

1. Melt four inserts into the body's corner columns from the top and four
   into the lid from its top face, where the boss holes open; the holes go
   right through the bosses.
2. Fit the SMA jack through the hole in the back wall, near the left end, and
   plug the pigtail onto JP2.
3. Stick the SHT41 on the left pad and the ENS160 on the right pad inside the
   shield under the body, on foam tape. Feed their Dupont leads up through the
   slot in the front channel one plug at a time and onto J3.
4. Drop the board into its pocket, terminal edge toward the wire bay, U.FL
   corner at the back left. It rests on ledges under three edges.
5. Lay the cell on the V-blocks in the wire bay, leads at the back. Pass the
   zip tie down one of the two square chimney holes between the blocks and
   up the other, round the web, then over the cell. Trim the leads and screw
   them into U11; the shorter (-) lead reaches at its nominal length and
   wants a soldered extension if it comes up short.
6. Stick foam squares on the three lid posts.
7. Stick the panel inside the wedge's rim with its leads through the nearer
   slot, seal the other slot, and screw the wedge to the lid with four
   M3 x 12 screws; all four screw heads sit outside the wedge, in open
   sight. Feed the leads through the lid hole, which sits just behind the
   wedge's front wall, to U9, and seal the hole with silicone.
8. Screw the body's ears to the ledge, or zip tie them, with the lid off.
9. Screw the lid down with four M3 x 8 screws.

Face the panel's low edge, the diamond-vented side, toward the sun. The
antenna stands behind the panel's high edge.
