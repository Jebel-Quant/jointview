"""Summary statistics for a single price or NAV series.

Everything here takes a column of *levels* — a net asset value, an index, a price —
and derives the returns itself, so the app never has to keep two representations of
the same series around.
"""

from __future__ import annotations

import math

import polars as pl

# Trading days. A series sampled monthly or weekly wants its own figure; it is a
# keyword everywhere rather than a constant baked into the maths.
PERIODS_PER_YEAR = 252

MISSING = "—"


def returns(levels: pl.Series) -> pl.Series:
    """Simple period-over-period returns of a level series."""
    values = _clean(levels)
    return (values / values.shift(1) - 1.0).drop_nulls()


def drawdown(levels: pl.Series) -> pl.Series:
    """Distance below the running maximum, as a fraction — zero or negative."""
    values = _clean(levels)
    return values / values.cum_max() - 1.0


def metrics(levels: pl.Series, *, periods_per_year: int = PERIODS_PER_YEAR) -> dict[str, float]:
    """The raw numbers behind the summary table, in natural units (0.07 is 7%).

    A figure that cannot be formed — a Sharpe ratio for a flat series, a growth rate
    for a series that touches zero — comes back as NaN rather than raising, so one
    odd column never blanks the whole table.
    """
    values = _clean(levels)
    if values.len() < 2:
        raise ValueError("need at least two observations to summarise a series")

    first, last = float(values[0]), float(values[-1])
    steps = values.len() - 1
    period = returns(values)
    volatility = float(period.std(ddof=1) or 0.0) * math.sqrt(periods_per_year)

    growth = last / first if first > 0 else math.nan
    years = steps / periods_per_year

    return {
        "Observations": float(values.len()),
        "Start": first,
        "End": last,
        "Total return": growth - 1.0,
        "Annual return": growth ** (1.0 / years) - 1.0 if growth > 0 else math.nan,
        "Annual volatility": volatility,
        "Sharpe ratio": float(period.mean()) * periods_per_year / volatility if volatility else math.nan,
        "Max drawdown": float(drawdown(values).min()),
        "Hit rate": float((period > 0).mean()),
        "Best period": float(period.max()),
        "Worst period": float(period.min()),
    }


# Levels keep their own units, rates get a sign, and volatility — which has no
# direction — does not.
FORMATS: dict[str, str] = {
    "Observations": "{:,.0f}",
    "Start": "{:,.2f}",
    "End": "{:,.2f}",
    "Total return": "{:+.2%}",
    "Annual return": "{:+.2%}",
    "Annual volatility": "{:.2%}",
    "Sharpe ratio": "{:.2f}",
    "Max drawdown": "{:.2%}",
    "Hit rate": "{:.1%}",
    "Best period": "{:+.2%}",
    "Worst period": "{:+.2%}",
}


def summary(levels: pl.Series, *, periods_per_year: int = PERIODS_PER_YEAR) -> pl.DataFrame:
    """The same numbers as :func:`metrics`, formatted for display."""
    numbers = metrics(levels, periods_per_year=periods_per_year)
    return pl.DataFrame(
        {
            "metric": list(numbers),
            "value": [_format(name, value) for name, value in numbers.items()],
        }
    )


def summary_markdown(levels: pl.Series, *, title: str | None = None, periods_per_year: int = PERIODS_PER_YEAR) -> str:
    """A two-column markdown table, ready for ``mo.md``."""
    table = summary(levels, periods_per_year=periods_per_year)
    header = f"| {title or levels.name} | |", "|:---|---:|"
    body = (f"| {row['metric']} | {row['value']} |" for row in table.iter_rows(named=True))
    return "\n".join((*header, *body))


def _format(name: str, value: float) -> str:
    """Render one metric, falling back to ``MISSING`` for anything not finite.

    A NaN here is a figure that could not be formed rather than a bug — a Sharpe
    ratio without volatility, a growth rate from a start of zero — so it shows as
    a dash instead of blanking the row.
    """
    if not math.isfinite(value):
        return MISSING
    return FORMATS.get(name, "{:,.4g}").format(value)


def _clean(levels: pl.Series) -> pl.Series:
    """Drop the gaps and settle on one dtype, so the arithmetic below has neither to think about."""
    return levels.drop_nulls().cast(pl.Float64)
