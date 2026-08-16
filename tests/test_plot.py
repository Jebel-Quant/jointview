"""Turning an aligned pair into a picture.

Two halves: ``line_frame``, which is the long-form data the chart is drawn from, and
``line_chart``, checked through the Vega-Lite spec it compiles to rather than by
rendering it.
"""

import polars as pl
import pytest

from jointview.data import demo_frame
from jointview.plot import SERIES, line_chart, line_frame


@pytest.fixture(scope="module")
def frame():
    """A demo frame big enough to thin, shared across the module — nothing here mutates it."""
    return demo_frame(rows=300)


def test_line_frame_is_one_column_per_series(frame):
    """The drawn frame carries the x-axis and the two series, under their own names."""
    assert line_frame(frame, "cash", "tech_fund").columns == ["period", "cash", "tech_fund"]


def test_line_frame_indexes_both_series_to_the_same_base(frame):
    """Rebasing is what makes a fund at 1.02 and one at 1,450 comparable."""
    drawn = line_frame(frame, "cash", "balanced", base=100.0)
    assert drawn["cash"][0] == pytest.approx(100.0)
    assert drawn["balanced"][0] == pytest.approx(100.0)


def test_line_frame_leaves_the_levels_alone_without_rebasing(frame):
    """Switched off, the raw levels reach the chart untouched."""
    drawn = line_frame(frame, "cash", "balanced", rebase=False)
    assert drawn["balanced"][0] == pytest.approx(frame["balanced"][0])


def test_line_frame_rebasing_preserves_the_shape(frame):
    """Indexing rescales the line; it must not bend it."""
    raw = line_frame(frame, "tech_fund", "cash", rebase=False)
    indexed = line_frame(frame, "tech_fund", "cash")
    ratio = raw["tech_fund"][-1] / raw["tech_fund"][0]
    assert indexed["tech_fund"][-1] / 100.0 == pytest.approx(ratio)


def test_line_frame_keeps_the_levels_when_a_series_starts_at_zero():
    """Dividing by a first value of zero would leave a column of infinities.

    Vega-Lite drops non-finite values, so the line would simply not be drawn — one
    line where the reader picked two, with nothing on the plot to say so. A cumulative
    P&L curve starts at zero by construction, so this is an ordinary frame rather than
    a broken one, and the levels it already carries are the honest thing to show.
    """
    pnl = pl.DataFrame({"strategy": [0.0, 5.0, 3.0], "benchmark": [1.0, 2.0, 4.0]})
    drawn = line_frame(pnl, "strategy", "benchmark")
    assert drawn["strategy"].to_list() == [0.0, 5.0, 3.0]


def test_line_frame_leaves_both_series_alone_when_only_one_starts_at_zero():
    """The fallback covers the pair, because a half-rebased plot is the worse answer.

    Indexing `benchmark` to 100 while `strategy` kept its own units would put two
    unrelated scales on one axis under a title claiming a shared one — the exact
    relationship the module refuses to invent.
    """
    pnl = pl.DataFrame({"strategy": [0.0, 5.0, 3.0], "benchmark": [50.0, 55.0, 60.0]})
    assert line_frame(pnl, "strategy", "benchmark")["benchmark"][0] == pytest.approx(50.0)


def test_line_frame_keeps_the_levels_when_a_series_starts_at_infinity():
    """A non-finite first value fails the same way a zero does, and is caught with it."""
    odd = pl.DataFrame({"broken": [float("inf"), 5.0, 3.0], "fine": [1.0, 2.0, 4.0]})
    assert line_frame(odd, "broken", "fine")["fine"].to_list() == [1.0, 2.0, 4.0]


def test_line_frame_survives_a_pair_that_never_overlaps():
    """No common sample means no first value to divide by, and no crash reaching for one."""
    disjoint = pl.DataFrame({"a": [1.0, None], "b": [None, 2.0]})
    assert line_frame(disjoint, "a", "b").height == 0


def test_line_chart_says_level_when_it_could_not_index(frame):
    """The axis names what the numbers under it are, not what was asked for.

    Falling back silently under a title reading "indexed to 100" would be a wrong
    label rather than a missing one — worse than the bug it replaces.
    """
    pnl = pl.DataFrame({"strategy": [0.0, 5.0, 3.0], "benchmark": [0.0, 2.0, 4.0]})
    spec = line_chart(pnl, "strategy", "benchmark", rebase=True).to_dict()
    assert spec["layer"][1]["encoding"]["y"]["title"] == "level"
    # The pair that can be indexed still says so, so the assertion above is about the
    # fallback rather than about the title always reading "level".
    indexed = line_chart(frame, "cash", "balanced", rebase=True).to_dict()
    assert indexed["layer"][1]["encoding"]["y"]["title"] == "indexed to 100"


def test_line_frame_draws_one_line_for_a_column_against_itself(frame):
    """A series against itself is one line, not two identical ones."""
    assert line_frame(frame, "cash", "cash").columns == ["period", "cash"]


def test_line_frame_thins_a_long_curve_but_keeps_the_end(frame):
    """Thinning is for the browser's sake, so it must not lose where the series got to."""
    drawn = line_frame(frame, "cash", "balanced", max_points=50)
    full = line_frame(frame, "cash", "balanced")
    assert drawn.height <= 50
    assert drawn["period"][-1] == full["period"][-1]
    assert drawn["cash"][-1] == pytest.approx(full["cash"][-1])


def test_line_chart_compiles_with_every_layer(frame):
    """The spec is built, not rendered — compiling it is what proves it is well formed."""
    spec = line_chart(frame, "world_equity", "bond_fund").to_dict()
    # crosshair, lines, hover markers, and one end label per series
    assert len(spec["layer"]) == 4


def test_line_chart_binds_a_colour_to_each_series_name(frame):
    """Colour is pinned to the series by name, so the two lines never swap."""
    spec = line_chart(frame, "world_equity", "bond_fund").to_dict()
    scale = spec["layer"][1]["encoding"]["color"]["scale"]
    assert scale["domain"] == ["world_equity", "bond_fund"]
    assert scale["range"] == list(SERIES)


def test_line_chart_uses_a_temporal_axis_when_there_is_a_date(frame):
    """A date column earns a real time axis, with the tick formatting that follows."""
    spec = line_chart(frame, "world_equity", "bond_fund").to_dict()
    assert spec["layer"][1]["encoding"]["x"]["type"] == "temporal"


def test_line_chart_falls_back_to_row_numbers(frame):
    """Without a date the axis is quantitative and says so, rather than inventing dates."""
    spec = line_chart(frame.drop("date"), "world_equity", "bond_fund").to_dict()
    assert spec["layer"][1]["encoding"]["x"]["type"] == "quantitative"
    assert spec["layer"][1]["encoding"]["x"]["title"] == "row"


def test_line_chart_rejects_an_unknown_column(frame):
    """The check happens before any spec is built."""
    with pytest.raises(KeyError):
        line_chart(frame, "cash", "nope")


def test_line_chart_survives_a_two_point_series():
    """The shortest thing that is still a line: no thinning, no dates, two points."""
    frame = pl.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    assert line_chart(frame, "a", "b").to_dict()["layer"]
