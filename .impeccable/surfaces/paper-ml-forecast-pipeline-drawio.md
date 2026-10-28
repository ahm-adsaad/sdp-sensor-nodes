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

FIRST VIEWPORT: Headers "Inputs", "Feature Construction", "Sky-Ratio Model", "Node Conversion" across the top. Left panel stacks five input blocks; the middle-left panel stacks pvlib, sky-ratio features and the feature table; the model panel shows three booster blocks feeding a tall clip-and-sort block, with the training inset dashed along its bottom; the right panel stacks clear-sky energy and node ratio into a product node, then the output levels and the InfluxDB cylinder. Config and measured-harvest arrows run under the panels into the right panel.

FORM: brief-pinned reference-figure style; seed: none. No roll was made because the user pinned the style in the request ("similar style of diagram ... ieee journal style").

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
