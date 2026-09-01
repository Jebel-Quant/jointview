"""The notebook, executed rather than rendered.

A marimo notebook is a runnable object: ``app.run()`` executes every cell in
dependency order and hands back their outputs and definitions. That is enough to
prove the page builds — the frame loads, both pickers open on real columns, the chart
compiles, the tables format — without a browser, a server, or a screenshot to compare
against. What it cannot check is how any of it looks.
"""

import runpy

import altair as alt
import polars as pl
import pytest

from jointview import cli
from jointview.app import app
from jointview.columns import WINDOW_ALL, WINDOWS
from jointview.plot import MAX_POINTS, drawn_points


@pytest.fixture(scope="module")
def notebook():
    """Run the notebook once and share the result — it builds a 1,500-row chart."""
    outputs, defs = app.run()
    return outputs, defs


def test_the_notebook_runs_every_cell(notebook):
    """Nine cells, each producing its output; a failure anywhere raises out of run()."""
    outputs, defs = notebook
    assert len(outputs) == 9
    assert defs["frame"].height > 0


def test_it_opens_on_two_different_series(notebook):
    """The demo frame has several columns, so the page should not open on a pair of one."""
    _, defs = notebook
    assert defs["a_column"] != defs["b_column"]
    assert {defs["a_column"], defs["b_column"]} <= set(defs["names"])


def test_the_pair_it_summarises_is_the_pair_it_draws(notebook):
    """The caption's promise: the tables describe exactly the rows behind the lines."""
    _, defs = notebook
    pair = defs["pair"]
    assert isinstance(pair, pl.DataFrame)
    assert pair.columns == ["period", "a", "b"]
    assert pair.height == defs["frame"].height


def test_the_window_row_offers_every_window_and_opens_on_the_whole_sample(notebook):
    """The chips over the plot are `columns.WINDOWS`, in its order, and none is preselected.

    A dated frame gets all four. The default is the whole sample because it is the only
    window that is not a choice — a file opens showing what is in it.
    """
    _, defs = notebook
    window = defs["window"]
    assert list(window.options) == list(WINDOWS)
    assert window.value == WINDOW_ALL


def test_the_window_defaulting_to_all_draws_the_whole_file(notebook):
    """Nothing is cut until a chip is clicked, so the pair still spans the frame."""
    _, defs = notebook
    assert defs["pair"].height == defs["frame"].height


def test_the_caption_names_the_window_the_sample_was_cut_to(notebook):
    """Under a cut the missing dates are a choice, and the caption says which one.

    `frame` in the caption is the whole file whatever is selected, so "90 of 1,500" on its
    own would read as 1,410 dates where a series was absent rather than as a window.
    """
    _, defs = notebook
    frame = defs["frame"]

    text = defs["caption"]("cash", "balanced", frame, defs["pair"].head(90), "ytd").text

    # Rendered markdown, so the backticks around the window's name have already become
    # a <code> element by the time the caption is a string.
    assert f"90 of {frame.height:,} dates inside <code>ytd</code> where both series are present" in text


def test_the_caption_has_no_window_to_name_when_nothing_was_cut(notebook):
    """`all` is the absence of a window, not a window called all, so it is not mentioned."""
    _, defs = notebook
    assert "inside" not in defs["caption"]("cash", "balanced", defs["frame"], defs["pair"]).text


def test_the_chart_is_a_compiled_layer_chart(notebook):
    """The notebook hands marimo a real chart, not a deferred builder."""
    _, defs = notebook
    assert isinstance(defs["chart"], alt.LayerChart)
    assert defs["chart"].to_dict()["layer"]


def test_the_plot_height_defaults_without_cli_args(notebook):
    """Run outside marimo there are no cli_args, which is the same as passing none."""
    _, defs = notebook
    assert defs["plot_height"] == 700


def test_a_panel_says_so_when_there_is_too_little_to_summarise(notebook):
    """Two series that barely overlap leave a table with nothing to compute.

    The panel prints a sentence instead of propagating the ValueError out of the cell
    and taking the whole page down with it.
    """
    _, defs = notebook
    lonely = pl.DataFrame({"period": [0], "a": [100.0]})
    assert "too few" in defs["summary_table"](lonely, "a", "tech_fund").text


def test_the_caption_says_the_tables_describe_the_lines(notebook):
    """Below the thinning cap the two numbers are one number, and the caption says so."""
    _, defs = notebook
    text = defs["caption"]("cash", "balanced", defs["frame"], defs["pair"]).text
    assert "1,500 dates where both series are present" in text
    assert "which is also what the tables summarise" in text


def test_the_caption_counts_the_dates_it_dropped(notebook):
    """A pair that does not span the frame is reported as a sample of it, not as all."""
    _, defs = notebook
    frame = defs["frame"]
    text = defs["caption"]("cash", "balanced", frame, defs["pair"].head(900)).text
    assert f"900 of {frame.height:,} dates" in text


def test_the_caption_does_not_call_a_thinned_curve_the_whole_sample(notebook):
    """Past the cap the chart draws fewer points than the tables summarise (#75).

    The caption used to quote the aligned height for both, so a 20,000-date parquet was
    described as 20,000 dates under a line of 3,335 points — and the max drawdown in the
    table beside it could sit at a date the line no longer carried a point for.
    """
    _, defs = notebook
    rows = MAX_POINTS * 5
    big = pl.DataFrame({"period": range(rows), "a": [1.0] * rows, "b": [2.0] * rows})

    text = defs["caption"]("tech_fund", "bond_fund", big, big).text

    assert f"{drawn_points(rows):,} points drawn from {rows:,} dates" in text
    assert f"the tables summarise all {rows:,}" in text
    assert drawn_points(rows) < rows


def test_running_the_file_directly_starts_the_app():
    """Marimo's own ``__main__`` guard — ``cli.APP`` is the very file the CLI launches."""
    runpy.run_path(str(cli.APP), run_name="__main__")
