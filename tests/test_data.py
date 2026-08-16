import polars as pl
import pytest

from jointview.data import demo_frame, load_frame


def test_demo_frame_is_deterministic():
    assert demo_frame(rows=50).equals(demo_frame(rows=50))


def test_demo_frame_is_a_date_plus_nav_series():
    frame = demo_frame(rows=50)
    date, *funds = frame.columns
    assert frame.schema[date].is_temporal()
    assert all(frame.schema[name].is_numeric() for name in funds)
    assert len(funds) > 1


def test_demo_frame_navs_stay_positive():
    frame = demo_frame(rows=200).drop("date")
    assert all(frame[name].min() > 0 for name in frame.columns)


def test_demo_frame_skips_weekends():
    dates = demo_frame(rows=200)["date"]
    assert dates.dt.weekday().max() <= 5
    assert dates.is_sorted()


def test_demo_frame_series_start_where_they_were_asked_to():
    # Within one day's move of the configured level, since the first row is already
    # one step in.
    frame = demo_frame(rows=50)
    assert 0.9 < frame["world_equity"][0] / 100.0 < 1.1
    assert 0.9 < frame["balanced"][0] / 1_450.0 < 1.1


def test_load_frame_falls_back_to_the_demo():
    assert load_frame(None).columns == demo_frame().columns


def test_load_frame_round_trips_parquet(tmp_path):
    file = tmp_path / "frame.parquet"
    demo_frame(rows=20).write_parquet(file)
    assert load_frame(file).height == 20


def test_load_frame_rejects_an_unknown_suffix(tmp_path):
    file = tmp_path / "frame.xlsx"
    file.touch()
    with pytest.raises(ValueError, match="supported"):
        load_frame(file)


def test_load_frame_reports_a_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_frame(tmp_path / "absent.parquet")


def test_load_frame_reads_a_csv_of_navs(tmp_path):
    file = tmp_path / "navs.csv"
    pl.DataFrame({"date": ["2024-01-01"], "fund": [100.0]}).write_csv(file)
    assert load_frame(file)["fund"][0] == 100.0
