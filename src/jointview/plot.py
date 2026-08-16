"""The joint plot: a scatter of two columns with a marginal histogram per axis.

Brushing the scatter highlights the corresponding part of both marginals, which is
the whole point of putting them on the same figure.
"""

from __future__ import annotations

import altair as alt
import polars as pl

# One series, so one hue. Both of these clear 3:1 contrast against the light
# (#fcfcfb) and the dark (#1a1a19) chart surface, so they survive marimo's theme
# switch without being redefined.
ACCENT = "#2a78d6"
CONTEXT = "#8a8a84"

MAX_BINS = 40
MAX_POINTS = 20_000
MARGINAL = 76


def encoding_type(dtype: pl.DataType) -> str:
    """Map a Polars dtype onto the Vega-Lite encoding type that fits it."""
    if dtype.is_numeric():
        return "quantitative"
    if dtype.is_temporal():
        return "temporal"
    return "nominal"


def default_pair(frame: pl.DataFrame) -> tuple[int, int]:
    """Column indices to open on — numeric first, so the app starts on a real scatter."""
    if not frame.columns:
        raise ValueError("frame has no columns")

    numeric = [i for i, dtype in enumerate(frame.dtypes) if dtype.is_numeric()]
    order = numeric + [i for i in range(frame.width) if i not in set(numeric)]
    return order[0], order[1] if len(order) > 1 else order[0]


def joint_frame(
    frame: pl.DataFrame, x: str, y: str, *, max_points: int = MAX_POINTS
) -> pl.DataFrame:
    """The two columns actually drawn: renamed, complete cases only, sampled down.

    Renaming sidesteps Vega-Lite's field-shorthand escaping (dots, brackets) and lets
    x and y point at the same source column without a duplicate-name error.
    """
    for column in (x, y):
        if column not in frame.columns:
            raise KeyError(f"no column {column!r} in frame")

    data = frame.select(pl.col(x).alias("x"), pl.col(y).alias("y")).drop_nulls()
    return data.sample(max_points, seed=0) if data.height > max_points else data


def joint_chart(
    frame: pl.DataFrame,
    x: str,
    y: str,
    *,
    width: int = 560,
    height: int = 420,
    max_bins: int = MAX_BINS,
    max_points: int = MAX_POINTS,
) -> alt.VConcatChart:
    """Build the joint plot of column ``x`` against column ``y``."""
    data = joint_frame(frame, x, y, max_points=max_points)
    x_type = encoding_type(frame.schema[x])
    y_type = encoding_type(frame.schema[y])

    brush = alt.selection_interval(name="brush", encodings=["x", "y"])
    base = alt.Chart(data)

    scatter = (
        base.mark_circle(size=54, opacity=0.45, color=ACCENT)
        .encode(
            alt.X("x", type=x_type, title=x, scale=_scale(x_type)),
            alt.Y("y", type=y_type, title=y, scale=_scale(y_type)),
            tooltip=[
                alt.Tooltip("x", type=x_type, title=x),
                alt.Tooltip("y", type=y_type, title=y),
            ],
        )
        .add_params(brush)
        .properties(width=width, height=height)
    )

    top = _marginal(base, "x", x_type, max_bins, brush, horizontal=True).properties(
        width=width, height=MARGINAL
    )
    right = _marginal(base, "y", y_type, max_bins, brush, horizontal=False).properties(
        width=MARGINAL, height=height
    )

    return (
        alt.vconcat(top, alt.hconcat(scatter, right, spacing=6), spacing=6)
        .configure_axis(grid=True, gridOpacity=0.3, domain=False, labelPadding=4)
        .configure_view(stroke=None)
        .configure_concat(spacing=6)
    )


def _scale(kind: str) -> alt.Scale | alt.UndefinedType:
    """Quantitative axes should frame the data, not be dragged down to zero."""
    return alt.Scale(zero=False) if kind == "quantitative" else alt.Undefined


def _marginal(
    base: alt.Chart,
    field: str,
    kind: str,
    max_bins: int,
    brush: alt.Parameter,
    *,
    horizontal: bool,
) -> alt.LayerChart:
    """A histogram of one field, layered as context (grey) plus selection (accent).

    ``horizontal`` means the bars grow upwards along a horizontal field axis — the
    top marginal. The right marginal is the same thing rotated.
    """
    nominal = kind == "nominal"
    binning = alt.Undefined if nominal else alt.Bin(maxbins=max_bins)

    # Bars are anchored to the count baseline, so only the far end gets rounded.
    corners = (
        {"cornerRadiusTopLeft": 3, "cornerRadiusTopRight": 3}
        if horizontal
        else {"cornerRadiusTopRight": 3, "cornerRadiusBottomRight": 3}
    )
    # A handful of categories would otherwise each get a bar the width of its band,
    # which reads as a block of colour rather than as a distribution.
    style = {"binSpacing": 2, "size": 20, **corners} if nominal else {"binSpacing": 2, **corners}
    mark = base.mark_bar(**style)

    field_channel = alt.X if horizontal else alt.Y
    count_channel = alt.Y if horizontal else alt.X

    layer = mark.encode(
        field_channel(field, type=kind, bin=binning, title=None, axis=None, scale=_scale(kind)),
        # The marginals are context for the scatter; their own axis would only add
        # ink, so the count is carried by the tooltip instead.
        count_channel("count()", title=None, axis=None, stack=None),
        tooltip=[
            alt.Tooltip(field, type=kind, bin=binning, title="bin"),
            alt.Tooltip("count()", title="rows"),
        ],
    )

    return alt.layer(
        layer.mark_bar(color=CONTEXT, **style),
        layer.mark_bar(color=ACCENT, **style).transform_filter(brush),
    )
