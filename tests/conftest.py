"""Shared resources: one canonical NAV table, written out in every format the app reads.

:data:`jointview.data.READERS` maps a suffix to the polars reader that opens it.
:data:`WRITERS` here is its mirror image, and the two are checked against each other in
``test_every_readable_suffix_has_a_resource`` rather than assumed to agree: a reader
added to the app without a way to produce a file for it then fails by name, instead of
quietly never being exercised. Line coverage cannot catch that on its own, because all
eight suffixes resolve through the same ``READERS.get(...)`` statement.

The files are generated per session rather than committed. Three of the eight suffixes
are the same IPC payload under different names, and a binary fixture in git has to be
regenerated whenever the writer that produced it changes its format — a maintenance
cost with no matching gain, since the writer and the reader ship in the same polars.
"""

import datetime as dt
from collections.abc import Callable
from pathlib import Path

import polars as pl
import pytest

# Deliberately small and hand-written rather than a slice of `demo_frame`: a round-trip
# is only legible if the expected numbers are on the page. Two funds three orders of
# magnitude apart, because that is the case the app exists for, and a fall in the middle
# so the levels are not monotone.
#
# `label` earns its place by being none of the above. The text formats have their dates
# parsed back out of strings on the way in, and the guarantee worth pinning is that the
# parsing is discriminating — a column of words has to survive as words, or every format
# would round-trip its dates by promoting anything that held still long enough.
CANONICAL = pl.DataFrame(
    {
        "date": [dt.date(2024, 1, 1), dt.date(2024, 1, 2), dt.date(2024, 1, 3)],
        "fund_a": [100.0, 101.0, 99.5],
        "fund_b": [1_450.0, 1_462.0, 1_455.0],
        "label": ["alpha", "beta", "gamma"],
    }
)

# One writer per entry in READERS, in the same order, so the two read as a pair. Each
# takes the frame and the path, where polars' own methods take the path alone — the
# uniform shape is what lets the fixture below stay a comprehension.
WRITERS: dict[str, Callable[[pl.DataFrame, Path], None]] = {
    ".arrow": lambda frame, path: frame.write_ipc(path),
    ".csv": lambda frame, path: frame.write_csv(path),
    ".feather": lambda frame, path: frame.write_ipc(path),
    ".ipc": lambda frame, path: frame.write_ipc(path),
    ".json": lambda frame, path: frame.write_json(path),
    ".ndjson": lambda frame, path: frame.write_ndjson(path),
    ".parquet": lambda frame, path: frame.write_parquet(path),
    ".tsv": lambda frame, path: frame.write_csv(path, separator="\t"),
}


@pytest.fixture(scope="session")
def resources(tmp_path_factory):
    """:data:`CANONICAL` on disk in every readable format, keyed by suffix.

    Session-scoped: the files are identical for every test that asks for them, and
    writing eight of them per test would be eight times the work for the same bytes.
    """
    directory = tmp_path_factory.mktemp("resources")
    return {suffix: _write(directory, suffix) for suffix in WRITERS}


def _write(directory, suffix):
    """:data:`CANONICAL` written into ``directory`` as ``navs<suffix>``."""
    path = directory / f"navs{suffix}"
    WRITERS[suffix](CANONICAL, path)
    return path
