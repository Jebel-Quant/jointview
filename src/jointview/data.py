"""Getting a DataFrame into the app.

The app is handed a path on the command line; when there is none it falls back to
a generated frame so that ``marimo run app.py`` works out of the box.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl

# Every entry has to hand back a frame whose dates are dates. The binary formats carry
# a schema and do it for free; the text ones cannot say that a column of "2024-01-01"
# was ever anything but text, so each says here how it recovers them. It matters beyond
# the x-axis: `stats` reads the annualisation factor off the spacing of the period
# column, and a date column arriving as text costs a weekly series its real one.
READERS: dict[str, Callable[[Path], pl.DataFrame]] = {
    ".arrow": pl.read_ipc,
    ".csv": lambda p: pl.read_csv(p, try_parse_dates=True),
    ".feather": pl.read_ipc,
    ".ipc": pl.read_ipc,
    # No try_parse_dates on the JSON readers — polars offers the hook for CSV only — so
    # the same promotion is done on the way out instead.
    ".json": lambda p: _with_dates(pl.read_json(p)),
    ".ndjson": lambda p: _with_dates(pl.read_ndjson(p)),
    ".parquet": pl.read_parquet,
    ".tsv": lambda p: pl.read_csv(p, separator="\t", try_parse_dates=True),
}

# name: starting level, sensitivity to the common market move, daily drift of its
# own, and the size of the wobble nobody else shares.
FUNDS: dict[str, tuple[float, float, float, float]] = {
    "world_equity": (100.0, 1.00, 0.00000, 0.0030),
    "tech_fund": (48.5, 1.35, 0.00030, 0.0090),
    "value_fund": (212.0, 0.85, 0.00005, 0.0060),
    "balanced": (1_450.0, 0.45, 0.00010, 0.0030),
    "bond_fund": (98.0, 0.10, 0.00004, 0.0020),
    "cash": (1.0, 0.00, 0.00008, 0.00002),
}


def load_frame(path: str | Path | None) -> pl.DataFrame:
    """Read a DataFrame from ``path``, or build the demo frame when it is None.

    The suffix picks the reader, so no path means the generated frame rather than
    an error — which is what makes ``marimo run app.py`` work with no arguments:

    >>> load_frame(None).columns[0]
    'date'

    Whatever the format, a column of dates arrives as dates: the text formats have no
    way to record that one ever was, so they are parsed back on the way in. A column
    that does not read as dates all the way down is left as the text it is.

    A path that is not there is reported before a reader is chosen, so the message
    names the file rather than complaining about its extension:

    >>> load_frame("nowhere.parquet")
    Traceback (most recent call last):
        ...
    FileNotFoundError: no such file: nowhere.parquet

    A directory is named as one. This is also where an empty ``Path`` lands, since
    ``Path("")`` is ``Path(".")`` — the two are the same object by the time anything
    here sees them, so the current directory is what actually arrived:

    >>> load_frame(".")
    Traceback (most recent call last):
        ...
    IsADirectoryError: not a file: .
    """
    # Only the empty *string* is the "no path" sentinel: it is what marimo hands over
    # for a flag that was not passed. A Path cannot carry it — see the docstring.
    if path is None or path == "":
        return demo_frame()

    file = Path(path).expanduser()
    if not file.exists():
        raise FileNotFoundError(f"no such file: {file}")  # noqa: TRY003

    # Before the suffix lookup, which would otherwise reject a directory for having
    # the wrong extension — and an empty one for having no name to quote at all.
    if file.is_dir():
        raise IsADirectoryError(f"not a file: {file}")  # noqa: TRY003

    reader = READERS.get(file.suffix.lower())
    if reader is None:
        supported = ", ".join(sorted(READERS))
        raise ValueError(f"cannot read {file.suffix or file.name!r}; supported: {supported}")  # noqa: TRY003

    return reader(file)


def demo_frame(rows: int = 1_500, seed: int = 42) -> pl.DataFrame:
    """Daily NAVs for a handful of made-up funds, on deliberately different scales.

    They share a market factor, so the lines rhyme without being copies, and they
    start anywhere from 1 to 1,450 — which is exactly the case that needs indexing
    before two of them can be read on one axis.

    The dates come first, so the frame is ready for :func:`jointview.plot.line_chart`
    as it stands, and ``seed`` makes it the same frame every time:

    >>> frame = demo_frame(rows=10)
    >>> frame.columns[:2]
    ['date', 'world_equity']
    >>> frame.height
    10
    """
    rng = np.random.default_rng(seed)
    market = rng.normal(0.0004, 0.011, rows)

    navs = {
        name: start * np.cumprod(1.0 + drift + beta * market + rng.normal(0.0, wobble, rows))
        for name, (start, beta, drift, wobble) in FUNDS.items()
    }
    return pl.DataFrame({"date": _business_days(date(2020, 1, 1), rows), **navs})


def _business_days(start: date, rows: int) -> pl.Series:
    """``rows`` weekdays from ``start``, so 252 periods really are about a year."""
    days = pl.date_range(start, start + timedelta(days=2 * rows), "1d", eager=True)
    return days.filter(days.dt.weekday() <= 5).head(rows).alias("date")


def _with_dates(frame: pl.DataFrame) -> pl.DataFrame:
    """``frame`` with every text column that reads cleanly as dates promoted to dates.

    What :func:`pl.read_csv`'s ``try_parse_dates`` does during the parse, done after it
    — the JSON readers take no such flag, and ``schema_overrides`` would need the column
    named in advance, which is exactly what is not known here.
    """
    promoted = []
    for name, dtype in frame.schema.items():
        if dtype == pl.String:
            parsed = _as_dates(frame[name])
            if parsed is not None:
                promoted.append(parsed.alias(name))
    return frame.with_columns(promoted)


def _as_dates(column: pl.Series) -> pl.Series | None:
    """``column`` read as dates, or None where it is text that merely looks like some.

    The bar is the whole column: a fund name, a code that happens to be eight digits,
    or a date column with one bad row all stay as they arrived. Promoting on a partial
    match would turn the rows that failed into nulls, and a null in the period column
    is a row silently dropped from both the plot and the summary beside it.
    """
    try:
        parsed = column.str.to_date(strict=False)
    except pl.exceptions.ComputeError:
        # Raised when no format fits *any* value — ordinary text. `strict=False` governs
        # the values that fail once a format is chosen, not the choosing of it.
        return None
    # A value that did not parse comes back null, so an unchanged null count is the test
    # for "every row was a date". The second clause is what stops a column of nothing
    # becoming a column of no dates: polars hands an all-null column over as `Null`
    # rather than `String` today, so nothing reaches here to need it, but a dateless
    # date column would be a poor thing to acquire on the strength of that.
    return parsed if parsed.null_count() == column.null_count() < parsed.len() else None
