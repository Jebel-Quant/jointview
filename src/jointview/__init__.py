"""Compare two price or NAV series of a Polars DataFrame side by side."""

from jointview.columns import PERIOD, aligned, date_column, default_pair, series_columns
from jointview.data import demo_frame, load_frame
from jointview.plot import drawn_points, line_chart, line_frame
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
    # What the chart actually draws, which past MAX_POINTS is not what it was given.
    # Exported for the same reason PERIOD is: the caption beside the plot has to say
    # which of the two numbers it is quoting, and so does anyone else drawing this frame.
    "drawn_points",
    "line_chart",
    "line_frame",
    "load_frame",
    "metrics",
    "returns",
    "series_columns",
    "summary",
    "summary_markdown",
]
