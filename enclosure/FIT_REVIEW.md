# Fit review — 16 September 2026

The existing parametric model uses the supplied 72.0 x 71.4 x 1.6 mm
panel, with the rails attached. Dedicated lids are exported for one, two,
and three solar panels; all use the same body.

## Layout and size

| Feature | Model dimensions (mm) |
|---|---|
| Body walls, excluding ears and corner columns | 121.4 x 104.8 x 36.0 |
| Lid | 138.6 x 122.0 |
| Complete nominal envelope, including mounting ears | 145.4 x 122.0 x 39.0 |
| PCB pocket | 72.6 x 72.0 |
| Clearance above main PCB | 28.0 |
| Supercapacitor bay | 42.0 x 72.0 |
| Sensor bay, before inward vent-wall thickening | 116.6 x 26.0 |
| Solar recess, each | 114.6 x 37.1 x 0.4 deep |

The PCB and supercapacitor sit side by side. A front compartment holds the
two sensors at opposite ends behind angled vents, with floor drains.
The lid faces upward and carries the solar panels. The antenna mount is on
the left wall near the board's antenna connector.

Tooling-hole centres are (4.8, 3.2), (61.5, 3.1), (5.3, 68.4), and
(66.8, 68.1), measured from the panel's top-left corner with Y toward the
bottom. The screw-terminal edge is the top. These are intentionally asymmetric.

## Check before a full print

- Print the fit coupon first. A 1.6 mm peg in a 2.0 mm hole allows only
  0.2 mm radial error; photo measurements cannot guarantee alignment of all
  four pegs. Adjust the measured coordinates or disable pegs in `params.py`.
- The pocket allows 0.3 mm per side at nominal panel size. At the stated
  maximum panel size, only 0.15 mm per side remains before printer error.
- The pack's maximum stated size, 66 x 39 x 19 mm, fits the nominal bay.
  Confirm the wire exit, wrapping and zip-tie clearance on the real pack.
- The estimated 16.5 mm header plug leaves 11.5 mm of nominal height for
  wire bends. Component bodies, underside pins and actual jumper routing
  still need a dry assembly check.
- Sensor supports assume 1.6 mm board thickness and adhesive mounting.
  Check underside components and header orientation; leave the sensing
  openings exposed. CAD reference models contain bare breakout boards,
  not their populated components.
- The antenna hole assumes a 6.5 mm SMA barrel with a 6.0 mm flat.
  The supplied antenna dimensions do not establish its connector type,
  diameter, nut dimensions or required thread length. Try the real fitting
  in the coupon before printing the body. Route the 80 mm lead loosely
  without pulling JP1; the model does not validate cable bend radius or
  antenna-to-panel clearance.
- Foil terminal positions, widths and attachment method remain unknown.
  The 8 x 1.5 mm lid slots are for insulated wires after a supported foil
  transition. Verify the transition before sticking the panels down.

## Assembly and deployment limits

The CAD lid seats directly on the wall tops. There is no gasket groove or
controlled compression stop. Adding perimeter foam raises the lid, increases
the gap under its PCB clamp posts and reduces screw engagement. Trial-fit the
seal, rail pads and screws together; the nominal 39 mm height excludes this
added separation. Do not assume the model verifies a watertight seal.

Angled vents and drains are rain-mitigation features, not a demonstrated IP
rating. Keep the lid up and drains down. Check water ingress and compare the
assembled SHT41 reading against a shaded reference under sun and with the
ENS160 running before relying on deployment measurements. No insect mesh or
sensor radiation shield is modelled.

Top-face-down lid printing requires bridging the solar recesses. Inspect the
slicer preview and validate bridging or support removal on the chosen printer.
The fit coupon does not test this feature.

CAD tests cover solid validity, nominal part interference, hole locations and
exports. They do not establish printed fit, weather resistance, RF performance,
sensor accuracy or the harvesting circuit's compatibility with panel wiring.
