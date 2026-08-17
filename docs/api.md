# API Reference

Everything the app is built from is importable, so a frame can be shaped, summarised
or drawn without opening the GUI at all:

```python
from jointview import demo_frame, line_chart, summary_markdown

frame = demo_frame()
chart = line_chart(frame, "world_equity", "tech_fund")               # an Altair LayerChart
table = summary_markdown(frame, "world_equity", date_col="date")     # a markdown table
```

Note what `summary_markdown` takes: the frame **and** the column name, not a bare
series, plus the column carrying the period. jQuantStats reads the annualisation factor
off the spacing of the observations, so the dates have to travel with the levels.
`date_col` defaults to `"period"` — the column [`aligned`](#columns) writes — so a frame
that has not been through `aligned` needs to name its own, as here. That name is
exported as `jointview.PERIOD`, so code reading an aligned frame back does not have to
spell the literal.

The five modules below are the whole of it. `jointview.app` is the notebook itself and
has no API — run it with `jointview` rather than importing it.

## Data

Getting a frame in: reading a file, or generating one to look at.

::: jointview.data

## Columns

Choosing the series, finding the x-axis, and cutting a chosen pair down to the rows the
two share. Neither drawing nor summarising depends on the other; both are built on this.

::: jointview.columns

## Charts

Turning an aligned pair into a picture.

::: jointview.plot

## Statistics

The numbers under each dropdown, computed from the rows in the plot.

::: jointview.stats

## Command line

What `uvx jointview` runs.

::: jointview.cli
