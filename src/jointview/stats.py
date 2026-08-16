"""Summary statistics for a single price or NAV series, computed by jQuantStats.

Everything here takes a frame of *levels* — a net asset value, an index, a price —
alongside the column that carries the period, and lets
[jQuantStats](https://github.com/jebel-quant/jquantstats) derive the returns and the
statistics from them.

Passing the period column rather than a bare series is what buys the accuracy: the
annualisation factor is read from the actual spacing of the observations, so a weekly
or monthly series is annualised as one, instead of every series being assumed daily.
A frame numbered by row rather than dated falls back to 252 periods a year, which is
what a bare series had to assume in every case.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import polars as pl
from jquantstats.data import Data

if TYPE_CHECKING:  # pragma: no cover
    from jquantstats._stats import Stats

PERIOD = "period"

MISSING = "—"


def _stats(frame: pl.DataFrame, column: str, *, date_col: str = PERIOD, rf: float = 0.0) -> Stats:
    """The jQuantStats view of one column of ``frame``.

    Raises:
        KeyError: if ``column`` or ``date_col`` is not in the frame.
    """
    for name in (date_col, column):
        if name not in frame.columns:
            raise KeyError(f"no column {name!r} in frame")  # noqa: TRY003
    # Gaps are dropped here rather than left to jQuantStats' own `null_strategy`, which
    # empties the frame outright when the price column carries a null.
    levels = frame.select(pl.col(date_col), pl.col(column).cast(pl.Float64)).drop_nulls()
    return Data.from_prices(levels, date_col=date_col, rf=rf).stats


def returns(frame: pl.DataFrame, column: str, *, date_col: str = PERIOD) -> pl.Series:
    """Simple period-over-period returns of a level series.

    >>> import polars as pl
    >>> frame = pl.DataFrame({"period": [0, 1, 2], "nav": [100.0, 110.0, 99.0]})
    >>> [round(value, 4) for value in returns(frame, "nav")]
    [0.1, -0.1]
    """
    stats = _stats(frame, column, date_col=date_col)
    return stats.returns[column]


def drawdown(frame: pl.DataFrame, column: str, *, date_col: str = PERIOD) -> pl.Series:
    """Distance below the running maximum, as a fraction — zero or negative.

    jQuantStats reports the same quantity as a positive depth, so the sign is flipped
    here: a drawdown is a fall, and every other rate in this module carries its
    direction in its sign.

    >>> import polars as pl
    >>> frame = pl.DataFrame({"period": [0, 1, 2], "nav": [100.0, 120.0, 60.0]})
    >>> round(drawdown(frame, "nav").min(), 4)
    -0.5
    """
    stats = _stats(frame, column, date_col=date_col)
    return -stats.drawdown()[column]


# Every entry is one call on the jQuantStats `Stats` object, in the order the panel
# shows them. Keeping it as data rather than fifteen lines of dict literal is what
# lets `metrics` stay a loop, and makes adding a statistic a one-line change.
STATISTICS: dict[str, str] = {
    "Total return": "comp",
    "Annual return": "cagr",
    "Annual volatility": "volatility",
    "Sharpe ratio": "sharpe",
    "Sortino ratio": "sortino",
    "Calmar ratio": "calmar",
    "Max drawdown": "max_drawdown",
    "Ulcer index": "ulcer_index",
    "Value at risk": "value_at_risk",
    "Hit rate": "win_rate",
    "Best period": "best",
    "Worst period": "worst",
    "Skew": "skew",
    "Kurtosis": "kurtosis",
}


def metrics(frame: pl.DataFrame, column: str, *, date_col: str = PERIOD, rf: float = 0.0) -> dict[str, float]:
    """The raw numbers behind the summary table, in natural units (0.07 is 7%).

    A figure that cannot be formed — a Sharpe ratio for a flat series, a growth rate
    for a series that touches zero — comes back as NaN or infinity rather than
    raising, so one odd column never blanks the whole table.

    Raises:
        ValueError: if there are too few observations to derive anything.

    >>> import polars as pl
    >>> frame = pl.DataFrame({"period": [0, 1, 2, 3], "nav": [100.0, 110.0, 105.0, 120.0]})
    >>> numbers = metrics(frame, "nav")
    >>> numbers["Observations"]
    4.0
    >>> round(numbers["Total return"], 4)
    0.2
    """
    stats = _stats(frame, column, date_col=date_col, rf=rf)
    levels = frame.get_column(column).drop_nulls().cast(pl.Float64)

    numbers: dict[str, float] = {
        "Observations": float(levels.len()),
        "Start": float(levels[0]),
        "End": float(levels[-1]),
    }
    for label, name in STATISTICS.items():
        numbers[label] = _number(stats, name, column)
    return numbers


def _number(stats: Stats, name: str, column: str) -> float:
    """One statistic as a float, with "could not be formed" spelled as NaN.

    Two things arrive here that are not numbers, and both mean the same thing. A
    sample too short to support a figure comes back as ``None`` — a kurtosis from four
    observations, say. And a series that never moves divides by zero on its way to a
    hit rate, because no period is a winner or a loser.

    Neither is a defect, and neither should reach the caller as an exception: this
    module's contract is that an unformable figure is NaN, which :func:`_format`
    already renders as a dash. A flat series is an ordinary column — a cash line — not
    an error condition.
    """
    try:
        value = getattr(stats, name)()[column]
    except ZeroDivisionError:
        return math.nan
    return math.nan if value is None else float(value)


# Levels keep their own units, rates get a sign, and the figures with no direction —
# volatility, the ratios, the shape statistics — do not.
FORMATS: dict[str, str] = {
    "Observations": "{:,.0f}",
    "Start": "{:,.2f}",
    "End": "{:,.2f}",
    "Total return": "{:+.2%}",
    "Annual return": "{:+.2%}",
    "Annual volatility": "{:.2%}",
    "Sharpe ratio": "{:.2f}",
    "Sortino ratio": "{:.2f}",
    "Calmar ratio": "{:.2f}",
    "Max drawdown": "{:.2%}",
    "Ulcer index": "{:.2%}",
    "Value at risk": "{:+.2%}",
    "Hit rate": "{:.1%}",
    "Best period": "{:+.2%}",
    "Worst period": "{:+.2%}",
    "Skew": "{:.2f}",
    "Kurtosis": "{:.2f}",
}


def summary(frame: pl.DataFrame, column: str, *, date_col: str = PERIOD, rf: float = 0.0) -> pl.DataFrame:
    """The same numbers as :func:`metrics`, formatted for display.

    >>> import polars as pl
    >>> frame = pl.DataFrame({"period": [0, 1, 2, 3], "nav": [100.0, 110.0, 105.0, 120.0]})
    >>> table = summary(frame, "nav")
    >>> table.columns
    ['metric', 'value']
    >>> table.row(by_predicate=pl.col("metric") == "Total return")[1]
    '+20.00%'
    """
    numbers = metrics(frame, column, date_col=date_col, rf=rf)
    return pl.DataFrame(
        {
            "metric": list(numbers),
            "value": [_format(name, value) for name, value in numbers.items()],
        }
    )


def summary_markdown(
    frame: pl.DataFrame,
    column: str,
    *,
    title: str | None = None,
    date_col: str = PERIOD,
    rf: float = 0.0,
) -> str:
    """A two-column markdown table, ready for ``mo.md``.

    >>> import polars as pl
    >>> frame = pl.DataFrame({"period": [0, 1, 2, 3], "nav": [100.0, 110.0, 105.0, 120.0]})
    >>> print(summary_markdown(frame, "nav", title="fund").splitlines()[0])
    | fund | |
    """
    table = summary(frame, column, date_col=date_col, rf=rf)
    header = f"| {title or column} | |", "|:---|---:|"
    body = (f"| {row['metric']} | {row['value']} |" for row in table.iter_rows(named=True))
    return "\n".join((*header, *body))


def _format(name: str, value: float) -> str:
    """Render one metric, falling back to ``MISSING`` for anything not finite.

    A NaN here is a figure that could not be formed rather than a bug — a Sharpe
    ratio without volatility, a growth rate from a start of zero — so it shows as
    a dash instead of blanking the row.

    >>> _format("Total return", 0.25)
    '+25.00%'
    >>> _format("Sharpe ratio", float("nan"))
    '—'
    """
    if not math.isfinite(value):
        return MISSING
    return FORMATS.get(name, "{:,.4g}").format(value)
