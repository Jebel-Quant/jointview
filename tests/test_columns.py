import polars as pl
import pytest

from jointview.data import demo_frame
from jointview.plot import default_pair, joint_frame


def test_default_pair_prefers_numeric_columns():
    frame = demo_frame(rows=10)
    x, y = default_pair(frame)
    assert frame.dtypes[x].is_numeric()
    assert frame.dtypes[y].is_numeric()
    assert x != y


def test_default_pair_falls_back_to_whatever_is_there():
    frame = pl.DataFrame({"a": ["x"], "b": ["y"]})
    assert default_pair(frame) == (0, 1)


def test_default_pair_repeats_a_lone_column():
    assert default_pair(pl.DataFrame({"a": [1]})) == (0, 0)


def test_default_pair_rejects_an_empty_frame():
    with pytest.raises(ValueError, match="no columns"):
        default_pair(pl.DataFrame())


def test_joint_frame_accepts_the_same_column_twice():
    frame = pl.DataFrame({"a": [1.0, 2.0]})
    assert joint_frame(frame, "a", "a").columns == ["x", "y"]
