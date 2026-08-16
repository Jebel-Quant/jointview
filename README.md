# jointview

A small [marimo](https://marimo.io) app for looking at two price or NAV series of a
[Polars](https://pola.rs) DataFrame at once.

Every numeric column is a series you can pick, one on the left and one on the right.
The middle holds both as two lines on one pair of axes; underneath each dropdown sits
the summary of exactly the rows in that plot.

```
┌──────────┬───────────────────────────┬──────────┐
│ left     │      two-line chart       │ right    │
│ dropdown │   (indexed to 100)        │ dropdown │
│ ─────────│                           │──────────│
│ summary  │                           │ summary  │
│ table    │                           │ table    │
└──────────┴───────────────────────────┴──────────┘
```

Both lines share one y-axis: a second scale would invent a relationship that is not
in the data. So the default is to index both series to 100 at the first date they
have in common, which is how a fund priced at 1.02 and one priced at 1,450 end up
comparable. The switch above the plot turns that off when the levels already share a
scale.

## Run it

There is nothing to install: the app ships with the package, and `uvx` fetches both
for the length of the run.

```bash
uvx jointview                            # generated demo frame
uvx jointview navs.parquet               # your own data
uvx jointview navs.parquet --height 900  # taller plot for a taller screen
```

Until the package is on PyPI, point `uvx` at the repository — or at a checkout of it:

```bash
uvx --from git+https://github.com/jebel-quant/jointview jointview navs.parquet
uv run jointview navs.parquet            # from a clone
uv run jointview --edit                  # open the notebook itself
```

`--edit` only makes sense from a clone: it opens the notebook marimo is serving, and
under `uvx` that is a copy in a throwaway environment.

Arguments after a bare `--` belong to marimo rather than to the app, which is how the
server itself is configured:

```bash
uvx jointview navs.parquet -- --port 8080 --headless
```

The plot takes the full width of the window and the tables sit either side of it. Its
height is the one thing the page cannot work out for itself — 700px suits a laptop, and
`--height` is there for a monitor that has more to give.

The file reads as `.parquet`, `.csv`, `.tsv`, `.json`, `.ndjson`, `.arrow`, `.ipc` and
`.feather`. The first temporal column becomes the x-axis; without one the rows are
numbered. Every numeric column is offered as a series. Given no file you get
`jointview.data.demo_frame()`: daily NAVs for six made-up funds that share a market
factor and start anywhere between 1 and 1,450.

## The summary

Both tables are computed from the *common sample* — the dates where both series are
present — so the numbers always describe the lines you are looking at.

| | |
|:---|---:|
| Observations, Start, End | the extent of the series |
| Total return, Annual return | `end/start`, and the same compounded to a year |
| Annual volatility, Sharpe ratio | of the period returns, at 252 periods a year, cash at zero |
| Max drawdown | the deepest fall below the running peak |
| Hit rate, Best period, Worst period | the shape of the period returns |

A figure that cannot be formed — a Sharpe ratio for a flat series, a growth rate for
a series that starts at zero — shows as `—` rather than blanking the table.

## Use the pieces on their own

Neither the chart nor the statistics need marimo:

```python
import polars as pl
from jointview import line_chart, summary, metrics

frame = pl.read_parquet("navs.parquet")
line_chart(frame, "tech_fund", "balanced").save("lines.html")

summary(frame["tech_fund"])              # a formatted two-column frame
metrics(frame["tech_fund"])["Sharpe ratio"]   # the raw number
```

`line_chart` is a plain Altair chart: two 2px lines, a legend and a label at the end
of each line, and a crosshair that reads both series at the hovered date. Curves
longer than `max_points` (4,000 by default) are thinned by a fixed stride — the last
point always survives, so the endpoints and the summary agree.

## Develop

```bash
uv sync
uv run pytest
```
