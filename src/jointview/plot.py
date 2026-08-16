"""Two price or NAV series drawn as two lines on one pair of axes.

The two columns are put on a shared y-axis rather than one axis each: two scales on
one plot invent a relationship that is not in the data. Where the levels are far
apart, ``rebase`` indexes both to the same starting value instead, which is the
honest way to compare a series priced at 12 with one priced at 4,000.
"""

from __future__ import annotations

from typing import Literal, cast

import altair as alt
import polars as pl

# Categorical slots 1 and 2 (blue, orange). The pair clears the contrast, chroma and
# colour-vision separation floors against both the light (#fcfcfb) and the dark
# (#1a1a19) chart surface, so it survives marimo's theme switch without being
# redefined. CONTEXT is chrome — the crosshair — not a series.
SERIES = ("#2a78d6", "#d95926")
CONTEXT = "#8a8a84"

BASE = 100.0
MAX_POINTS = 4_000
PERIOD = "period"


def series_columns(frame: pl.DataFrame) -> list[str]:
    """The columns that can be drawn: every numeric one.

    >>> import datetime as dt, polars as pl
    >>> frame = pl.DataFrame({"date": [dt.date(2024, 1, 1)], "nav": [1.0], "label": ["a"]})
    >>> series_columns(frame)
    ['nav']
    """
    return [name for name, dtype in frame.schema.items() if dtype.is_numeric()]


def date_column(frame: pl.DataFrame) -> str | None:
    """The first temporal column, which becomes the x-axis. None means row number.

    >>> import datetime as dt, polars as pl
    >>> date_column(pl.DataFrame({"when": [dt.date(2024, 1, 1)], "nav": [1.0]}))
    'when'
    >>> date_column(pl.DataFrame({"nav": [1.0]})) is None
    True
    """
    return next((name for name, dtype in frame.schema.items() if dtype.is_temporal()), None)


def default_pair(frame: pl.DataFrame) -> tuple[int, int]:
    """Indices into :func:`series_columns` to open on — the first two series.

    A frame with a single series opens on it twice, rather than refusing to draw.

    >>> import polars as pl
    >>> default_pair(pl.DataFrame({"a": [1.0], "b": [2.0]}))
    (0, 1)
    >>> default_pair(pl.DataFrame({"only": [1.0]}))
    (0, 0)
    """
    names = series_columns(frame)
    if not names:
        raise ValueError("frame has no numeric columns to plot")  # noqa: TRY003
    return 0, 1 if len(names) > 1 else 0


def aligned(frame: pl.DataFrame, a: str, b: str) -> pl.DataFrame:
    """The two series on their common sample: ``period``, ``a``, ``b``, in order.

    Both the picture and the summary tables are built from this, so the numbers
    beside the chart always describe the lines in it. Renaming also sidesteps
    Vega-Lite's field-shorthand escaping and lets ``a`` and ``b`` be the same column.
    """
    for column in (a, b):
        if column not in frame.columns:
            raise KeyError(f"no column {column!r} in frame")  # noqa: TRY003
        if not frame.schema[column].is_numeric():
            raise TypeError(f"column {column!r} is {frame.schema[column]}, which cannot be drawn")  # noqa: TRY003

    date = date_column(frame)
    period = pl.col(date).alias(PERIOD) if date else pl.int_range(pl.len()).alias(PERIOD)
    data = frame.select(period, pl.col(a).alias("a"), pl.col(b).alias("b"))
    return data.drop_nulls().sort(PERIOD)


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
    x_type = "temporal" if date else "quantitative"
    x_title = date or "row"
    y_title = f"indexed to {base:g}" if rebase else "level"

    long = wide.unpivot(index=PERIOD, variable_name="series", value_name="value")
    x = alt.X(PERIOD, type=x_type, title=x_title)

    colour = alt.Color(
        "series",
        type="nominal",
        title=None,
        # Bound to the names, so picking a different pair never repaints a series that
        # stayed on screen.
        scale=alt.Scale(domain=names, range=list(SERIES[: len(names)])),
        legend=alt.Legend(orient="top", offset=4, symbolType="stroke", symbolStrokeWidth=2),
    )

    # The `ty: ignore` here and below is altair's `mark_*` returning an unresolved
    # TypeVar rather than a chart, so the checker cannot see `.encode` on it. It is a
    # limitation of the stubs, not of the call — the same chain is what altair's own
    # documentation shows.
    lines = (
        alt.Chart(long)  # ty: ignore[unresolved-attribute]
        .mark_line(strokeWidth=2, clip=True)
        .encode(
            x,
            # The levels frame the data; a zero baseline on a NAV is wasted panel.
            alt.Y("value", type="quantitative", title=y_title, scale=alt.Scale(zero=False)),
            colour,
        )
    )

    # The crosshair finds the period; the tooltip then reads every series at it. Nobody
    # can be asked to hover a 2px line.
    hover = alt.selection_point(
        name="hover",
        fields=[PERIOD],
        nearest=True,
        on="pointerover",
        clear="pointerout",
        empty=False,
    )
    rule = (
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
    markers = lines.mark_point(size=64, filled=True).encode(
        opacity=alt.condition(hover, alt.value(1.0), alt.value(0.0))
    )

    return (
        alt.layer(rule, lines, markers, _end_labels(wide, names, x))
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
