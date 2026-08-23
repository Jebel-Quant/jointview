"""Which columns the app offers, and what it does to the pair you pick.

These cover :mod:`jointview.columns` — choosing the series, finding the x-axis, and
cutting the two columns down to the rows they share. What the drawing half then makes
of that frame is in :mod:`tests.test_plot`.
"""

import datetime as dt

import polars as pl
import pytest

import jointview
from jointview.columns import PERIOD, aligned, date_column, default_pair, series_columns
from jointview.data import demo_frame


def test_the_period_contract_is_on_the_public_surface():
    """`aligned` is exported, so the name of the column it writes has to be too.

    Without it the only way to read that frame back is to spell "period" at the call
    site — the one literal this module exists to keep in a single place.
    """
    assert jointview.PERIOD is PERIOD
    assert "PERIOD" in jointview.__all__


def test_series_columns_are_the_numeric_ones():
    """Only numbers can be a line, so the date column is not on offer."""
    frame = demo_frame(rows=10)
    assert "date" not in series_columns(frame)
    assert series_columns(frame) == frame.columns[1:]


def test_date_column_is_the_first_date_like_one():
    """The x-axis is found by dtype, not by being called "date"."""
    assert date_column(demo_frame(rows=10)) == "date"


def test_date_column_is_none_without_one():
    """No temporal column is a legitimate frame, not an error — the rows get numbered."""
    assert date_column(pl.DataFrame({"a": [1.0]})) is None


def test_date_column_takes_every_flavour_of_datetime():
    """A time unit and a time zone are not a different kind of axis."""
    stamps = [dt.datetime(2024, 1, 1, tzinfo=dt.UTC)]
    for dtype in (pl.Datetime("us"), pl.Datetime("ns"), pl.Datetime("ms", "Europe/Zurich")):
        frame = pl.DataFrame({"when": stamps}, schema={"when": dtype}).with_columns(nav=pl.lit(1.0))
        assert date_column(frame) == "when", dtype


@pytest.mark.parametrize(
    "quantity",
    [
        pytest.param(dt.timedelta(days=1), id="duration"),
        pytest.param(dt.time(9, 30), id="time"),
    ],
)
def test_date_column_does_not_mistake_a_temporal_quantity_for_the_axis(quantity):
    """A holding period or a time of day is temporal, and is still not a date (#74).

    `dtype.is_temporal()` is true of `Duration` and `Time` as well, so a frame carrying
    one of them *before* its dates used to have that taken as the period axis. Nothing
    failed: `stats` reads the annualisation factor off the spacing of whatever `aligned`
    wrote, and a column of timedeltas answered with a CAGR of about 2.5 trillion percent.
    """
    frame = pl.DataFrame(
        {
            "quantity": [quantity, quantity],
            "date": [dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
            "nav": [1.0, 1.1],
        }
    )
    assert date_column(frame) == "date"


def test_a_temporal_quantity_does_not_reach_the_period_column():
    """The consequence of the above, one layer up: `aligned` writes the dates.

    `date_column` is not read for its own sake — what it returns becomes `PERIOD`, and
    `PERIOD` is what the statistics are annualised from. This is the assertion that would
    have caught #74 from the outside.
    """
    frame = pl.DataFrame(
        {
            "held": [dt.timedelta(days=i) for i in range(3)],
            "date": [dt.date(2024, 1, 1 + i) for i in range(3)],
            "nav": [1.0, 1.1, 1.2],
        }
    )
    assert aligned(frame, "nav", "nav")[PERIOD].dtype == pl.Date


def test_default_pair_opens_on_the_first_two_series():
    """The app opens on something worth looking at rather than a series against itself."""
    assert default_pair(demo_frame(rows=10)) == (0, 1)


def test_default_pair_repeats_a_lone_series():
    """With one series there is no pair to make, so both sides show it."""
    assert default_pair(pl.DataFrame({"name": ["fund"], "a": [1.0]})) == (0, 0)


def test_default_pair_rejects_a_frame_with_nothing_to_draw():
    """A frame of no numeric columns cannot open the app at all."""
    with pytest.raises(ValueError, match="numeric"):
        default_pair(pl.DataFrame({"name": ["a"]}))


def test_aligned_keeps_only_the_common_sample():
    """A row where either series is absent describes neither line, so it goes."""
    frame = pl.DataFrame({"a": [1.0, 2.0, None], "b": [1.0, None, 3.0]})
    assert aligned(frame, "a", "b").rows() == [(0, 1.0, 1.0)]


def test_aligned_numbers_the_rows_without_a_date():
    """Without a date column the position in the frame becomes the x-axis."""
    frame = pl.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    assert aligned(frame, "a", "b")["period"].to_list() == [0, 1]


def test_aligned_sorts_by_date():
    """A frame in any order still draws left to right in time."""
    frame = pl.DataFrame({"date": [2, 1], "a": [1.0, 2.0], "b": [3.0, 4.0]}).with_columns(pl.col("date").cast(pl.Date))
    assert aligned(frame, "a", "b")["a"].to_list() == [2.0, 1.0]


def test_aligned_accepts_the_same_column_twice():
    """Both pickers on one series is a thing a user can do, so it has to hold up."""
    frame = pl.DataFrame({"a": [1.0, 2.0]})
    assert aligned(frame, "a", "a").columns == ["period", "a", "b"]


def test_aligned_rejects_an_unknown_column():
    """A name that is not in the frame is a mistake worth raising on."""
    with pytest.raises(KeyError):
        aligned(demo_frame(rows=10), "cash", "nope")


def test_aligned_rejects_a_column_that_cannot_be_drawn():
    """A column that exists but holds strings fails on its dtype, not its name."""
    frame = pl.DataFrame({"a": [1.0], "label": ["x"]})
    with pytest.raises(TypeError, match="cannot be drawn"):
        aligned(frame, "a", "label")
