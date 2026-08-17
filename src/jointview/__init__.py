"""Compare two price or NAV series of a Polars DataFrame side by side."""

from jointview.columns import PERIOD, aligned, date_column, default_pair, series_columns
from jointview.data import demo_frame, load_frame
from jointview.plot import line_chart, line_frame
from jointview.stats import drawdown, metrics, returns, summary, summary_markdown

__all__ = [
    # The name `aligned` writes the x-axis under and the statistics read it back out
    # of. Exported because `aligned` is: a caller who has the frame but not the name
    # has to spell "period" by hand, which is the literal `columns` exists to hold.
    "PERIOD",
    "aligned",
    "date_column",
    "default_pair",
    "demo_frame",
    "drawdown",
    "line_chart",
    "line_frame",
    "load_frame",
    "metrics",
    "returns",
    "series_columns",
    "summary",
    "summary_markdown",
]
