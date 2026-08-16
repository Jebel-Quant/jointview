# API Reference

Everything the app is built from is importable, so a frame can be shaped, summarised
or drawn without opening the GUI at all:

```python
import polars as pl

from jointview import demo_frame, line_chart, summary_markdown

frame = demo_frame()
chart = line_chart(frame, "world_equity", "tech_fund")   # an Altair LayerChart
table = summary_markdown(frame["world_equity"])          # a markdown table
```

The four modules below are the whole of it. `jointview.app` is the notebook itself and
has no API — see [Marimo Notebooks](development/MARIMO.md).

## Data

Getting a frame in: reading a file, or generating one to look at.

::: jointview.data

## Columns and charts

Choosing the series, cutting them down to their common sample, and drawing the pair.

::: jointview.plot

## Statistics

The numbers under each dropdown, computed from the rows in the plot.

::: jointview.stats

## Command line

What `uvx jointview` runs.

::: jointview.cli
