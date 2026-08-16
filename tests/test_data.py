import polars as pl
import pytest

from jointview.data import demo_frame, load_frame


def test_demo_frame_is_deterministic():
    assert demo_frame(rows=50).equals(demo_frame(rows=50))


def test_demo_frame_covers_the_dtype_families():
    schema = demo_frame(rows=50).schema
    assert schema["date"].is_temporal()
    assert schema["sector"] == pl.String
    assert schema["returns"].is_numeric()


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
