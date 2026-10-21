# Sensor node enclosure, rev 2 — design

Date: 2026-10-21
Status: written from the user's answers of 2026-10-21; supersedes
`2026-09-14-enclosure-design.md` for the rev-2 board.

## Goal

A 3D-printable case for one rev-2 sensor node that holds the bare rev-2 PCB,
one Eaton HS1040 lithium-ion capacitor, the SHT41 and ENS160 breakouts, and
one PowerFilm MP3-37 solar panel tilted at 45 degrees on top. It sits flat on
a ledge outdoors in Sharjah, where the bare node reached 40 to 50 C in the
sun, so the case must shade and ventilate the electronics and give the
humidity sensor outside air in the shade. Output is print-ready STL, 3MF and
STEP files plus renders and a browser viewer, generated from the existing
parametric build123d project in `enclosure/` so every dimension can be
changed and re-exported.

Out of scope: a waterproof rating, a pole or wall bracket, a light pipe for
the LED, the CO sensor on J2, and anything for more than one panel.

## What changed since the September design

| Item | September | Now |
|---|---|---|
| Board | rev-1 panel with rails, 72.0 x 71.4 mm | bare rev-2 board, no rails, no mounting holes |
| Storage | flat 65 x 38 x 18 mm pack | HS1040 cylinder, 10 x 40 mm, radial leads |
| Solar | up to three MP3-37 flat on the lid | one MP3-37 at 45 degrees on top |
| Sensors | vented bay at the front of the body | louvred shield under the body |
| Cooling | shaded vents on the sensor bay only | chimney through the whole case, panel shading the lid |
| Mounting | shelf or wall | flat on a ledge |

## Inputs and how sure we are

| Item | Value | Source | Confidence |
|---|---|---|---|
| Board outline, used for the model | 53 x 38 x 1.6 mm | user's ruler, 2026-10-21 | +/-1 mm, see open item 1 |
| Board outline, as exported for fabrication | 58.0 x 42.4 mm | PCB SVG of 2026-10-05, board-outline layer | exact for the export |
| Tallest part on the board | 10 mm, the two KF301 screw terminals | user and KF301 footprint | +/-0.5 mm |
| Parts near the edges | see the table below | PCB SVG pad list | exact for the export |
| HS1040 cell | body 10.0 +/-0.5 dia x 40.0 +/-2.0 mm; leads 0.6 mm dia on 5.0 mm pitch, 27 +/-3 mm (+) and 22 +/-3 mm (-) long, both at one end | Eaton TD 11043, Feb 2025, dimension table | exact; the user's 9 x 36 mm reading is inside the tolerance |
| MP3-37 panel | 114.0 x 36.5 x 0.22 mm, foil-tape terminals | PowerFilm Classic Application Series sheet 5/23 | exact; terminal position still unknown |
| SHT41 breakout | 25 x 17 mm | user, September | +/-1 mm |
| ENS160 breakout | 17 x 18 mm | user, September | +/-1 mm |
| Sensor wiring | Dupont jumper leads from the breakouts to the 2x2 header, both sensors on one bus | user, 2026-10-21; firmware uses rail A = J3 | — |
| Antenna | U.FL pigtail 80 mm to an SMA bulkhead jack, 70 mm whip | user, unchanged | — |
| Deployment | flat on a ledge, outdoors, bare node measured 40 to 50 C in the sun | user, 2026-10-21 | — |
| Printer | unknown; generic 0.4 mm FDM, no supports | September answer | — |

Board features, from the 2026-10-05 export. "Top" is the edge with the two
screw terminals; x runs left to right and y top to bottom with the
silkscreen upright. Distances are from the nearest board edge, which is what
the case uses, so they survive a different outline better than absolute
positions would.

| Feature | Where | Clearance to the edge |
|---|---|---|
| U11 storage terminal, KF301-5.0-2P | top edge, pins 6.1 and 11.1 mm from the left corner | body 0.4 to 8.0 mm from the top edge, 10 mm tall, wires enter from the top edge |
| U9 solar terminal, KF301-5.0-2P | top edge, pins 32.3 and 37.3 mm from the left corner | same |
| J3 sensor header, 2x2, bus A | right edge, 18 to 21 mm from the top | pins 3.3 mm in; plastic from about 2.8 mm in |
| J4 sensor header, 2x2, bus B | left edge, 23.6 to 26.2 mm from the top | pins 1.6 mm in; plastic from about 1.1 mm in |
| H4 and H5 six-pin headers | right edge 27.6 to 40.3 mm, left edge 29.3 to 42.0 mm from the top | H4 pins 5.1 mm in, H5 pins 1.5 mm in |
| JP2 U.FL antenna socket | bottom-left corner | pads 1.3 mm from the bottom edge, 4.1 to 8.1 mm from the left corner |
| SX1276 LoRa module | bottom-left quarter | castellations 4.0 mm from the bottom edge, 11.4 to 27 mm from the left corner |
| Two 0402 parts | bottom edge, 18.2 to 20.4 mm from the left corner | 0.7 mm from the edge |
| Bottom edge, 22 to 40 mm from the left corner | bare on top for at least 3.9 mm | — |
| Top edge | nothing through-hole closer than 3.1 mm (terminal pads) | — |
| Bottom edge | nothing through-hole at all | — |

## Decisions already made

- Follow the ruler: model the pocket for 53 x 38 mm, keep the outline as two
  parameters, and print the fit coupon before the body. The export says
  58.0 x 42.4 mm, and its U9 terminal body alone spans 29.8 to 39.8 mm along
  the terminal edge, which cannot sit on a 38 mm edge, so either the ruler
  reading is off by 5 mm on both axes or the board in hand came from a
  layout that is not in the repo. The coupon therefore carries two pocket
  fences, one for each outline, so one print settles it either way.
- Both sensors are fitted, on Dupont leads into J3.
- One panel only, at 45 degrees. The angle is a parameter.
- The node sits flat on a ledge. Two ears with slots take screws or a zip
  tie, fitted with the lid off.
- The antenna is unchanged: SMA bulkhead jack in a wall, pigtail to the U.FL.
- Same toolchain, same `enclosure/` project, rewritten rather than patched.
  The September print files are replaced; they only fit the rev-1 panel.
- Print in PETG or ASA, light colour, 0.4 mm nozzle, no supports anywhere.
  Every downward face is on the bed, slopes at 45 degrees or more, or is a
  bridge under 10 mm, and a test checks that on the exported solids.

## The shape

Four printed parts: body, lid, panel wedge, fit coupon. Frame: X left to
right along the panel's long side, Y front to back with the front being the
panel's low edge and the sun side, Z up. Origin at the outer front-left
bottom corner of the body walls at ground level.

```
                 ___________                panel wedge: MP3-37 on a 45 deg plate,
                /    panel   \              front edge 8 mm off the lid so air
               /______________\__           passes under the panel
      ________/_________________\________   lid, eaves 22 mm (ends), 15 mm (front), 9 mm (back),
      |  = = = eave vent notches = = =  |   drip skirt at the edge, labyrinth skirt
      |                                 |   round the walls
      |   PCB       |  cell   wire bay  |   electronics cavity, 31.6 mm clear
      |  __________ |________           |
      |  solid, 45 deg gable ceiling    |   solid wedge between the two cavities;
      |      /  chimney holes  \        |   printable without support
      |     /                   \       |
      |  ==/== louvred shield ===\===   |   sensor cavity: 45 deg slots in 4 mm walls,
      |  SHT41               ENS160     |   two rows, all four sides; floor drains
      |_________________________________|   ears with slots at both ends
```

Air enters the louvred sensor cavity at the bottom in the shade of the body
and lid, passes the two sensors, rises through the lead slot and holes in
the front channel and the wire bay into the electronics cavity (never under
the board, where the ledges would throttle it), and leaves through notches
in the wall tops under the lid. The panel plate shades the middle of the lid and stands off it, so
the hottest surface never touches the box. The cell sits on the floor at the
back, furthest from the sun-facing front wall.

## Body

One print, open side up, floor on the bed. Outer walls 2.4 mm, overall
80.4 x 51.4 mm and 78.1 mm tall plus corner columns. Height stack from the
ground: 2.4 floor, 20.0 louvre band, 21.7 gable (half the 43.4 mm sensor
cavity), 2.4 upper floor, 4.0 board standoff, 1.6 board, 26.0 above the
board. The gable is truncated 4 mm below its apex to an 8 mm flat ceiling,
under the 10 mm bridge limit, so the chimney holes pass through a plane
rather than a sharp ridge; the upper floor is 6.4 mm thick along that flat
and thicker everywhere else, so holes through it are 6.4 to 24 mm bores.
All chimney and drain holes are square, because the 3MF mesher mis-handled
the seams of round ones cut through this floor.

**Electronics cavity**, 75.6 x 46.6 x 31.6 mm inside. From front to back:

- A 6 mm **front channel** along the front wall. The Dupont leads from J3,
  which sits on the board's right edge facing the front, come down here into
  a 12 x 3.5 mm slot through the floor into the sensor cavity below, set
  back from the front wall so it clears the 4 mm louvre wall under it; a
  Dupont housing is 2.54 mm wide, so the leads go through one at a time.
  Two 3 mm drain holes and two 5 mm chimney holes along the channel.
- A 2 mm **fence**, 8 mm above the floor, with the front ledge on its board
  side. It stops the board and keeps the leads out of the pocket.
- The **board pocket**, 53.6 x 38.6 mm (board plus 0.3 mm a side), with the
  terminal edge facing right (+X) into the wire bay and the U.FL corner at
  the back left. Ledges 4 mm above the floor under three edges: 3.5 mm under
  the bottom edge (left end, nothing through-hole there), 2.5 mm under the
  terminal edge (pads start 3.1 mm in) and 2.5 mm under the front edge (J3
  pads start 3.3 mm in). No ledge under the back edge, where J4 and H5 pins
  sit 1.5 mm from the edge; the divider there is a side guide only. Pin
  tails up to 3.5 mm long clear the 4 mm standoff. A 2 mm **terminal fence**,
  8 mm above the floor, closes the terminal end so the board cannot slide
  off its ledge; the terminals' wire entries sit above it. The pocket's back
  edge is the back wall itself.
- The **wire bay**, 20 mm clear beyond the terminal fence, full depth, so
  the cavity is 6 + 2 + 38.6 = 46.6 mm deep and 53.6 + 2 + 20 = 75.6 mm
  long. The HS1040 lies here along Y on two 45-degree V-blocks that hold
  it 2 mm off the floor, its axis 10.5 mm from the fence (5 mm of bend room
  for the terminal wires, cell radius 5.5), leads at the back end bending
  toward U11. A zip tie passes under the cell between the blocks; no groove
  is needed. Lead reach, from the Eaton tolerances: the run from the cell
  end to the inside of U11's clamp is about 21 mm, the (+) lead is 24 to
  30 mm and reaches, the (-) lead is 19 to 25 mm and reaches at nominal
  length but may need a soldered 15 mm extension on a short one. The solar
  leads drop from the lid hole, which sits over the 5 mm gap between the
  fence and the cell, straight into U9 at the front.
- **Hold-down** from the lid: two 5 mm posts land on the two screw-terminal
  bodies through 3 mm foam, and one 3.5 mm post lands on the bare strip at
  the board's bottom edge, 2 mm in from the edge and 11.4 mm from the right
  corner (between the two 0402 parts and the corner); the strip is 3.9 mm
  deep, which a 4 mm post would overrun. With the lid off the board lifts
  straight out.
- **Chimney holes**: three 6 mm holes through the upper floor along the
  gable ridge under the wire bay, between the V-blocks, plus the two in the
  front channel. None under the board.
- **Antenna**: a 6.5 mm D-cut hole with a 6.0 mm flat through the back wall,
  10 mm from the left end's outer face so the nut clears the corner column,
  9 mm below the wall top, so the jack and nut clear the board, the header
  housings and the eave notches above. The lid's back eave is only 9 mm for this reason: a
  hinged whip's pivot sits 15 to 20 mm off the wall and must stand up past
  the eave and its skirt, and a straight whip lies horizontally under it. Either way the whip is behind
  the panel's high edge, out of its sun.
- **Eave vents**: 10 x 4 mm notches in the top of all four walls on a
  16 mm pitch, under the lid.

**Sensor cavity**, 72.4 x 43.4 mm inside, 20 mm tall at the walls and
37.7 mm under the ridge flat. Walls 4 mm thick with two rows of 45-degree slots sloping down
to the outside, 2.5 mm tall on an 8.5 mm pitch, 14 mm long on the long walls
and 12 mm on the ends, so no horizontal line of sight and no straight path
for rain; about 660 mm² of opening. SHT41 pad at the left end, ENS160 pad at
the right end, each 3 mm tall for foam tape, centred front to back under the
ridge where the headroom is. Two 3 mm drain holes through each end wall,
cut 0.5 mm into the floor so nothing pools. The ceiling is a 45-degree
gable with its ridge along X, which is why the upper floor needs no
support. The lowest slot row starts high enough that its outward slope
clears the mounting ears outside.

**Columns, ears, inserts.** Four 9 mm square columns on the outside corners
run from the ground to the top with a 4.0 x 6.5 mm hole for an M3 heat-set
insert (parameter: 2.6 mm pilot for self-tapping screws). Two ears, 12 mm
out and 20 mm wide at the left and right ends, 3 mm thick, with 8 x 4.5 mm
slots.

## Lid

A 3.0 mm plate, 124 x 75.4 mm, printed top face down: eaves of 21.8 mm at
the ends, 15 mm at the front and 9 mm at the back, the least that clears
the back columns with a drip skirt outside them. Underside: a 1.6 mm drip
skirt 6 mm deep round the edge; a 1.6 mm labyrinth skirt 6 mm deep round
the column envelope with a 2.5 mm air gap, so eave air enters under the
skirt and rain running off the lid cannot, merged into the drip skirt along
the back where there is no room for two; the three hold-down posts;
four 8 mm bosses, 5 mm deep, with 4.0 x 6.5 mm insert holes for the wedge
feet. The bosses overlap the labyrinth skirt at the ends and fuse with it.
Top: four countersunk 3.4 mm holes at the columns, and a 4 mm hole for the
solar leads over the gap between the terminal fence and the cell, at U9's
position, which puts it 11 to 14 mm from the front wall and under the panel
plate. The wedge is centred on the body, not the lid.

## Panel wedge

A right-triangular prism printed feet down. The sloped plate is
120 x 42 x 2.4 mm. The panel is located by a 0.6 mm raised rim, 1.5 mm
wide, around a 114.6 x 37.1 mm window; the rim is open along the low edge
so water runs off the panel instead of pooling. An 8 x 1.5 mm lead slot
sits at each end of the window, as the terminal end is still unknown. Two
2.4 mm cheeks at the ends; each is a trapezoid 8 mm tall at the front and
37.7 mm at the back, so the plate's low edge sits 8 mm off the lid. A
2.4 mm front wall of the same 8 mm height carries the plate's low edge,
pierced by a row of 5 mm diamond openings on a 9 mm pitch so air still
passes under the panel and out of the open back. Four feet, 10 x 8 x 4 mm,
turn inward from the cheeks' bottom corners with 3.4 mm countersunk holes
for M3 screws into the lid bosses. The angle, 45 degrees, is one parameter;
the cheek profile, front wall and feet follow it. Printed feet down, the
plate's underside is a 45-degree overhang and everything else is vertical
or on the bed, so there is no bridge anywhere; a recess on the panel face
was rejected because printed either way up it is a 37 mm bridge. Angles
under 45 degrees would need support.

## Fit coupon

A flat print of about 25 minutes with everything the ruler could have got
wrong: two pocket fences side by side, one for the ruler's 53 x 38 mm and
one for the export's 58.0 x 42.4 mm, each with its three ledges; one SMA
D-cut hole in a 2.4 mm tab; one insert column; and one pair of cell
V-blocks. The user drops the real board into whichever fence takes it, the
cell onto the blocks, and reports which fence fits and what binds, rattles
or sits on a pad. If the export fence is the one that fits, `BOARD_X` and
`BOARD_Y` change to 58.0 and 42.4 and everything else re-exports.

## Printing and hardware

Material PETG at minimum, ASA preferred, light colour. 0.2 mm layers, four
perimeters, 20 to 25 percent infill. Body open side up, lid top face down,
wedge feet down, coupon flat. Expect the body to take the longest; the
gable region prints as perimeters and sparse infill.

| Part | Qty |
|---|---|
| M3 x 8 countersunk screw | 4, lid |
| M3 x 12 countersunk screw | 4, wedge (foot 4 mm plus lid 3 mm leaves 5 mm in the insert) |
| M3 heat-set insert, 5.7 mm long | 8 |
| SMA bulkhead jack to U.FL pigtail | 1 |
| Small zip tie | 1 |
| 3 mm closed-cell foam tape | about 10 cm, for the three posts |
| Thin double-sided tape | panel and sensor breakouts |
| Neutral-cure silicone | spare lead slot |
| Fibreglass insect mesh, optional | glued behind the louvres against dust and insects |

Assembly: inserts into the columns and lid bosses; SMA jack through the
back wall and pigtail onto JP2; sensors onto their pads, leads up through
the channel slot and onto J3; board into the pocket, terminal edge to the
wire bay; cell onto the V-blocks, zip tie, leads trimmed into U11; foam
squares on the three posts; panel into the wedge recess with its leads
through a slot, wedge onto the lid with four screws, leads through the lid
hole to U9; ears screwed or tied to the ledge; lid on with four screws.

## Tooling and files

Same project as September. `params.py` keeps every dimension and the
derived layout with no CAD imports; `shapes.py` the helpers and reference
solids (board with its 10 mm part zone and 26 mm header zones, cell, sensor
boards, panel); `body.py`, `lid.py`, `wedge.py`, `coupon.py` one part each;
`build.py` exports STL, 3MF and STEP in print orientation plus the assembly
GLB; `render.py` the PNG views; `viewer.py` the self-contained browser
viewer with placement labels, published as a private artifact. Tests cover
the layout rules, solid validity, interference against the reference
solids, the no-line-of-sight rule for the louvres and eave labyrinth, and a
print-orientation overhang check on every exported part.

## Open items

1. **Board outline.** Ruler 53 x 38, export 58.0 x 42.4. The coupon decides;
   `BOARD_X` and `BOARD_Y` are the only numbers to change. The post and
   ledge positions are measured from the edges, so they should survive
   either outline, but the bare strips were read off the export and want a
   look on the real board before the body is printed.
2. **Panel terminal end.** Lead slots at both ends until the panel is in
   hand; seal the spare one.
3. **Breakout headers.** Straight or right-angle headers on the breakouts
   change how tall the Dupont housings stand in the sensor cavity. The
   cavity gives 43 mm at the ridge, which covers either.
4. **Lid heat.** The lid outside the panel's shadow is still in the sun. If
   the SHT41 or the cell still run hot, the next step is a double-skin lid
   or a wider plate on the wedge, both of which fit the current parts.
5. **Dust.** Vents this open will take dust in Sharjah. Mesh is listed as
   optional hardware; nothing in the model depends on it.
