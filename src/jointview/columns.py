"""Which columns the app can draw, and cutting a chosen pair down to its common sample.

This is the vocabulary both halves of the app are built on, and it belongs to neither
of them. :mod:`jointview.plot` draws what :func:`aligned` produces and
:mod:`jointview.stats` summarises it, so the column names and the shaping rules live
here rather than in either — two peers reaching into a third, instead of one reaching
into the other.

``PERIOD`` is the clearest case. It is the name :func:`aligned` writes the x-axis under
and the name the statistics read it back out of: a data contract between the two, not
a fact about plotting.

``WINDOWS`` is here for the same reason one layer out. Cutting the sample to the year to
date is not a fact about the drawing either: the window is taken off the frame once, and
the lines, the tables and the base a rebased pair is indexed to all follow from that one
cut instead of each making it themselves.
"""

from __future__ import annotations

from collections.abc import Callable

import polars as pl

PERIOD = "period"

WINDOW_ALL = "all"

# The stretches of the sample the app offers above the plot, in the order it offers them,
# each mapped to where it begins as a function of the last period in the frame.
#
# Measured back from that last period rather than from today: a parquet is as recent as
# it is, and a window read off the clock would come back empty on a series that ends last
# year — the same file being informative on Tuesday and blank on Wednesday.
#
# `None` is the whole sample. It is not "an offset of zero": it cuts nothing, and it is
# also how a caller knows there is no cut to mention.
WINDOWS: dict[str, Callable[[pl.Expr], pl.Expr] | None] = {
    WINDOW_ALL: None,
    # The turn of the year is a calendar boundary rather than a duration, which is why
    # this one truncates where the others count backwards.
    "ytd": lambda last: last.dt.truncate("1y"),
    "12m": lambda last: last.dt.offset_by("-12mo"),
    "36m": lambda last: last.dt.offset_by("-36mo"),
}


def series_columns(frame: pl.DataFrame) -> list[str]:
    """The columns that can be drawn: every numeric one.

    >>> import datetime as dt, polars as pl
    >>> frame = pl.DataFrame({"date": [dt.date(2024, 1, 1)], "nav": [1.0], "label": ["a"]})
    >>> series_columns(frame)
    ['nav']
    """
    return [name for name, dtype in frame.schema.items() if dtype.is_numeric()]


# Dates and datetimes, and deliberately not everything `dtype.is_temporal()` admits:
# that predicate is also true of `Time` and `Duration`. A holding period or a time of day
# is a temporal *quantity*, not a point on a calendar, and it cannot be the axis these
# series are observed along — `aligned` writes whatever this returns under `PERIOD`, and
# `stats` reads the annualisation factor off its spacing, so a column of timedeltas
# arriving here is answered with a CAGR in the trillions rather than an error (#74).
#
# Compared with `==` rather than `isinstance`, which is what polars documents for asking
# after a base type: `pl.Datetime` matches every time unit and time zone, so a
# `Datetime("ns", "Europe/Zurich")` is admitted without any of that being spelled here.
_DATE_LIKE = (pl.Date, pl.Datetime)


def date_column(frame: pl.DataFrame) -> str | None:
    """The first date or datetime column, which becomes the x-axis. None means row number.

    >>> import datetime as dt, polars as pl
    >>> date_column(pl.DataFrame({"when": [dt.date(2024, 1, 1)], "nav": [1.0]}))
    'when'
    >>> date_column(pl.DataFrame({"nav": [1.0]})) is None
    True

    A `Time` or `Duration` column is temporal but is not a date, and does not become the
    axis — the rows get numbered instead, which is the documented fallback:

    >>> date_column(pl.DataFrame({"held": [dt.timedelta(days=1)], "nav": [1.0]})) is None
    True
    """
    return next((name for name, dtype in frame.schema.items() if dtype in _DATE_LIKE), None)


def windowed(frame: pl.DataFrame, key: str = WINDOW_ALL) -> pl.DataFrame:
    """``frame`` cut to one of :data:`WINDOWS`, measured back from its last period.

    Applied to the frame rather than to the picture, so everything built from it agrees:
    the lines, the numbers beside them, and the base a rebased pair is indexed to.

    Raises:
        KeyError: if ``key`` is not one of :data:`WINDOWS`.

    >>> import datetime as dt, polars as pl
    >>> frame = pl.DataFrame(
    ...     {
    ...         "date": [dt.date(2022, 12, 30), dt.date(2023, 12, 29), dt.date(2024, 6, 28)],
    ...         "nav": [90.0, 100.0, 110.0],
    ...     }
    ... )
    >>> windowed(frame, "ytd")["date"].to_list()
    [datetime.date(2024, 6, 28)]
    >>> windowed(frame, "12m").height
    2
    >>> windowed(frame, "all").height
    3

    A window is a stretch of calendar, so a frame numbered by row has nothing to cut
    against and comes back whole:

    >>> windowed(pl.DataFrame({"nav": [1.0, 2.0]}), "ytd").height
    2
    """
    start = WINDOWS[key]
    date = date_column(frame)
    if start is None or date is None:
        return frame
    # `max()` rather than the last row: the frame reaching here need not be sorted, and
    # `aligned` does its own sorting afterwards.
    return frame.filter(pl.col(date) >= start(pl.col(date).max()))


def default_pair(frame: pl.DataFrame) -> tuple[int, int]:
    """Indices into :func:`series_columns` to open on — the first two series.

    A frame with a single series opens on it twice, rather than refusing to draw.

    >>> import polars as pl
    >>> default_pair(pl.DataFrame({"a": [1.0], "b": [2.0]}))
    (0, 1)
    >>> default_pair(pl.DataFrame({"only": [1.0]}))
    (0, 0)
    """
    names = series_columns(frame)
    if not names:
        raise ValueError("frame has no numeric columns to plot")  # noqa: TRY003
    return 0, 1 if len(names) > 1 else 0


def aligned(frame: pl.DataFrame, a: str, b: str) -> pl.DataFrame:
    """The two series on their common sample: ``period``, ``a``, ``b``, in order.

    Both the picture and the summary tables are built from this, so the numbers
    beside the chart always describe the lines in it. Renaming also sidesteps
    Vega-Lite's field-shorthand escaping and lets ``a`` and ``b`` be the same column.

    The three names are fixed whatever the columns were called, the rows come out
    sorted by period, and a date where either series is missing is not part of the
    sample — here the frame arrives unsorted and with a gap on the 2nd:

    >>> import datetime as dt, polars as pl
    >>> frame = pl.DataFrame(
    ...     {
    ...         "date": [dt.date(2024, 1, 3), dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
    ...         "x": [3.0, 1.0, None],
    ...         "y": [30.0, 10.0, 20.0],
    ...     }
    ... )
    >>> pair = aligned(frame, "x", "y")
    >>> pair.columns
    ['period', 'a', 'b']
    >>> pair["a"].to_list()
    [1.0, 3.0]
    """
    for column in (a, b):
        if column not in frame.columns:
            raise KeyError(f"no column {column!r} in frame")  # noqa: TRY003
        if not frame.schema[column].is_numeric():
            raise TypeError(f"column {column!r} is {frame.schema[column]}, which cannot be drawn")  # noqa: TRY003

    date = date_column(frame)
    period = pl.col(date).alias(PERIOD) if date else pl.int_range(pl.len()).alias(PERIOD)
    data = frame.select(period, pl.col(a).alias("a"), pl.col(b).alias("b"))
    return data.drop_nulls().sort(PERIOD)
