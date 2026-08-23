# jointview

Compare two price or NAV series of a [Polars](https://pola.rs) DataFrame, side by side.

[![PyPI version](https://img.shields.io/pypi/v/jointview.svg?logo=pypi&logoColor=white)](https://pypi.org/project/jointview/)

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](https://github.com/Jebel-Quant/jointview/blob/main/LICENSE)
[![Python versions](https://img.shields.io/badge/Python-3.11%20•%203.12%20•%203.13%20•%203.14-blue?logo=python)](https://www.python.org/)
[![CI](https://github.com/Jebel-Quant/jointview/actions/workflows/rhiza_ci.yml/badge.svg?event=push)](https://github.com/Jebel-Quant/jointview/actions/workflows/rhiza_ci.yml)
[![Coverage](https://jebel-quant.github.io/jointview/coverage-badge.svg)](https://jebel-quant.github.io/jointview/reports/html-coverage/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg?logo=ruff)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![marimo](https://img.shields.io/badge/built%20with-marimo-1f7cff)](https://marimo.io)
[![CodeFactor](https://www.codefactor.io/repository/github/jebel-quant/jointview/badge)](https://www.codefactor.io/repository/github/jebel-quant/jointview)
[![Rhiza](https://img.shields.io/badge/dynamic/yaml?url=https%3A%2F%2Fraw.githubusercontent.com%2FJebel-Quant%2Fjointview%2Fmain%2F.rhiza%2Ftemplate.yml&query=%24.ref&label=rhiza)](https://github.com/jebel-quant/rhiza)
[![Downloads](https://static.pepy.tech/personalized-badge/jointview?period=month&units=international_system&left_color=black&right_color=orange&left_text=PyPI%20downloads%20per%20month)](https://pepy.tech/project/jointview)

## Run it

```bash
uvx jointview
```

That is the whole installation. `uvx` fetches the package and its dependencies for the
length of the run and leaves nothing behind.

```bash
uvx jointview navs.parquet               # your own data
uvx jointview navs.parquet --height 900  # taller plot for a taller screen
```

![jointview comparing two funds of the demo frame](https://raw.githubusercontent.com/Jebel-Quant/jointview/main/docs/assets/screenshot.png)

Pick a series on each side. Both are drawn on one pair of axes, and each summary table
describes exactly the rows in the plot — the *common sample*, where both series are
present.

## Why both lines share an axis

A second scale would invent a relationship that is not in the data. So both series are
indexed to 100 at their first shared date, which is how a fund priced at 49 and one
priced at 1,450 become comparable. The switch above the plot turns that off when the
levels already share a scale.

## Options

| | |
|:---|:---|
| `jointview` | the generated demo frame |
| `jointview <file>` | `.parquet`, `.csv`, `.tsv`, `.json`, `.ndjson`, `.arrow`, `.ipc`, `.feather` |
| `--height` | plot height in pixels (default 700) |
| `--edit` | open the notebook itself, from a clone |
| `-- …` | everything after a bare `--` goes to marimo: `-- --port 8080 --headless` |

The first date column becomes the x-axis; without one the rows are numbered. Every
numeric column is offered as a series.

## The pieces on their own

Neither the chart nor the statistics need marimo. `uvx` runs the app; to import the
pieces, install the package from [PyPI](https://pypi.org/project/jointview/):

```bash
uv add jointview      # or: pip install jointview
```

The package ships a `py.typed` marker, so the annotations on everything below reach your
own type checker instead of resolving to `Any`.

Statistics come from [jQuantStats](https://github.com/jebel-quant/jquantstats), so the
frame carries its period column into `summary` — the annualisation factor is read from
the spacing of the observations rather than assumed.

```python
from jointview import demo_frame, line_chart, metrics, summary

frame = demo_frame()

table = summary(frame, "balanced", date_col="date")                    # a formatted two-column frame
sharpe = metrics(frame, "tech_fund", date_col="date")["Sharpe ratio"]  # the raw number
chart = line_chart(frame, "balanced", "tech_fund")                     # a plain Altair chart

print(table.columns, table.height, dict(table.iter_rows())["Max drawdown"])
print(f"{sharpe:.2f}")
print(type(chart).__name__)
```

```result
['metric', 'value'] 17 -15.90%
0.52
LayerChart
```

One line per claim above, in the same order — the table is two columns of formatted
strings, the metric is a bare float, and the chart is Altair's own type rather than a
marimo widget. The block is executed on every commit and its output compared against the
result printed here, so a figure that drifts is a failing test rather than a stale
README.

Seventeen figures per series — returns, volatility, Sharpe, Sortino, Calmar, drawdown,
Ulcer index, value at risk, and the shape of the period returns. A figure that cannot be
formed shows as `—` rather than blanking the table.
