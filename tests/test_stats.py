import math

import polars as pl
import pytest

from jointview.stats import MISSING, drawdown, metrics, returns, summary, summary_markdown


@pytest.fixture
def steady():
    """Ten percent up, twice — no volatility, so the ratios have to give up."""
    return pl.Series("fund", [100.0, 110.0, 121.0])


@pytest.fixture
def bumpy():
    return pl.Series("fund", [100.0, 120.0, 90.0, 108.0])


def test_returns_are_period_over_period(steady):
    assert returns(steady).to_list() == pytest.approx([0.1, 0.1])


def test_returns_ignore_gaps():
    assert returns(pl.Series([100.0, None, 110.0])).to_list() == pytest.approx([0.1])


def test_drawdown_is_zero_on_the_way_up(steady):
    assert drawdown(steady).to_list() == pytest.approx([0.0, 0.0, 0.0])


def test_drawdown_measures_from_the_running_peak(bumpy):
    assert drawdown(bumpy).min() == pytest.approx(-0.25)


def test_metrics_report_the_ends_and_the_total(steady):
    numbers = metrics(steady)
    assert numbers["Observations"] == 3
    assert numbers["Start"] == 100.0
    assert numbers["End"] == 121.0
    assert numbers["Total return"] == pytest.approx(0.21)


def test_metrics_annualise_with_the_given_period_count(steady):
    # Two steps of a four-period year: 1.21 compounded twice.
    assert metrics(steady, periods_per_year=4)["Annual return"] == pytest.approx(0.4641)


def test_metrics_describe_the_distribution(bumpy):
    numbers = metrics(bumpy)
    assert numbers["Best period"] == pytest.approx(0.2)
    assert numbers["Worst period"] == pytest.approx(-0.25)
    assert numbers["Hit rate"] == pytest.approx(2 / 3)
    assert numbers["Max drawdown"] == pytest.approx(-0.25)


def test_metrics_give_up_on_a_sharpe_ratio_without_volatility(steady):
    assert math.isnan(metrics(steady)["Sharpe ratio"])
    assert metrics(steady)["Annual volatility"] == 0.0


def test_metrics_give_up_on_a_growth_rate_from_a_worthless_start():
    assert math.isnan(metrics(pl.Series([0.0, 1.0, 2.0]))["Annual return"])


def test_metrics_need_two_observations():
    with pytest.raises(ValueError, match="two observations"):
        metrics(pl.Series([100.0]))


def test_summary_formats_every_metric(steady):
    table = summary(steady)
    values = dict(table.iter_rows())
    assert table.columns == ["metric", "value"]
    assert values["Observations"] == "3"
    assert values["Total return"] == "+21.00%"
    assert values["Max drawdown"] == "0.00%"
    assert values["Sharpe ratio"] == MISSING


def test_summary_markdown_is_a_table_titled_by_the_series(steady):
    lines = summary_markdown(steady, title="tech_fund").splitlines()
    assert lines[0] == "| tech_fund | |"
    assert lines[1] == "|:---|---:|"
    assert lines[2] == "| Observations | 3 |"
    assert len(lines) == len(summary(steady)) + 2


def test_summary_markdown_falls_back_to_the_series_name(steady):
    assert summary_markdown(steady).startswith("| fund |")
