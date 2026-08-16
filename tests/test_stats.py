"""The summary tables: the raw metrics, their formatting, and the markdown around them.

Three fixtures carry most of the cases — one series that only goes up, so the ratios
have to give up; one that falls, so drawdown and the distribution have something to
describe; and one that never moves at all, which is the case that used to raise.

Every function here takes the frame rather than the column, because jQuantStats reads
the annualisation factor off the spacing of the period column.
"""

import datetime as dt
import math

import polars as pl
import pytest

import jointview.columns
import jointview.stats
from jointview.stats import MISSING, drawdown, metrics, returns, summary, summary_markdown


def framed(values, periods=None):
    """A one-series frame shaped the way :func:`jointview.columns.aligned` returns them."""
    return pl.DataFrame(
        {
            "period": periods if periods is not None else list(range(len(values))),
            "fund": [float(value) for value in values],
        }
    )


@pytest.fixture
def steady():
    """Ten percent up, twice — no volatility, so the ratios have to give up."""
    return framed([100.0, 110.0, 121.0])


@pytest.fixture
def bumpy():
    """Up a fifth, down a quarter, up a fifth — enough of a fall to measure from."""
    return framed([100.0, 120.0, 90.0, 108.0])


@pytest.fixture
def flat():
    """A series that never moves — a cash line, and the one that divides by zero."""
    return framed([100.0] * 4)


def test_the_summary_reads_the_column_aligned_writes():
    """The default `date_col` is the column `aligned` produces, not a second literal.

    Both halves of the package take the name from `columns`, which owns the contract,
    so they agree by construction. The assertion is what fails if someone reintroduces
    a local copy: a `KeyError` deep in the app is the alternative way to find out.
    """
    frame = pl.DataFrame({"date": [dt.date(2024, 1, 1), dt.date(2024, 1, 2)], "x": [1.0, 2.0]})
    assert jointview.columns.PERIOD in jointview.columns.aligned(frame, "x", "x").columns
    assert jointview.stats.PERIOD is jointview.columns.PERIOD


def test_returns_are_period_over_period(steady):
    """Returns come off the levels, so nothing has to carry both representations."""
    assert returns(steady, "fund").to_list() == pytest.approx([0.1, 0.1])


def test_returns_ignore_gaps():
    """A missing observation is dropped rather than counted as a flat period."""
    frame = pl.DataFrame({"period": [0, 1, 2, 3], "fund": [100.0, None, 110.0, 121.0]})
    assert returns(frame, "fund").to_list() == pytest.approx([0.1, 0.1])


def test_drawdown_is_zero_on_the_way_up(steady):
    """At a new high the distance below the peak is nothing, not a small negative."""
    assert drawdown(steady, "fund").to_list() == pytest.approx([0.0, 0.0])


def test_drawdown_is_negative_not_a_depth(bumpy):
    """120 down to 90 is a quarter *down* — jQuantStats' positive depth is flipped."""
    assert drawdown(bumpy, "fund").min() == pytest.approx(-0.25)
    assert drawdown(bumpy, "fund").max() <= 0.0


def test_metrics_report_the_ends_and_the_total(steady):
    """The plain facts of the series, before anything is annualised."""
    numbers = metrics(steady, "fund")
    assert numbers["Observations"] == 3
    assert numbers["Start"] == 100.0
    assert numbers["End"] == 121.0
    assert numbers["Total return"] == pytest.approx(0.21)


def test_metrics_annualise_from_the_spacing_of_the_periods():
    """A weekly series is annualised as weekly — the factor is read, not assumed.

    The same three levels dated a week apart rather than a day apart must not produce
    the same annual return; that they do not is the whole reason the period column is
    threaded through.
    """
    levels = [100.0, 110.0, 121.0]
    daily = framed(levels, [dt.date(2024, 1, 1), dt.date(2024, 1, 2), dt.date(2024, 1, 3)])
    weekly = framed(levels, [dt.date(2024, 1, 1), dt.date(2024, 1, 8), dt.date(2024, 1, 15)])
    assert metrics(daily, "fund")["Annual return"] > metrics(weekly, "fund")["Annual return"]


def test_metrics_without_dates_assume_daily(steady):
    """A frame numbered by row still annualises, on the 252-day convention."""
    assert math.isfinite(metrics(steady, "fund")["Annual return"])


def test_metrics_describe_the_distribution(bumpy):
    """The shape of the period returns, not just where the series ended up."""
    numbers = metrics(bumpy, "fund")
    assert numbers["Best period"] == pytest.approx(0.2)
    assert numbers["Worst period"] == pytest.approx(-0.25)
    assert numbers["Hit rate"] == pytest.approx(2 / 3)
    assert numbers["Max drawdown"] == pytest.approx(-0.25)


def test_metrics_carry_the_ratios_jquantstats_adds(bumpy):
    """Sortino, Calmar and the rest come from the library rather than being reimplemented."""
    numbers = metrics(bumpy, "fund")
    for name in ("Sortino ratio", "Calmar ratio", "Ulcer index", "Value at risk", "Skew"):
        assert name in numbers


def test_metrics_give_up_on_a_sharpe_ratio_without_volatility(steady):
    """A ratio over zero volatility is NaN — the one honest answer, and not a raise."""
    assert math.isnan(metrics(steady, "fund")["Sharpe ratio"])
    assert metrics(steady, "fund")["Annual volatility"] == 0.0


def test_a_series_that_never_moves_is_summarised_not_an_error(flat):
    """A flat column has no winning periods; a hit rate over no periods is NaN, not a crash.

    jQuantStats divides by the count of non-zero returns to get a win rate, so a cash
    line raises ZeroDivisionError inside the library. It is an ordinary column, and the
    table has to render it.
    """
    numbers = metrics(flat, "fund")
    assert math.isnan(numbers["Hit rate"])
    assert numbers["Total return"] == pytest.approx(0.0)
    assert dict(summary(flat, "fund").iter_rows())["Hit rate"] == MISSING


def test_metrics_need_more_than_a_point():
    """Too short to have an index is the one case that raises rather than NaNs."""
    with pytest.raises(ValueError, match="at least two"):
        metrics(framed([100.0]), "fund")


def test_metrics_reject_a_column_that_is_not_there(steady):
    """A typo names a column, and says so, rather than failing somewhere in the library."""
    with pytest.raises(KeyError, match="nope"):
        metrics(steady, "nope")


def test_summary_formats_every_metric(steady):
    """Each metric carries its own units, and a NaN becomes a dash."""
    table = summary(steady, "fund")
    values = dict(table.iter_rows())
    assert table.columns == ["metric", "value"]
    assert values["Observations"] == "3"
    assert values["Total return"] == "+21.00%"
    assert values["Max drawdown"] == "0.00%"
    assert values["Sharpe ratio"] == MISSING


def test_summary_markdown_is_a_table_titled_by_the_series(steady):
    """The header row is the column name, so the panel says which series it describes."""
    lines = summary_markdown(steady, "fund", title="tech_fund").splitlines()
    assert lines[0] == "| tech_fund | |"
    assert lines[1] == "|:---|---:|"
    assert lines[2] == "| Observations | 3 |"
    assert len(lines) == len(summary(steady, "fund")) + 2


def test_summary_markdown_falls_back_to_the_column_name(steady):
    """Without a title the column names itself."""
    assert summary_markdown(steady, "fund").startswith("| fund |")
