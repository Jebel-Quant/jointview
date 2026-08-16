"""The marimo notebook itself: two pickers, one chart, a summary table either side.

Run it with the ``jointview`` command rather than opening this file — see
:mod:`jointview.cli`, which starts marimo on this notebook and passes it ``--data``
and ``--height``.
"""

# The cell signatures below are marimo's, not ours: it names every cell ``_``, derives
# the parameters from what the cell reads, and rewrites both on save. Annotating them
# would be annotating generated code that the next edit in the marimo editor throws
# away — and the types are marimo's UI plumbing, so the annotations would be `Any`
# anyway. Told to ruff here rather than in a config file, so the reason sits next to
# the code it excuses. (ty asks for none of this; it does not require annotations.)
# ruff: noqa: ANN001, ANN202

import marimo

__generated_with = "0.23.15"
app = marimo.App(width="full")


@app.cell
def _():
    """Import marimo — the one cell every other cell here depends on."""
    import marimo as mo

    return (mo,)  # pragma: no cover


@app.cell
def _(mo) -> None:
    """Give the plot back the margins marimo reserves for prose."""
    # marimo pads a notebook for prose — 96px of side margin and 48px under the last
    # cell, twice over. This is a single-screen instrument, so those margins go back to
    # the plot. First cell so the trim is in the DOM before anything that sizes itself
    # against the page — the chart follows its container's width — is laid out.
    #
    # Matched on class *substrings* because the classes are Tailwind and carry colons;
    # if a future marimo renames them the rules stop applying and the app still lays
    # out, only roomier.
    mo.Html("""
    <style>
      #App [class*="xl:px-24"] { padding-inline: 0.75rem !important; }
      #App [class*="pb-24"] { padding-bottom: 0 !important; }
      #App .output-area { padding-inline: 0 !important; }
      /* vega-embed keeps a further 38px on the right for its own "..." menu. That one
         is out of reach — marimo renders the chart into a shadow root — and it buys
         the save/view-source menu, so it stays. */
    </style>
    """)
    return  # pragma: no cover


@app.cell
def _(mo):
    """Load the frame, and settle the two things the command line gets a say in."""
    from jointview.columns import aligned, default_pair, series_columns
    from jointview.data import load_frame
    from jointview.plot import line_chart
    from jointview.stats import summary_markdown

    # jointview navs.parquet --height 900
    frame = load_frame(mo.cli_args().get("data"))
    names = series_columns(frame)
    # Nothing on the page has a height for the plot to follow, so it is a number. 700
    # fills a laptop window once the notebook margins are gone; a tall monitor wants
    # more, and only the person looking at it knows which they have.
    plot_height = int(mo.cli_args().get("height") or 700)
    return (
        aligned,
        default_pair,
        frame,
        line_chart,
        names,
        plot_height,
        summary_markdown,
    )


@app.cell
def _(default_pair, frame, mo, names):
    """Build the two series pickers, opened on a pair worth looking at."""
    a_start, b_start = default_pair(frame)

    # One dropdown is the whole selector: it holds its own value, so there is no
    # mo.state and no two-way binding to keep in step. It also costs a fixed two lines
    # of the panel whatever the frame is — a radio list grew with the column count,
    # and a wide parquet would have turned the side panels into a scroll.
    def _pick(start):
        """One dropdown over every series, opened on the column at ``start``."""
        return mo.ui.dropdown(
            options=names,
            value=names[start],
            # Searchable from ten columns up, where scanning the list stops being
            # quicker than typing. Below that the search box is only in the way.
            searchable=len(names) >= 10,
            # There is no such thing as a plot of no series: the "--" entry would only
            # ever be a way to break the chart.
            allow_select_none=False,
            full_width=True,
        )

    a_pick, b_pick = _pick(a_start), _pick(b_start)
    return a_pick, b_pick


@app.cell
def _(mo):
    """The only control over the plot itself: whether to index both series to 100."""
    # Two NAVs on one axis only mean something on a shared scale; off, the raw levels
    # are there for a pair that already shares one.
    rebase = mo.ui.switch(value=True, label="index both to 100")
    return (rebase,)


@app.cell
def _(a_pick, aligned, b_pick, frame, line_chart, plot_height, rebase):
    """Read the pickers, and derive everything the layout below draws."""
    a_column = a_pick.value
    b_column = b_pick.value
    pair = aligned(frame, a_column, b_column)
    chart = line_chart(frame, a_column, b_column, rebase=rebase.value, height=plot_height)
    return a_column, b_column, chart, pair


@app.cell
def _(mo, summary_markdown):
    """The two pieces of furniture a side panel is made of."""

    def summary_table(pair, side, title):
        """A metric table for one side of ``pair``, or a note when the sample is too short.

        The whole aligned frame goes in rather than the column alone: jQuantStats reads
        the annualisation factor off the spacing of the period column, so the dates have
        to travel with the levels.
        """
        try:
            return mo.md(summary_markdown(pair, side, title=title))
        except (ValueError, KeyError):
            return mo.md(f"**{title}** — too few overlapping observations to summarise.")

    # A dropdown and seventeen metrics: the panel is now the same height whatever the
    # frame holds, so it no longer needs the scroll box that a per-column radio list
    # did. The wide gap keeps the split legible — the dropdown is a control, the
    # table under it is a result, and they should not read as one column of text.
    def panel(label, picker, table):
        """One side of the page: a heading, its picker, and the table underneath."""
        return mo.vstack(
            [
                mo.md(f"**{label}**"),
                mo.vstack([picker, table], gap=1.75),
            ],
            gap=0.5,
        )

    return panel, summary_table  # pragma: no cover


@app.cell
def _(a_column, b_column, chart, frame, mo, pair, rebase):
    """The middle column: the switch, the chart, and a line saying what it is of."""
    _dropped = frame.height - pair.height
    _note = f" of {frame.height:,}" if _dropped else ""
    caption = mo.md(
        # The multiplication sign is the character this means; a lowercase x beside two
        # column names reads as part of one of them.
        f"`{a_column}` × `{b_column}` — {pair.height:,}{_note} dates where both series "  # noqa: RUF001
        "are present, which is also what the tables summarise."
    )
    # No align= here: centring would shrink the stack to its content and hand the chart
    # back the gutter that "container" is there to fill.
    figure = mo.vstack([rebase, chart, caption], gap=0.25)
    return (figure,)


@app.cell
def _(a_column, a_pick, b_column, b_pick, figure, mo, pair, panel, summary_table) -> None:
    """Lay out the page: a picker and its table either side of the figure."""
    mo.hstack(
        [
            panel("left", a_pick, summary_table(pair, "a", a_column)),
            figure,
            panel("right", b_pick, summary_table(pair, "b", b_column)),
        ],
        # The side panels hold a dropdown and a two-column table; anything wider than
        # that is width taken off the picture.
        widths=[1, 6, 1],
        align="start",
        gap=0.75,
    )
    return  # pragma: no cover


if __name__ == "__main__":
    app.run()
