import polars as pl
import pytest

from jointview.data import demo_frame
from jointview.plot import SERIES, line_chart, line_frame


@pytest.fixture(scope="module")
def frame():
    return demo_frame(rows=300)


def test_line_frame_is_one_column_per_series(frame):
    assert line_frame(frame, "cash", "tech_fund").columns == ["period", "cash", "tech_fund"]


def test_line_frame_indexes_both_series_to_the_same_base(frame):
    drawn = line_frame(frame, "cash", "balanced", base=100.0)
    assert drawn["cash"][0] == pytest.approx(100.0)
    assert drawn["balanced"][0] == pytest.approx(100.0)


def test_line_frame_leaves_the_levels_alone_without_rebasing(frame):
    drawn = line_frame(frame, "cash", "balanced", rebase=False)
    assert drawn["balanced"][0] == pytest.approx(frame["balanced"][0])


def test_line_frame_rebasing_preserves_the_shape(frame):
    raw = line_frame(frame, "tech_fund", "cash", rebase=False)
    indexed = line_frame(frame, "tech_fund", "cash")
    ratio = raw["tech_fund"][-1] / raw["tech_fund"][0]
    assert indexed["tech_fund"][-1] / 100.0 == pytest.approx(ratio)


def test_line_frame_draws_one_line_for_a_column_against_itself(frame):
    assert line_frame(frame, "cash", "cash").columns == ["period", "cash"]


def test_line_frame_thins_a_long_curve_but_keeps_the_end(frame):
    drawn = line_frame(frame, "cash", "balanced", max_points=50)
    full = line_frame(frame, "cash", "balanced")
    assert drawn.height <= 50
    assert drawn["period"][-1] == full["period"][-1]
    assert drawn["cash"][-1] == pytest.approx(full["cash"][-1])


def test_line_chart_compiles_with_every_layer(frame):
    spec = line_chart(frame, "world_equity", "bond_fund").to_dict()
    # crosshair, lines, hover markers, and one end label per series
    assert len(spec["layer"]) == 4


def test_line_chart_binds_a_colour_to_each_series_name(frame):
    spec = line_chart(frame, "world_equity", "bond_fund").to_dict()
    scale = spec["layer"][1]["encoding"]["color"]["scale"]
    assert scale["domain"] == ["world_equity", "bond_fund"]
    assert scale["range"] == list(SERIES)


def test_line_chart_uses_a_temporal_axis_when_there_is_a_date(frame):
    spec = line_chart(frame, "world_equity", "bond_fund").to_dict()
    assert spec["layer"][1]["encoding"]["x"]["type"] == "temporal"


def test_line_chart_falls_back_to_row_numbers(frame):
    spec = line_chart(frame.drop("date"), "world_equity", "bond_fund").to_dict()
    assert spec["layer"][1]["encoding"]["x"]["type"] == "quantitative"
    assert spec["layer"][1]["encoding"]["x"]["title"] == "row"


def test_line_chart_rejects_an_unknown_column(frame):
    with pytest.raises(KeyError):
        line_chart(frame, "cash", "nope")


def test_line_chart_survives_a_two_point_series():
    frame = pl.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    assert line_chart(frame, "a", "b").to_dict()["layer"]
