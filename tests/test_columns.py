import polars as pl
import pytest

from jointview.data import demo_frame
from jointview.plot import aligned, date_column, default_pair, series_columns


def test_series_columns_are_the_numeric_ones():
    frame = demo_frame(rows=10)
    assert "date" not in series_columns(frame)
    assert series_columns(frame) == frame.columns[1:]


def test_date_column_is_the_first_temporal_one():
    assert date_column(demo_frame(rows=10)) == "date"


def test_date_column_is_none_without_one():
    assert date_column(pl.DataFrame({"a": [1.0]})) is None


def test_default_pair_opens_on_the_first_two_series():
    assert default_pair(demo_frame(rows=10)) == (0, 1)


def test_default_pair_repeats_a_lone_series():
    assert default_pair(pl.DataFrame({"name": ["fund"], "a": [1.0]})) == (0, 0)


def test_default_pair_rejects_a_frame_with_nothing_to_draw():
    with pytest.raises(ValueError, match="numeric"):
        default_pair(pl.DataFrame({"name": ["a"]}))


def test_aligned_keeps_only_the_common_sample():
    frame = pl.DataFrame({"a": [1.0, 2.0, None], "b": [1.0, None, 3.0]})
    assert aligned(frame, "a", "b").rows() == [(0, 1.0, 1.0)]


def test_aligned_numbers_the_rows_without_a_date():
    frame = pl.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    assert aligned(frame, "a", "b")["period"].to_list() == [0, 1]


def test_aligned_sorts_by_date():
    frame = pl.DataFrame({"date": [2, 1], "a": [1.0, 2.0], "b": [3.0, 4.0]}).with_columns(
        pl.col("date").cast(pl.Date)
    )
    assert aligned(frame, "a", "b")["a"].to_list() == [2.0, 1.0]


def test_aligned_accepts_the_same_column_twice():
    frame = pl.DataFrame({"a": [1.0, 2.0]})
    assert aligned(frame, "a", "a").columns == ["period", "a", "b"]


def test_aligned_rejects_an_unknown_column():
    with pytest.raises(KeyError):
        aligned(demo_frame(rows=10), "cash", "nope")


def test_aligned_rejects_a_column_that_cannot_be_drawn():
    frame = pl.DataFrame({"a": [1.0], "label": ["x"]})
    with pytest.raises(TypeError, match="cannot be drawn"):
        aligned(frame, "a", "label")
