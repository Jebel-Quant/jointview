# jointview

A small [marimo](https://marimo.io) app for looking at two columns of a
[Polars](https://pola.rs) DataFrame at once.

Column names are listed on the left and on the right — step through them with
`◀`/`▶` or click one directly. The middle holds the joint plot of the two
selections: a scatter with a marginal histogram on each axis. Drag a box over the
scatter and both marginals highlight the rows inside it.

```
┌────────┬──────────────────────┬────────┐
│ x-axis │                      │ y-axis │
│ ◀ ▶    │      joint plot      │ ◀ ▶    │
│ factor │   (scatter + hists)  │ returns│
└────────┴──────────────────────┴────────┘
```

## Run it

```bash
uv run marimo run app.py                              # generated demo frame
uv run marimo run app.py -- --data prices.parquet     # your own data
uv run marimo edit app.py                             # open the notebook itself
```

`--data` reads `.parquet`, `.csv`, `.tsv`, `.json`, `.ndjson`, `.arrow`, `.ipc`
and `.feather`. Without it you get `jointview.data.demo_frame()`, which carries a
date, a string, and a handful of numeric columns — including a couple of
deliberately correlated pairs (`factor` × `returns`, `volatility` ×
`spread_bps`) so there is something to find.

## Use the plot on its own

`joint_chart` is a plain Altair chart and does not need marimo:

```python
import polars as pl
from jointview import joint_chart

frame = pl.read_parquet("prices.parquet")
joint_chart(frame, "factor", "returns").save("joint.html")
```

Numeric columns are treated as quantitative, dates as temporal and everything
else as nominal, so any pair of columns can be selected. Frames larger than
`max_points` (20k by default) are sampled down for the scatter; the marginals are
drawn from the same sample.

## Develop

```bash
uv sync
uv run pytest
```
