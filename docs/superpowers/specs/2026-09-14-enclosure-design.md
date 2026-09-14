# Sensor node enclosure — design

Date: 2026-09-14
Status: draft, waiting for review before any geometry is modelled

## Goal

A 3D-printable case for one sensor node that holds the rev 1.0 PCB panel, the
supercapacitor pack, and both sensor breakouts, carries up to two solar panels
on the lid, and survives both indoor and outdoor use. Output is print-ready
STL/3MF files plus rendered previews, generated from one parametric script so
dimensions can be changed and re-exported.

Out of scope: a waterproof (IP67) rating, a pole or wall bracket, a light pipe
for the status LED, and anything for the CO sensor on J2.

## Inputs and how sure we are

| Item | Value | Source | Confidence |
|---|---|---|---|
| PCB design outline | 43.94 x 59.05 x 1.6 mm | EasyEDA export in `sensor-nodes-hardware/` | exact |
| PCB panel incl. breakaway rails | 72.0 x 71.4 mm | photo, scaled from the design outline | +/-0.3 mm |
| Same, by tape | 70 x 70 mm | user | +/-1 mm |
| Rails | ~14 mm left and right, ~6 mm top and bottom | photo | +/-0.3 mm |
| Tooling holes | ~2 mm, one per corner, positions below | photo and user tape | +/-0.5 mm |
| Tallest board part | under 12 mm | user | — |
| Sensor wiring | Dupont jumper wires on J1 | user | — |
| ENS160 breakout | 17 x 18 mm | user | +/-1 mm |
| SHT41 breakout | 25 x 17 mm | user | +/-1 mm |
| Supercapacitor pack | 65 x 38 x 18 mm flat pack, wired to C9 | user | +/-1 mm |
| Solar panel | PowerFilm MP3-37, 114.0 x 36.5 x 0.22 mm, foil-tape terminals | manufacturer page | exact |
| Antenna | U.FL pigtail 80 mm to an SMA bulkhead jack, 70 mm antenna | user | — |
| Screw terminal U5 | wires enter from the board edge | user | — |

Tooling hole centres, measured from the panel's outer edges (photo values used
for the model; tape values in brackets):

| Corner | Along top/bottom edge | In from top/bottom edge |
|---|---|---|
| Top-left | 4.8 mm (6) | 3.2 mm (3) |
| Top-right | 10.5 mm (10) | 3.1 mm (4) |
| Bottom-left | 5.3 mm (6) | 3.0 mm (4) |
| Bottom-right | 5.2 mm (7) | 3.3 mm (4) |

"Top" means the edge nearest U5 and J2 when the silkscreen reads upright.

## Decisions already made

- Keep the breakaway rails on and locate the whole panel in the case.
- Two MP3-37 panels on the lid, wired in parallel. One fitted at first.
- Hybrid deployment: splash-resistant, not sealed. Sensors breathe through
  shaded vents; the electronics bay stays closed.
- Lid held by four M3 screws.
- Printer and filament unknown, so the design targets a generic 0.4 mm-nozzle
  FDM printer with no supports.

## Layout

Case frame: X runs left to right, Y front to back, Z up. The lid faces the sky.
The PCB panel sits with its silkscreen upright, so U5 and J2 face the back
wall and the LoRa module and JP1 face the front.

Top view with the lid removed:

```
 back
 +---------------------------+----------------------+
 | U5                    J2  |                      |
 |                           |   supercap bay       |
 |   PCB panel pocket        |   42.0 x 72.0        |
 |   72.6 x 72.0             |   pack lies flat,    |
 |  H3            J1  H1     |   one zip tie        |
 |                           |                      |
 | JP1     LoRa              |                      |
 +==== sealed wall, wire notch above J1 ============+
 | SHT41                                    ENS160  |
 |          sensor bay 116.6 x 26.0, vented         |
 +--------------------------------------------------+
 front
```

SMA bulkhead on the left wall beside JP1. Solar leads come down the left side
to U5.

| Dimension | Value |
|---|---|
| Internal | 116.6 x 100.0 x 33.6 mm |
| Body outside | 121.4 x 104.8 x 36.0 mm |
| Overall with lid | 39.0 mm tall, plus corner lugs and mounting ears |
| Walls and floor | 2.4 mm; vent walls thicken inward to 4.0 mm |

Height stack: 2.4 mm floor, 4.0 mm ledge under the panel so through-hole pins
clear the floor, 1.6 mm board, then 28 mm clear above the board. The 28 mm is
set by the Dupont housings on J1, which stand about 16.5 mm tall, plus room to
bend the wires.

## Body

**PCB panel.** A 5 mm ledge runs under all four rails, stopping 1 mm short of
the V-score lines so the scores carry no load. Four 1.6 mm locating pegs,
2 mm tall with a 0.4 mm chamfer, rise from the ledge at the tooling hole
positions. Two vertical snap hooks, one on each side wall of the pocket, catch
the top face of the side rails. The panel presses in; pulling the hooks back
releases it. The pegs can be switched off with one parameter if the hole
positions prove unreliable, since the pocket walls also locate the panel.

**Supercapacitor bay.** The pack lies flat on the floor, held by one zip tie
through two 4 x 2 mm floor slots. The divider between the bay and the PCB
pocket is 20 mm tall, with a notch at its back end so the pack's leads reach
the C9 pads. A zip-tie anchor on the divider takes the strain off those 0603
pads.

**Sensor bay.** A full-height wall separates it from the electronics. A strip
of 3 mm closed-cell foam tape on top of that wall seals it against the lid. A
10 x 6 mm notch at the top of the wall above J1 passes the jumper wires and is
closed with silicone after wiring. The front and both end walls of the bay are
4 mm thick and carry horizontal vent slots, 1.6 mm tall on a 4 mm pitch,
sloping downward toward the outside so rain cannot fly straight in. Two 3 mm
drain holes sit in the bay floor at the front. Each breakout sticks with foam
tape onto a 3 mm raised pad, so air reaches both faces. The SHT41 goes at the
left end and the ENS160 at the right end, about 60 mm apart, so the ENS160
heater does not warm the humidity sensor.

**Antenna.** A 6.5 mm D-cut hole with a 6.0 mm flat, centred 20 mm above the
floor on the left wall beside JP1, takes the SMA bulkhead jack. A 12 mm flat
spot-face on the outside seats the nut and washer.

**Fasteners and mounting.** Four square columns on the outside corners hold M3
heat-set inserts, 4.0 mm holes 6 mm deep. A parameter switches them to 2.6 mm
pilot holes for self-tapping screws instead. Two ears at the bottom of the
left and right ends have 4.5 mm slots that take a screw or a zip tie. The
bottom is otherwise flat for shelf use.

## Lid

A 3.0 mm plate the size of the body, with a skirt that drops 4 mm over the
outside of the walls as a drip edge. The front edge overhangs a further 4 mm
to shade the sensor bay vents. Foam tape on the body's wall tops seals against
the underside.

The top face has two recesses, 114.6 x 37.1 x 0.4 mm, 3 mm apart, sized for
MP3-37 panels on thin double-sided tape. Each recess has an 8 x 1.5 mm lead
slot at both ends because the panel's terminal position is not confirmed
yet. Unused slots are filled with silicone. Leads run down inside to U5 with
about 10 cm of slack, so the open lid hangs on its wires.

Four countersunk 3.4 mm holes line up with the corner columns.

A third panel does not fit. It needs 121.5 mm across the lid, which is
104.8 mm. A third panel later would mean a bolt-on panel plate.

## Fit coupon

A small print, about 20 minutes, to settle every uncertain number before the
full case:

- a 2 mm base with the panel pocket as a 3 mm-tall frame, the ledge, the four
  pegs, and one snap hook
- one SMA D-cut test hole in a 2.4 mm tab
- one heat-set insert column

The user drops the real panel in, fits the SMA jack and an insert, and
reports what binds or rattles. Parameters get adjusted, then the full case is
exported.

## Printing

- **Material.** PETG at minimum. ASA is better for long outdoor sun exposure.
  Use a light colour so the lid under the panels runs cooler. Avoid PLA,
  which softens at around 55 to 60 C in direct sun.
- **Orientation.** Body open side up. Lid top face down on the bed, which also
  makes the panel recesses flat and smooth. Coupon flat. No supports anywhere.
- **Settings.** 0.2 mm layers, 4 perimeters, 20 to 25 percent infill.

Hardware per node:

| Part | Qty |
|---|---|
| M3 x 8 countersunk screw | 4 |
| M3 heat-set insert, 5.7 mm long | 4 |
| SMA bulkhead jack to U.FL pigtail | 1 |
| Small zip tie | 2 |
| 3 mm closed-cell foam tape | about 50 cm |
| Thin double-sided tape | for panels and sensors |
| Neutral-cure silicone | for notches and spare slots |

## Tooling and files

The model is written in Python with build123d, an OpenCASCADE-based CAD
library installed with pip into a virtual environment. build123d 0.11.1 and
its OCP kernel are published on PyPI for Python 3.13.

```
enclosure/
  params.py     every dimension, grouped by the input it comes from
  parts.py      builds the body, lid and fit coupon
  build.py      exports STL, 3MF and STEP to out/, plus drawings and a GLB
  README.md     regenerate, print settings, assembly order
  out/          committed, so the files print without Python
  .venv/        not committed
```

The render is a 3D viewer published as a private web page for orbit and zoom
review, plus orthographic SVG drawings committed next to the STLs.

## Verification

1. `build.py` checks every solid is valid and closed, the minimum wall is at
   least 1.6 mm, and two panels fit the lid recesses.
2. A simplified PCB panel model with component keep-outs taken from the
   EasyEDA footprints is placed in the pocket, and the build fails if it
   intersects the body.
3. The drawings and viewer are inspected before hand-over.
4. The fit coupon is printed and tried with the real parts before the full
   case.

## Open items

- **Panel size.** Photo says 72.0 x 71.4 mm, tape says 70 x 70 mm. The pocket
  uses the photo value plus 0.3 mm clearance, since a smaller real panel still
  seats on the pegs. The coupon settles it.
- **Case height.** Jumper wires force 39 mm overall. Soldered wires or
  right-angle headers later would allow about 25 mm; `above_pcb` controls it.
- **Panel terminal position.** Lead slots at both ends until confirmed.
- **Breakout mounting holes.** Unknown, so foam-tape pads.
- **Supercapacitor rating.** Needed to finish the power verdict, not the case.
