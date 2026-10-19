---
name: Virtualized Energy Harvesting IoT
description: Print-first IEEE conference idiom for the AUS senior design team's EH sensor network deliverables.
colors:
  maroon: "#880e12"
  maroon-tint: "#f6e9ea"
  on-maroon-soft: "#f3dfe0"
  ink: "#1d1f24"
  ink-secondary: "#4a4740"
  ink-muted: "#77726a"
  hairline: "#d9d3cb"
  paper: "#ffffff"
  data-rx: "#3a6ea5"
  data-rx-tint: "#eaf0f7"
  data-sense: "#b8861b"
  data-sense-tint: "#f7f0e1"
  data-sense-deep: "#7a5806"
  data-tx: "#b5373d"
  data-sleep: "#e6e2dc"
  data-sleep-ink: "#5f5a53"
  energy: "#2e7d5b"
  energy-tint: "#eaf3ee"
typography:
  display:
    fontFamily: "STIX Two Text, STIX Two Math, Times New Roman, serif"
    fontSize: "86pt"
    fontWeight: 700
    lineHeight: 1.04
    letterSpacing: "-0.012em"
  byline:
    fontFamily: "STIX Two Text, STIX Two Math, Times New Roman, serif"
    fontSize: "38pt"
    fontWeight: 400
    lineHeight: 1.2
  affiliation:
    fontFamily: "STIX Two Text, STIX Two Math, Times New Roman, serif"
    fontSize: "29pt"
    fontWeight: 400
    lineHeight: 1.25
  headline:
    fontFamily: "STIX Two Text, STIX Two Math, Times New Roman, serif"
    fontSize: "36pt"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "0.02em"
    fontFeature: "small-caps"
  title:
    fontFamily: "STIX Two Text, STIX Two Math, Times New Roman, serif"
    fontSize: "29pt"
    fontWeight: 400
    lineHeight: 1.2
  body:
    fontFamily: "STIX Two Text, STIX Two Math, Times New Roman, serif"
    fontSize: "27pt"
    fontWeight: 400
    lineHeight: 1.3
    fontFeature: "lnum"
  algorithm:
    fontFamily: "STIX Two Text, STIX Two Math, Times New Roman, serif"
    fontSize: "24pt"
    fontWeight: 400
    lineHeight: 1.55
  table:
    fontFamily: "STIX Two Text, STIX Two Math, Times New Roman, serif"
    fontSize: "22.5pt"
    fontWeight: 400
    lineHeight: 1.22
  table-head:
    fontFamily: "STIX Two Text, STIX Two Math, Times New Roman, serif"
    fontSize: "22.5pt"
    fontWeight: 600
    letterSpacing: "0.02em"
    fontFeature: "small-caps"
  reference:
    fontFamily: "STIX Two Text, STIX Two Math, Times New Roman, serif"
    fontSize: "16pt"
    fontWeight: 400
    lineHeight: 1.26
  math:
    fontFamily: "STIX Two Math, STIX Two Text, serif"
    fontSize: "1.04em"
  label:
    fontFamily: "Source Sans 3, STIX Two Text, sans-serif"
    fontSize: "7-8 viewBox units (about 20-23pt at A0)"
    fontWeight: 400
rounded:
  none: "0"
  diagram-box: "2 viewBox units"
  diagram-chip: "1.8 viewBox units"
  seal: "50%"
spacing:
  page-margin: "20mm"
  band-padding: "19mm 26mm 18mm 24mm"
  gutter: "16mm"
  row-gap: "12mm"
  section-stack: "10mm"
  heading-after: "5mm"
  paragraph: "3.5mm"
components:
  title-band:
    backgroundColor: "{colors.maroon}"
    textColor: "{colors.paper}"
    typography: "{typography.display}"
    padding: "19mm 26mm 18mm 24mm"
  section-heading:
    textColor: "{colors.maroon}"
    typography: "{typography.headline}"
    padding: "0 0 2.2mm"
  subsection-heading:
    textColor: "{colors.ink}"
    typography: "{typography.title}"
  booktabs-table:
    textColor: "{colors.ink}"
    typography: "{typography.table}"
    rounded: "{rounded.none}"
    width: "100%"
  booktabs-head:
    textColor: "{colors.ink}"
    typography: "{typography.table-head}"
    padding: "2mm 2.5mm 1.8mm"
  algorithm-block:
    textColor: "{colors.ink}"
    typography: "{typography.algorithm}"
    padding: "2.5mm 0 3mm"
  diagram-box:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.diagram-box}"
  diagram-box-energy:
    backgroundColor: "{colors.energy-tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.diagram-box}"
  diagram-box-mcu:
    backgroundColor: "{colors.maroon-tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.diagram-box}"
  diagram-box-radio:
    backgroundColor: "{colors.data-rx-tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.diagram-box}"
  diagram-box-sensing:
    backgroundColor: "{colors.data-sense-tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.diagram-box}"
  reference-list:
    textColor: "{colors.ink}"
    typography: "{typography.reference}"
---

# Design System: Virtualized Energy Harvesting IoT

## Overview

**Creative North Star: "The Proceedings Page, Enlarged"**

The system is an IEEE conference page scaled to A0 and played straight. Authority comes from the conventions engineering readers already trust: Roman-numeral section heads in small caps, booktabs tables, numbered display equations, an algorithm2e-style ruled block, and bracketed numbered references. Nothing is dressed up; precision of setting is the only ornament. The page is dense by poster standards because judges read it twice, first at 1 to 2 m for the title band and the diagrams, then up close for the mechanism.

Colour is rationed. AUS maroon owns the title band and the section rules and appears nowhere as decoration. A small, validated data palette (receive, sense, transmit, sleep, harvested energy) carries every diagram and is never used for prose. The ground is white print paper and the ink is a near-black with a warm secondary grey.

The world refuses the infographic-poster default: no icon tiles, no stat blocks, no gradient banners, no captions or subtitles, and no number presented as a measured result when the report of record has none.

**Key Characteristics:**
- White print ground, near-black ink, one institutional accent (AUS maroon).
- One serif family (STIX Two Text) for all text, its math sibling for equations, a humanist sans only inside diagrams.
- Typeset academic devices: small-caps numbered sections, booktabs rules, numbered equations, ruled algorithm, numbered references.
- Diagrams are the figures; they carry no captions.
- Flat throughout: depth only from rules, tints and the maroon band.

## Colors

A print palette: one institutional red, a warm neutral ink ladder, and a five-colour data set validated for a light ground.

### Primary
- **AUS Maroon** (maroon): the full-width title band, every section heading and its rule, list markers, the VPS container outline and title in the system diagram, and the MCU box stroke. It marks structure, never emphasis inside prose.
- **Maroon Wash** (maroon-tint): fill of the server container and the MCU block, the two places the "brain" of the system sits.
- **Blush on Maroon** (on-maroon-soft): affiliation line inside the title band, one step below the white title and authors.

### Secondary (data palette)
- **Signal Blue** (data-rx): downlink and task flow (arrows into nodes, task requests) and Rx segments in the schedule. Radio module tint is **Radio Wash** (data-rx-tint).
- **Sensing Ochre** (data-sense): active sensor chips, Sense segments, the load-switch and sensor path. **Sensing Wash** (data-sense-tint) fills sensor blocks; **Deep Ochre** (data-sense-deep) sets the italic task label beside a node name.
- **Brick** (data-tx): uplink of data and status, Tx segments, server-internal pipeline arrows.
- **Sleep Stone** (data-sleep): sleep segments, labelled in **Sleep Ink** (data-sleep-ink).
- **Harvest Green** (energy): the energy chain (panel, PMIC, storage, 3V3 rail) and the always-on harvesting line under each schedule row. **Harvest Wash** (energy-tint) fills energy blocks.

### Neutral
- **Proof Ink** (ink): body text, table rules, diagram box strokes and primary labels.
- **Warm Graphite** (ink-secondary): diagram sublabels, algorithm line numbers and comments.
- **Faded Graphite** (ink-muted): dashed links, inactive sensor chips, the time axis. (Inactive chip strokes use #b9b2a9.)
- **Rule Sand** (hairline): inner row rules in tables and divider lines inside diagram boxes.
- **Print White** (paper): the ground and diagram box fills.

### Named Rules
**The Maroon Is Structure Rule.** Maroon marks the band, section heads, their rules and list markers. It never colours a word in a paragraph or a table cell.

**The Data Colours Mean Data Rule.** Blue is always receive or task flow, ochre always sensing, brick always transmit or data uplink, green always harvested energy, stone always sleep. A colour keeps its meaning in every diagram; it is never reused decoratively.

**The Legible Fill Rule.** Text on a solid data fill follows the validated pairing: white on blue and brick, ink on ochre, Sleep Ink on stone.

## Typography

**Display Font:** STIX Two Text (with STIX Two Math, Times New Roman, serif)
**Body Font:** STIX Two Text
**Math Font:** STIX Two Math
**Label Font:** Source Sans 3 (diagrams only)

**Character:** STIX is the typeface of the journals this work cites, so the poster reads as their page. Source Sans 3 gives diagram labels a cleaner small-size texture and keeps figures visibly distinct from prose.

All fonts are self-hosted woff2 subsets in the artifact's `fonts/` folder; Greek uses a separate unicode-range subset.

### Hierarchy
- **Display** (700, 86pt, 1.04, -0.012em, balanced wrap): the poster title in the band.
- **Byline** (400, 38pt, 1.2): authors in the band. **Affiliation** (400, 29pt, 1.25) follows with a 600-weight "Advisor:" lead.
- **Headline** (700, 36pt, small caps, 0.02em): numbered section heads "I. Motivation" in maroon over a 1.3 mm maroon rule. The References head drops to 27pt.
- **Title** (400 italic, 29pt, 1.2): lettered subsections "A. MILP", "B. Heuristic", and unnumbered sub-heads.
- **Body** (400, 27pt, 1.3, lining numerals): justified with automatic hyphenation; 3.5 mm between paragraphs and list items.
- **Algorithm** (400, 24pt, 1.55): pseudocode, bold keywords, italic variables; line numbers at 18pt in Warm Graphite.
- **Table** (400, 22.5pt, 1.22): booktabs tables; 600-weight small-caps heads. The opening gap table runs at 23.5pt with looser rows.
- **Equation numbers** (25pt), display math at 1.12em of body.
- **Reference** (400, 16pt, 1.26): three-column numbered list. Acknowledgement at 18pt.
- **Label** (Source Sans 3, 7 to 8 viewBox units, about 20 to 23pt at print size): 700 for part names, 400 in Warm Graphite for sublabels, about 6.8 to 7.5 units.

### Named Rules
**The One Serif Rule.** Every word outside a diagram is STIX Two Text or STIX Two Math. Sans appears only inside SVG figures.

**The Small-Caps Head Rule.** Section and table heads use true small caps (`font-variant-caps: small-caps`) with 0.02em tracking, never uppercase transforms.

## Layout

Fixed A0 portrait page (841 x 1189 mm, `@page` margin 0), rendered by headless Chromium. A full-width maroon title band (seal column 134 mm, 20 mm gap, then title block) sits above a three-column grid with 20 mm side margins, 16 mm gutters and 12 mm row gaps. Row one pairs the opening section in column one with the system diagram spanning columns two and three; row two holds three stacked columns whose sections space out vertically (10 mm minimum) to fill the height; row three is the full-width references block, itself set in three columns on the same 16 mm gutter. Section heads sit 5 mm above their content; display equations take 5.5 mm above and 7 mm below. Diagrams span the full column width at `width: 100%`.

**The Column Grid Rule.** Every block aligns to the three-column, 16 mm-gutter grid; a figure may span columns but never breaks the margin.

## Elevation & Depth

Completely flat. There are no shadows, gradients or blurs. Depth and grouping come from rules (booktabs weights, the 1.3 mm section rule), pale tints behind diagram groups, and the solid maroon band. Print colour is forced with `print-color-adjust: exact`.

**The Ink-Only Rule.** If a hierarchy cannot be expressed with rule weight, tint or type, it does not get a shadow.

## Shapes

Text matter is square: tables, algorithm and band have no radius. Diagram boxes take slight rounding (2 to 3 viewBox units for blocks, 1.8 for chips, 1.2 to 1.6 for schedule segments) so they read as components, not table cells. The seal is the only circle. Strokes are hairline (0.55 to 0.8 units) for boxes and 1 to 1.2 units for flow arrows, with small filled triangle markers in the flow's colour. Optional or debug links are dashed.

## Components

### Title Band
Institutional and confident. Solid maroon, the AUS seal on a white disc with 6 mm padding at left, the bold title, authors and affiliation in white and blush at right.

### Section Heading
Roman numeral plus title, maroon small caps over a 1.3 mm maroon rule with 2.2 mm clearance.

### Booktabs Table
Rules only: 0.75 mm ink top and bottom, 0.4 mm ink under the head, 0.2 mm Rule Sand between body rows, no vertical rules, no fills. First and last columns flush to the table edge. Numeric columns right-aligned with tabular lining numerals. The team's own row is set in bold, not tinted.

### Algorithm Block
algorithm2e ruled style: 0.75 mm ink rules top and bottom, a 0.4 mm rule under the Input line, right-aligned line numbers, indentation in 9 mm steps, right-floated italic comments led by a triangle (U+25B7) as in algorithm2e.

### Numbered Equation
Display MathML centred on the column with its number "(n)" right-aligned; constraint rows place an italic "s.t." label in a 22 mm left column.

### Diagram Box
White or tinted fill with a thin stroke in the group's colour, a 700-weight part name and 400-weight Warm Graphite sublabels in Source Sans 3. Tint chooses the subsystem: Harvest Wash for energy, Maroon Wash for the MCU or server, Radio Wash for the radio, Sensing Wash for sensors.

### Schedule Strip
Per-node rows of rounded segments in the data palette, each labelled inside, with a 1.4-unit Harvest Green line beneath every row for continuous harvesting and a legend above.

### Reference List
Bracketed numbers hanging 12 mm, three columns, IEEE citation style with italic venues.

## Do's and Don'ts

### Do:
- **Do** number sections with Roman numerals and subsections with letters, as an IEEE paper does.
- **Do** keep every data colour bound to its meaning (blue Rx/task, ochre sense, brick Tx/data, stone sleep, green harvest) in every new figure.
- **Do** set SVG text colour with `fill` presentation attributes on the element; inherit a default from `svg { fill: var(--ink) }` only.
- **Do** set CO<sub>2</sub> in diagrams with a subscript tspan (`baseline-shift: -0.26em`, 0.75em); the diagram font subset has no U+2082, so a script pass converts the character.
- **Do** keep diagram labels between 7 and 8 viewBox units at the A0 scale, so they print at about 20 to 23pt.
- **Do** cite with bracketed numbers that resolve to the reference list.

### Don't:
- **Don't** write a CSS rule like `svg text { fill: ... }`; it overrides the per-element fill attributes and flattens the data colours.
- **Don't** add figure captions, subtitles or filler text; the section head and the figure carry the meaning.
- **Don't** present any number as a measured result when the report of record has none; targets go in a requirements table labelled as targets.
- **Don't** use icon tiles, stat blocks, gradient banners or shadows.
- **Don't** introduce a second display face or set prose in Source Sans 3.
- **Don't** use maroon or the data colours to highlight words in prose.
