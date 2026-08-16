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

READERS: dict[str, Callable[[Path], pl.DataFrame]] = {
    ".arrow": pl.read_ipc,
    ".csv": pl.read_csv,
    ".feather": pl.read_ipc,
    ".ipc": pl.read_ipc,
    ".json": pl.read_json,
    ".ndjson": pl.read_ndjson,
    ".parquet": pl.read_parquet,
    ".tsv": lambda p: pl.read_csv(p, separator="\t"),
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
