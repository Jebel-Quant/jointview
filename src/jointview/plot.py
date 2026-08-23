"""Two price or NAV series drawn as two lines on one pair of axes.

The two columns are put on a shared y-axis rather than one axis each: two scales on
one plot invent a relationship that is not in the data. Where the levels are far
apart, ``rebase`` indexes both to the same starting value instead, which is the
honest way to compare a series priced at 12 with one priced at 4,000.

Choosing the columns and cutting them to their common sample happens before any of
this, in :mod:`jointview.columns`.
"""

from __future__ import annotations

import math
from typing import Literal, cast

import altair as alt
import polars as pl

from jointview.columns import PERIOD, aligned, date_column

# Categorical slots 1 and 2 (blue, orange). The pair clears the contrast, chroma and
# colour-vision separation floors against both the light (#fcfcfb) and the dark
# (#1a1a19) chart surface, so it survives marimo's theme switch without being
# redefined. CONTEXT is chrome — the crosshair — not a series.
SERIES = ("#2a78d6", "#d95926")
CONTEXT = "#8a8a84"

BASE = 100.0
MAX_POINTS = 4_000

# Narrower than `str`, because altair's `type=` only accepts its four measurement kinds
# and these are the two an x-axis of periods can be. Inside one function the literal was
# inferred; passing it between them needs the type spelled out.
XType = Literal["temporal", "quantitative"]


def line_frame(
    frame: pl.DataFrame,
    a: str,
    b: str,
    *,
    rebase: bool = True,
    base: float = BASE,
    max_points: int = MAX_POINTS,
) -> pl.DataFrame:
    """What the chart draws: one ``period`` column and one column per named series.

    Wide rather than long, because the crosshair reads every series at the hovered
    period out of a single row.

    >>> import polars as pl
    >>> frame = pl.DataFrame({"cash": [1.0, 1.01, 1.02], "balanced": [1450.0, 1479.0, 1465.0]})
    >>> drawn = line_frame(frame, "cash", "balanced")
    >>> drawn.columns
    ['period', 'cash', 'balanced']

    Rebasing is what lets those two share a y-axis at all: both leave the first
    period at ``base``, whatever they were priced at.

    >>> round(drawn["cash"][0], 6), round(drawn["balanced"][0], 6)
    (100.0, 100.0)

    A column against itself is one line rather than two identical ones:

    >>> line_frame(frame, "cash", "cash").columns
    ['period', 'cash']

    A series starting at zero cannot be indexed — a cumulative P&L curve starts there
    by construction — so the pair keeps its own levels instead:

    >>> pnl = pl.DataFrame({"strategy": [0.0, 5.0, 3.0], "benchmark": [0.0, 2.0, 4.0]})
    >>> line_frame(pnl, "strategy", "benchmark")["strategy"].to_list()
    [0.0, 5.0, 3.0]
    """
    wide, _ = _wide(frame, a, b, rebase=rebase, base=base, max_points=max_points)
    return wide


def line_chart(
    frame: pl.DataFrame,
    a: str,
    b: str,
    *,
    rebase: bool = True,
    base: float = BASE,
    width: int | str = "container",
    height: int | str = 700,
    max_points: int = MAX_POINTS,
) -> alt.LayerChart:
    """Draw columns ``a`` and ``b`` of ``frame`` as two lines against time.

    Four layers over one plotting area — the crosshair, the lines, the hover markers
    and the end labels — handed back as a plain Altair chart, so nothing here needs
    marimo to draw it:

    >>> import polars as pl
    >>> frame = pl.DataFrame({"cash": [1.0, 1.01, 1.02], "balanced": [1450.0, 1479.0, 1465.0]})
    >>> chart = line_chart(frame, "cash", "balanced")
    >>> type(chart).__name__
    'LayerChart'
    >>> len(chart.to_dict()["layer"])
    4

    Width defaults to ``"container"``: the plot takes whatever the column around it
    gives it, which is the point of a full-width app. Height stays a number, because
    nothing in the page has a height for a chart to follow — 700 fills a laptop window
    once the notebook margins are out of the way, without spilling off a short one.

    Asking to rebase a pair that cannot be indexed draws the raw levels, and the
    y-axis says ``level`` rather than claiming otherwise — see :func:`_rebasable`.
    The title is read back out of the compiled spec, because that is the only place it
    exists; layer 1 is :func:`_lines`, the series themselves:

    >>> chart.to_dict()["layer"][1]["encoding"]["y"]["title"]
    'indexed to 100'
    >>> pnl = pl.DataFrame({"strategy": [0.0, 5.0, 3.0], "benchmark": [0.0, 2.0, 4.0]})
    >>> line_chart(pnl, "strategy", "benchmark").to_dict()["layer"][1]["encoding"]["y"]["title"]
    'level'
    """
    wide, rebased = _wide(frame, a, b, rebase=rebase, base=base, max_points=max_points)
    names = [name for name in wide.columns if name != PERIOD]

    date = date_column(frame)
    x_type: XType = "temporal" if date else "quantitative"
    x_title = date or "row"
    # `rebased`, not `rebase`: the title names what the numbers underneath actually are.
    y_title = f"indexed to {base:g}" if rebased else "level"
    x = alt.X(PERIOD, type=x_type, title=x_title)

    # Made here rather than inside a layer because two of them share it: the crosshair
    # carries the parameter, the markers only read it.
    hover = _hover()
    lines = _lines(wide, names, x, y_title)
    return (
        alt.layer(
            _crosshair(wide, names, x, x_type, x_title, hover),
            lines,
            _markers(lines, hover),
            _end_labels(wide, names, x),
        )
        .resolve_scale(color="shared")
        .configure_axis(grid=True, gridOpacity=0.3, domain=False, labelPadding=4, tickSize=4)
        .configure_view(stroke=None)
        .configure_legend(labelFontSize=12)
        .properties(
            # One plotting area for all four layers, sized at the top level so a
            # container width is measured once rather than per layer.
            width=width,
            height=height,
            # Only the right margin earns its keep: it is where the end labels go.
            padding={"left": 0, "top": 0, "bottom": 0, "right": 76},
            # "pad", the default, grows the figure past the box it was given and puts
            # the gutter back; fitting spends the padding out of the size instead.
            autosize=_autosize(width, height),
        )
    )


def _wide(
    frame: pl.DataFrame,
    a: str,
    b: str,
    *,
    rebase: bool,
    base: float,
    max_points: int,
) -> tuple[pl.DataFrame, bool]:
    """The frame the chart is drawn from, and whether it ended up indexed after all.

    One decision point for two callers. :func:`line_frame` wants the frame;
    :func:`line_chart` wants the answer too, because an axis labelled "indexed to 100"
    over unindexed levels is a wrong label rather than a missing one.
    """
    data = aligned(frame, a, b)
    names = [a] if a == b else [a, b]
    # `aligned` always writes both, so a column against itself takes only the first.
    sources = ["a", "b"][: len(names)]
    rebased = rebase and _rebasable(data, sources)

    columns = [pl.col(source).alias(name) for source, name in zip(sources, names, strict=True)]
    if rebased:
        columns = [column / column.first() * base for column in columns]

    return _thin(data.select(PERIOD, *columns), max_points), rebased


def _rebasable(data: pl.DataFrame, sources: list[str]) -> bool:
    """Whether dividing by the first value leaves a number for every series.

    A first value of zero is not a broken frame — a cumulative P&L curve starts there
    by construction — but dividing by it turns the rest of the line into infinities,
    and Vega-Lite drops those silently. The reader picks two series, gets one, and
    nothing on the plot says where the other went.

    Answered for the pair together rather than per series. Indexing one to 100 while
    the other kept its own units would put two unrelated scales on one axis, which is
    the relationship this module exists in order not to invent.

    A pair with no overlap has no first value to divide by, so there is nothing to
    check and nothing to break: an empty frame comes out empty either way.
    """
    firsts = [value for row in data.head(1).select(sources).rows() for value in row]
    return all(value != 0.0 and math.isfinite(value) for value in firsts)


def _hover() -> alt.Parameter:
    """Which period the pointer is nearest, shared by the crosshair and the markers.

    Nearest-point rather than a hit on the mark itself: nobody can be asked to hover a
    2px line. It resolves to a period, not to a series, which is what lets one tooltip
    report every line at that x.
    """
    return alt.selection_point(
        name="hover",
        fields=[PERIOD],
        nearest=True,
        on="pointerover",
        clear="pointerout",
        empty=False,
    )


def _lines(wide: pl.DataFrame, names: list[str], x: alt.X, y_title: str) -> alt.Chart:
    """The series themselves — the layer everything else is chrome around.

    Drawn from the long form, because one line per ``series`` value is what lets a
    single colour encoding paint both.
    """
    long = wide.unpivot(index=PERIOD, variable_name="series", value_name="value")
    colour = alt.Color(
        "series",
        type="nominal",
        title=None,
        # Bound to the names, so picking a different pair never repaints a series that
        # stayed on screen.
        scale=alt.Scale(domain=names, range=list(SERIES[: len(names)])),
        legend=alt.Legend(orient="top", offset=4, symbolType="stroke", symbolStrokeWidth=2),
    )
    # The `ty: ignore` here and in the layers below is altair's `mark_*` returning an
    # unresolved TypeVar rather than a chart, so the checker cannot see `.encode` on it.
    # It is a limitation of the stubs, not of the call — the same chain is what altair's
    # own documentation shows.
    return (
        alt.Chart(long)  # ty: ignore[unresolved-attribute]
        .mark_line(strokeWidth=2, clip=True)
        .encode(
            x,
            # The levels frame the data; a zero baseline on a NAV is wasted panel.
            alt.Y("value", type="quantitative", title=y_title, scale=alt.Scale(zero=False)),
            colour,
        )
    )


def _crosshair(
    wide: pl.DataFrame,
    names: list[str],
    x: alt.X,
    x_type: XType,
    x_title: str,
    hover: alt.Parameter,
) -> alt.Chart:
    """The vertical rule under the pointer, carrying the tooltip for every series.

    Drawn from the wide form: the tooltip reads all the series at the hovered period
    out of a single row, which is the whole reason :func:`line_frame` is wide.
    """
    return (
        alt.Chart(wide)  # ty: ignore[unresolved-attribute]
        .mark_rule(color=CONTEXT, strokeWidth=1)
        .encode(
            x,
            opacity=alt.condition(hover, alt.value(0.6), alt.value(0.0)),
            tooltip=[
                alt.Tooltip(PERIOD, type=x_type, title=x_title),
                *(alt.Tooltip(name, type="quantitative", format=",.2f") for name in names),
            ],
        )
        .add_params(hover)
    )


def _markers(lines: alt.Chart, hover: alt.Parameter) -> alt.Chart:
    """A dot on each line at the hovered period — the lines' own marks, made visible.

    Built off ``lines`` rather than from scratch so the points inherit its data and
    colour encoding, and cannot drift from the curve they sit on.
    """
    return lines.mark_point(size=64, filled=True).encode(  # ty: ignore[unresolved-attribute]
        opacity=alt.condition(hover, alt.value(1.0), alt.value(0.0))
    )


def _autosize(width: int | str, height: int | str) -> alt.AutoSizeParams:
    """Fit whichever axes were asked to follow their container, and leave the rest.

    A figure given two numbers keeps Vega-Lite's own ``pad``: it was asked for a
    drawing of exactly that size, and fitting would quietly shrink it.
    """
    follows = ((width == "container", "x"), (height == "container", "y"))
    axes = "".join(axis for container, axis in follows if container)
    # Built from the axes rather than spelled out, so the cast is what tells the type
    # checker that the four strings this can produce are exactly Vega-Lite's four.
    kind = cast(
        "Literal['pad', 'fit', 'fit-x', 'fit-y']",
        {"": "pad", "xy": "fit"}.get(axes, f"fit-{axes}"),
    )
    return alt.AutoSizeParams(type=kind, contains="padding")


def _end_labels(wide: pl.DataFrame, names: list[str], x: alt.X) -> alt.LayerChart:
    """The series name at the end of its own line, so identity is never colour alone.

    The labels wear chrome ink rather than the series colour — the line they sit on
    carries the identity — and the upper one is nudged up, the lower one down, so a
    pair that ends at the same level does not print on top of itself.
    """
    last = wide.tail(1)
    order = sorted(names, key=lambda name: -float(last[name][0]))
    dodge = dict(zip(order, (-8, 8), strict=False)) if len(order) > 1 else {order[0]: 0}

    # alt.layer widens to LayerChart | FacetChart for the general case; none of these
    # labels is faceted, so the layer it returns is always the former.
    return cast(
        "alt.LayerChart",
        alt.layer(
            *(
                alt.Chart(last.select(PERIOD, pl.col(name).alias("value")))  # ty: ignore[unresolved-attribute]
                .mark_text(align="left", dx=8, dy=dodge[name], fontSize=11, fontWeight=600, color=CONTEXT)
                .encode(x, alt.Y("value", type="quantitative"), text=alt.value(name))
                for name in names
            )
        ),
    )


def _thin(frame: pl.DataFrame, max_points: int) -> pl.DataFrame:
    """Every k-th row of an over-long curve, with the last one kept.

    A line is a shape, not a scatter: dropping intermediate points leaves the shape
    intact, and it is the browser rather than the reader that notices the difference.
    """
    stride = _stride(frame.height, max_points)
    if stride == 1:
        return frame

    index = pl.int_range(pl.len())
    return frame.filter((index % stride == 0) | (index == frame.height - 1))


def _stride(height: int, max_points: int) -> int:
    """Take every k-th row of ``height`` to fit inside ``max_points``. 1 draws them all.

    Counting gaps rather than rows, and rounding up: keeping the last point costs one of
    the budget, and rounding down would spend one more than there is.
    """
    if height <= max_points or max_points < 2:
        return 1
    return -(-(height - 1) // (max_points - 1))


def drawn_points(height: int, max_points: int = MAX_POINTS) -> int:
    """How many points a curve of ``height`` rows is actually drawn with.

    The caption beside the chart needs this and the chart itself does not, which is why
    it is a function of the row count rather than of a frame: the answer is arithmetic on
    a height, and asking it should not cost a second pass over the data.

    Short of the cap every row is drawn:

    >>> drawn_points(1_500)
    1500

    Past it the curve is thinned, and the two numbers stop agreeing — which is the whole
    reason to be able to ask:

    >>> drawn_points(20_000)
    3335

    That is fewer than the 4,000 allowed, and it is the rounding rather than a defect. A
    uniform stride can only divide 19,999 gaps into 6s or 5s; 5s would draw 4,001 points
    and break the cap the browser is being protected by. Spacing them unevenly would hit
    the budget exactly, at the price of a line whose gaps are not equal — the shape it
    exists to preserve is worth more than the 665 points.
    """
    stride = _stride(height, max_points)
    if stride == 1:
        return height

    last = height - 1
    # The strided rows, plus the last one where the stride does not already land on it.
    return last // stride + 1 + (last % stride != 0)
