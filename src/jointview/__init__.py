"""Compare two price or NAV series of a Polars DataFrame side by side."""

from jointview.data import demo_frame, load_frame
from jointview.plot import (
    aligned,
    date_column,
    default_pair,
    line_chart,
    line_frame,
    series_columns,
)
from jointview.stats import drawdown, metrics, returns, summary, summary_markdown

__all__ = [
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
