"""Which columns the app can draw, and cutting a chosen pair down to its common sample.

This is the vocabulary both halves of the app are built on, and it belongs to neither
of them. :mod:`jointview.plot` draws what :func:`aligned` produces and
:mod:`jointview.stats` summarises it, so the column names and the shaping rules live
here rather than in either — two peers reaching into a third, instead of one reaching
into the other.

``PERIOD`` is the clearest case. It is the name :func:`aligned` writes the x-axis under
and the name the statistics read it back out of: a data contract between the two, not
a fact about plotting.
"""

from __future__ import annotations

import polars as pl

PERIOD = "period"


def series_columns(frame: pl.DataFrame) -> list[str]:
    """The columns that can be drawn: every numeric one.

    >>> import datetime as dt, polars as pl
    >>> frame = pl.DataFrame({"date": [dt.date(2024, 1, 1)], "nav": [1.0], "label": ["a"]})
    >>> series_columns(frame)
    ['nav']
    """
    return [name for name, dtype in frame.schema.items() if dtype.is_numeric()]


def date_column(frame: pl.DataFrame) -> str | None:
    """The first temporal column, which becomes the x-axis. None means row number.

    >>> import datetime as dt, polars as pl
    >>> date_column(pl.DataFrame({"when": [dt.date(2024, 1, 1)], "nav": [1.0]}))
    'when'
    >>> date_column(pl.DataFrame({"nav": [1.0]})) is None
    True
    """
    return next((name for name, dtype in frame.schema.items() if dtype.is_temporal()), None)


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
