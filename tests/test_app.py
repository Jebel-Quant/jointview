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
    lonely = pl.Series("tech_fund", [100.0])
    assert "too few" in defs["summary_table"](lonely, "tech_fund").text


def test_running_the_file_directly_starts_the_app():
    """Marimo's own ``__main__`` guard — ``cli.APP`` is the very file the CLI launches."""
    runpy.run_path(str(cli.APP), run_name="__main__")
