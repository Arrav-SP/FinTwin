# FinTwin interface design

The rules for the `web/` interface. Read this before adding a page or a component. Tokens live in `src/styles.css`.

## What the interface is for

FinTwin is a test bench: it runs banking workloads against PostgreSQL, measures the response, predicts it with a model, and checks the prediction. The reader is an engineer or an examiner who wants to know what happened in a run and whether the model was right. Every screen should answer a question in the order the reader would ask it: what happened, by how much, compared with what.

## The one rule

**A measured value is filled. A predicted value is hollow and dashed.**

- Measured: solid fill in the signal colour (`--color-signal`).
- Predicted: dashed outline in the text colour, no fill.
- The signal colour is used for measured data and system health only. It is never a button fill, a decoration, or a link colour.

The wordmark, the chart points, the evidence tracks and their keys all follow this. If a new chart shows a prediction, it must be visibly unfinished next to the measurement.

## Voice

The page opens with a finding in words, built from the latest run's own values (`src/lib/runSummary.ts`): "High concurrency transfer asked for 400 transactions a second and got 275." Figures follow the sentence; they do not replace it.

- Sentence case everywhere. No all-caps labels, no labels above headings.
- Name things as the reader sees them: "Requested", "Delivered", "Lock requests waiting", not field names.
- A button says what it does and keeps that name ("Read again", then "Reading").
- An empty screen says what to run to fill it. An error repeats the server's reason and offers one action.
- Never print a number the API did not return. A missing value is a dash; a percentage that is not defined says "not defined".

## Colour

| Token | Hex | Use |
|---|---|---|
| `ink` | `#0d1826` | Page background |
| `well` | `#0a1420` | Inputs, tooltips |
| `slate` | `#16263a` | Hover, meter tracks, placeholders |
| `rule` / `rule-strong` | `#24364d` / `#3a5170` | Hairlines; control and table-head borders |
| `paper` | `#eef1ec` | Text, predicted outlines, focus ring |
| `graphite` | `#a8b5c5` | Secondary text (about 8:1 on ink) |
| `pencil` | `#8192a8` | Tertiary marks only: run IDs, reference lines |
| `signal` | `#4cc2a8` | Measured values, healthy status |
| `amber` | `#e5b454` | Contention and shortfall: lock waits above zero, delivery under 95% |
| `red` | `#f0766e` | Failure and unavailable services |

No gradients, no glows, no translucent panels. Dark only for now.

## Type

| Role | Face | Size |
|---|---|---|
| Statements and section titles | Newsreader (serif, optical sizing) | Lede `clamp(28px, …, 46px)`; titles 24px |
| Interface text | IBM Plex Sans | 15px body, 18px for the lede's supporting line |
| Captions, table heads, axis labels | IBM Plex Sans | 13px, the minimum anywhere |
| Figures | IBM Plex Sans 500, tabular lining numerals | 36px |
| Run IDs and commands | IBM Plex Mono | 13px |

The serif is the editorial voice and appears only where the interface is saying something. Mono is for things a person would copy, never for labels. Lines of prose stay under about 62 characters.

## Layout

- A top bar, not a sidebar: wordmark, sections, system status. The page gets the full width.
- Content is a single column up to 1320px. Regions are separated by a hairline and 56px of space, not by boxes. There are no cards and nothing is nested in a container.
- One radius, 4px, on controls only.
- The Overview reads top to bottom: finding, figures, the load chart beside the prediction check, the run log.
- Breakpoints: figures go 2 columns, then 4 (640px), then one row (1024px); the chart and the prediction check sit side by side from 1152px.

## Components

| Component | Rule |
|---|---|
| `Section` | Serif title, optional one-line note on how to read it, optional controls on the right |
| `RunFigures` | Throughput leads, with a meter against the requested rate; other figures are equal |
| `LoadChart` | Requested rate on x, response on y, both logarithmic. On the throughput view the axes share a scale so the diagonal means "delivered what was asked". Runs timed by the earlier runner are hollow grey on latency views |
| `EvidenceGap` | One metric per row, each on its own scale from zero; values in columns, track beneath |
| `RunsTable` | Units in column heads; figures right-aligned and tabular; status shown only when a run did not complete |
| `Segmented` | Underlined text buttons with `aria-pressed`, for re-plotting one chart |
| `Placeholder`, `EmptyState`, `ErrorState` | Shaped like the content; a left rule, a serif line, a plain explanation |

## Charts

- Every axis has a title with its unit. Every mark that is not self-evident has a key under the chart.
- Use a log scale when values span more than a decade, and say what the reference line means.
- No animation on data. Tooltips repeat the value with its unit, the scenario, the workload and the time.

## Interaction and accessibility

- Focus is a 2px paper-coloured outline, offset 3px, on every interactive element. A skip link is the first tab stop.
- Motion is limited to colour transitions on hover and a pulse on placeholders, which stops under `prefers-reduced-motion`.
- Tables have captions and scoped headers. Decorative tracks and meters are hidden from assistive technology, and the values they show are in text beside them.
- Minimum text size is 13px. Secondary text keeps at least 7:1 contrast.

## Not allowed

Fake or sample data outside test files; zero in place of a missing value; icons without a job; badges for states that are always the same; a control that leads nowhere.
