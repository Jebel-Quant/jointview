"""Getting a frame into the app — the generated demo one, and the file you pass it."""

from pathlib import Path

import polars as pl
import pytest

from jointview.data import demo_frame, load_frame


def test_demo_frame_is_deterministic():
    """The demo is seeded, so a screenshot or a doc example stays true."""
    assert demo_frame(rows=50).equals(demo_frame(rows=50))


def test_demo_frame_is_a_date_plus_nav_series():
    """It has the shape the app expects of any frame: one date, then numbers."""
    frame = demo_frame(rows=50)
    date, *funds = frame.columns
    assert frame.schema[date].is_temporal()
    assert all(frame.schema[name].is_numeric() for name in funds)
    assert len(funds) > 1


def test_demo_frame_navs_stay_positive():
    """A NAV that reaches zero would break rebasing, and no real fund does it."""
    frame = demo_frame(rows=200).drop("date")
    assert all(frame[name].min() > 0 for name in frame.columns)


def test_demo_frame_skips_weekends():
    """Weekdays only, so 252 periods really are about a year."""
    dates = demo_frame(rows=200)["date"]
    assert dates.dt.weekday().max() <= 5
    assert dates.is_sorted()


def test_demo_frame_series_start_where_they_were_asked_to():
    """The whole point of the demo is series on scales that need indexing."""
    # Within one day's move of the configured level, since the first row is already
    # one step in.
    frame = demo_frame(rows=50)
    assert 0.9 < frame["world_equity"][0] / 100.0 < 1.1
    assert 0.9 < frame["balanced"][0] / 1_450.0 < 1.1


def test_load_frame_falls_back_to_the_demo():
    """`jointview` with no file still opens on something."""
    assert load_frame(None).columns == demo_frame().columns


def test_load_frame_round_trips_parquet(tmp_path):
    """The common case: a parquet of NAVs, read back whole."""
    file = tmp_path / "frame.parquet"
    demo_frame(rows=20).write_parquet(file)
    assert load_frame(file).height == 20


def test_load_frame_rejects_an_unknown_suffix(tmp_path):
    """An unreadable extension names the ones that would have worked."""
    file = tmp_path / "frame.xlsx"
    file.touch()
    with pytest.raises(ValueError, match="supported"):
        load_frame(file)


def test_load_frame_reports_a_missing_file(tmp_path):
    """A typo in the path fails as a missing file, not as an empty frame."""
    with pytest.raises(FileNotFoundError):
        load_frame(tmp_path / "absent.parquet")


def test_load_frame_reports_a_directory_as_one(tmp_path):
    """A directory is named as a directory, not rejected for its extension.

    The suffix lookup would otherwise call this an unsupported format, which sends
    the reader looking for a typo in an extension that was never there.
    """
    with pytest.raises(IsADirectoryError, match="not a file"):
        load_frame(tmp_path)


def test_load_frame_says_something_useful_about_an_empty_path(tmp_path, monkeypatch):
    """``Path("")`` is ``Path(".")``, so it arrives as the current directory.

    The empty string is the "no path" sentinel and returns the demo frame; an empty
    ``Path`` cannot be, because Python normalises it away at construction. The two
    genuinely differ, and the guarantee is that neither ends in a message quoting an
    empty name. Pinned because the directory branch is the only thing standing
    between an empty Path and `cannot read ''`.
    """
    monkeypatch.chdir(tmp_path)
    assert load_frame("").columns == demo_frame().columns
    with pytest.raises(IsADirectoryError, match=r"not a file: \."):
        load_frame(Path(""))


def test_load_frame_reads_a_csv_of_navs(tmp_path):
    """Not everything arrives as parquet; the reader is chosen by suffix."""
    file = tmp_path / "navs.csv"
    pl.DataFrame({"date": ["2024-01-01"], "fund": [100.0]}).write_csv(file)
    assert load_frame(file)["fund"][0] == 100.0
