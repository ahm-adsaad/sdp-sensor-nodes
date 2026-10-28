---
version: 1
slug: "paper-ml-forecast-pipeline-drawio"
primary_target: "paper/ml/forecast-pipeline.drawio"
related_targets: []
---

# Surface: IEEE journal figure, harvest-forecast ML pipeline

Scope: one double-column method figure, draw.io source at paper/ml/forecast-pipeline.drawio, exported by the user to PDF or SVG for an IEEE Internet of Things Journal submission. Mode: Read.
Audience: journal reviewers and readers who know ML forecasting and read the figure beside the method section.
Content: only what forecast/ implements (Open-Meteo feeds, pvlib clear sky, the 16-feature table, three quantile LightGBM boosters, clip and sort, node conversion, InfluxDB sink) plus the trained-model snapshot of 2026-10-10. No invented components and no back-test results inside the figure.
Constraints: the style of the reference figure paper/ml/wshah2-3598110-small.gif (stage panels with bold headers above, left-to-right flow, a dashed inset sub-group, italic math), a restrained IEEE palette, Times serif labels (user, 2026-10-29). paper/ is git-ignored.

## Direction contract

THESIS: One figure that shows the factorisation harvest = clear-sky energy x sky ratio x node ratio, with the learned part (three quantile LightGBM boosters) as the visual centre and the physics on either side. It refuses the generic "boxes named after Python modules" pipeline chart and the icon-tile flow diagram.

OWN-WORLD: White ground, near-black ink, Times New Roman throughout with italic math symbols. Four stage panels in pale washes (blue-grey inputs, warm grey features, blush model, mint node conversion) with no stroke; white blocks with 1 px ink stroke and small radius; dashed warm-graphite strokes for everything training-only; black block-head arrows for the hourly inference path. Tree glyphs in ink inside each booster block. No gradients, shadows or saturated fills.

STORY: The reader follows public weather and dust feeds through pvlib and a 16-feature table into three quantile boosters, sees the quantiles clipped and sorted, then multiplied by clear-sky energy and the measured node ratio into 36 hourly joule levels per node, and sees underneath how the model is retrained weekly and gated against the raw forecast.

FIRST VIEWPORT: Headers "Inputs", "Feature Construction", "Sky-Ratio Model", "Node Conversion" across the top of four strokeless wash panels (canvas 1496 x 922; type 22 px body, 24 px bold titles, 30 px headers, about 7.6, 8.3 and 10.4 pt at double-column width). Left panel stacks six input blocks (site, weather forecast, training inputs, air-quality forecast, training target, measured harvest; training-only blocks dashed). Second panel runs pvlib sun geometry, weather features and the 16-feature table top to bottom with the dashed target below. Third panel shows three booster blocks with ink tree glyphs feeding a tall clip-and-sort block that lists the three sorted levels, the hyperparameter clause beneath, and the dashed training-and-gate inset along the bottom. Right panel is built around the product node at its left edge: sorted levels enter straight from the gutter, clear-sky energy from above, node ratio from below, output to the right into the 36-level block and down into the InfluxDB cylinder. One line runs under the panels (measured harvest to node ratio); no two lines cross.

FORM: brief-pinned reference-figure style; seed: none. No roll was made because the user pinned the style in the request ("similar style of diagram ... ieee journal style").

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
