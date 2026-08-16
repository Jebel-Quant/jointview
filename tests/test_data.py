"""Getting a frame into the app — the generated demo one, and the file you pass it."""

import datetime as dt
from pathlib import Path

import polars as pl
import pytest
from conftest import CANONICAL, WRITERS

from jointview.columns import aligned, date_column, series_columns
from jointview.data import READERS, demo_frame, load_frame
from jointview.stats import metrics


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


def test_every_readable_suffix_has_a_resource():
    """The two maps are mirror images, so no reader can slip through untested.

    Parametrising over ``READERS`` below is only worth as much as the fixture's cover
    of it. Asserted here rather than left to a ``KeyError`` inside the fixture, because
    the failure should name the suffix nobody wrote a case for.
    """
    assert set(WRITERS) == set(READERS)


@pytest.mark.parametrize("suffix", sorted(READERS))
def test_load_frame_reads_every_supported_format(resources, suffix):
    """Every suffix the command line advertises opens, with the same numbers inside.

    All eight resolve through one ``READERS.get`` statement, so line coverage says
    nothing about whether the entries behind it work — a separator typo in the ``.tsv``
    lambda would leave the suite at 100% and the format broken.

    Compared column by column rather than with ``DataFrame.equals``, which ignores
    dtypes: it calls a date column read back as text equal to the dates that produced
    it, and the dtypes are half of what these cases are here to check.
    """
    frame = load_frame(resources[suffix])
    assert frame.columns == CANONICAL.columns
    assert frame["fund_a"].to_list() == CANONICAL["fund_a"].to_list()
    assert frame["fund_b"].to_list() == CANONICAL["fund_b"].to_list()
    assert frame["label"].to_list() == CANONICAL["label"].to_list()


@pytest.mark.parametrize("suffix", sorted(READERS))
def test_every_format_offers_both_funds_as_series(resources, suffix):
    """Whatever the file was, the app finds the same two columns to draw.

    `label` is the control: it rides through every format and must never be offered,
    which is what makes this more than a column count.
    """
    assert series_columns(load_frame(resources[suffix])) == ["fund_a", "fund_b"]


@pytest.mark.parametrize("suffix", sorted(READERS))
def test_every_format_gives_the_app_a_temporal_axis(resources, suffix):
    """A date is a date whichever file it came out of — the point of the whole map.

    The text formats have no schema to carry it, so ``load_frame`` parses it back. Were
    this to regress, the plot would quietly renumber its x-axis by row and the summary
    beside it would annualise on the 252-day assumption rather than the real spacing.
    """
    assert date_column(load_frame(resources[suffix])) == "date"
    assert load_frame(resources[suffix])["date"].to_list() == CANONICAL["date"].to_list()


@pytest.mark.parametrize("suffix", sorted(READERS))
def test_no_format_promotes_the_text_column(resources, suffix):
    """Recovering dates must not sweep up words on the way past."""
    assert load_frame(resources[suffix]).schema["label"] == pl.String


def test_a_weekly_csv_is_annualised_as_weekly(tmp_path):
    """Why the dates are parsed back at all, stated in the units a reader would feel.

    Reaches across into `stats` on purpose, and lives here rather than there because
    the regression it guards against is a change to `load_frame`. Without the parsing
    the dates arrive as text, `aligned` numbers the rows instead, and jQuantStats
    annualises 1% a week on the 252-day assumption — about 1,128% a year against a true
    68%. Both are finite, neither raises, and the table shows the wrong one.
    """
    weeks = 30
    frame = pl.DataFrame(
        {
            "date": [dt.date(2024, 1, 1) + dt.timedelta(weeks=week) for week in range(weeks)],
            "fund": [100.0 * 1.01**week for week in range(weeks)],
        }
    )
    file = tmp_path / "weekly.csv"
    frame.write_csv(file)

    pair = aligned(load_frame(file), "fund", "fund")
    assert metrics(pair, "a")["Annual return"] == pytest.approx(1.01**52 - 1, rel=0.01)


def test_a_column_of_part_dates_stays_text(tmp_path):
    """One unparseable row and the column is text, rather than a date with a hole in it.

    Promoting on a partial match turns the rows that failed into nulls, and a null in
    the period column is a row dropped from the plot and from the table beside it —
    a silently shorter sample, which is worse than an x-axis of row numbers.
    """
    file = tmp_path / "partial.ndjson"
    file.write_text('{"when": "2024-01-01", "nav": 1.0}\n{"when": "later that year", "nav": 2.0}\n')
    assert load_frame(file).schema["when"] == pl.String


def test_a_column_of_nothing_is_not_mistaken_for_dates(tmp_path):
    """A column with no values in it must not arrive as a column of no dates.

    polars types an all-null NDJSON column as ``Null`` rather than ``String``, so the
    promotion never sees it — but what matters to the app is the guarantee, not the
    route to it: `date_column` picks the *first* temporal column, and an empty one
    promoted to `Date` would take the x-axis from the real dates further along.
    """
    file = tmp_path / "empty.ndjson"
    file.write_text('{"when": null, "on": "2024-01-01", "nav": 1.0}\n{"when": null, "on": "2024-01-02", "nav": 2.0}\n')
    frame = load_frame(file)
    assert not frame.schema["when"].is_temporal()
    assert date_column(frame) == "on"


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
