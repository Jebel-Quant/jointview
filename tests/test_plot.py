import polars as pl
import pytest

from jointview.data import demo_frame
from jointview.plot import encoding_type, joint_chart


@pytest.fixture(scope="module")
def frame():
    return demo_frame(rows=300)


@pytest.mark.parametrize(
    ("column", "expected"),
    [("returns", "quantitative"), ("date", "temporal"), ("sector", "nominal")],
)
def test_encoding_type_follows_the_dtype(frame, column, expected):
    assert encoding_type(frame.schema[column]) == expected


@pytest.mark.parametrize(
    ("x", "y"),
    [
        ("factor", "returns"),  # quantitative × quantitative
        ("date", "volume"),  # temporal × quantitative
        ("sector", "spread_bps"),  # nominal × quantitative
        ("noise", "noise"),  # the same column on both axes
    ],
)
def test_joint_chart_compiles_for_every_dtype_pair(frame, x, y):
    spec = joint_chart(frame, x, y).to_dict()
    assert len(spec["vconcat"]) == 2


def test_joint_chart_rejects_an_unknown_column(frame):
    with pytest.raises(KeyError):
        joint_chart(frame, "factor", "nope")


def rows(chart):
    """The rows Altair hoisted into the spec's shared, named dataset."""
    spec = chart.to_dict()
    return next(iter(spec["datasets"].values()))


def test_joint_chart_drops_null_rows():
    frame = pl.DataFrame({"a": [1.0, 2.0, None], "b": [1.0, None, 3.0]})
    assert rows(joint_chart(frame, "a", "b")) == [{"x": 1.0, "y": 1.0}]


def test_joint_chart_samples_down_a_large_frame(frame):
    assert len(rows(joint_chart(frame, "factor", "returns", max_points=25))) == 25
