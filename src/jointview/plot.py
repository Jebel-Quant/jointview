"""Two price or NAV series drawn as two lines on one pair of axes.

The two columns are put on a shared y-axis rather than one axis each: two scales on
one plot invent a relationship that is not in the data. Where the levels are far
apart, ``rebase`` indexes both to the same starting value instead, which is the
honest way to compare a series priced at 12 with one priced at 4,000.

Choosing the columns and cutting them to their common sample happens before any of
this, in :mod:`jointview.columns`.
"""

from __future__ import annotations

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
    """
    data = aligned(frame, a, b)
    names = [a] if a == b else [a, b]
    columns = [pl.col(source).alias(name) for source, name in zip("ab", names, strict=False)]
    if rebase:
        columns = [column / column.first() * base for column in columns]

    return _thin(data.select(PERIOD, *columns), max_points)


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

    Width defaults to ``"container"``: the plot takes whatever the column around it
    gives it, which is the point of a full-width app. Height stays a number, because
    nothing in the page has a height for a chart to follow — 700 fills a laptop window
    once the notebook margins are out of the way, without spilling off a short one.
    """
    wide = line_frame(frame, a, b, rebase=rebase, base=base, max_points=max_points)
    names = [name for name in wide.columns if name != PERIOD]

    date = date_column(frame)
    x_type: XType = "temporal" if date else "quantitative"
    x_title = date or "row"
    y_title = f"indexed to {base:g}" if rebase else "level"
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
    if frame.height <= max_points or max_points < 2:
        return frame

    # Counting gaps rather than rows: keeping the last point costs one of the budget.
    stride = -(-(frame.height - 1) // (max_points - 1))
    index = pl.int_range(pl.len())
    return frame.filter((index % stride == 0) | (index == frame.height - 1))
