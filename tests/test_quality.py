import pandas as pd
import pytest

from src.quality import check_frame


def make_weather_df(rows=24, location="dallas", day="2026-07-22"):
    """Build a clean, complete weather frame: `rows` consecutive hours."""
    times = pd.date_range(f"{day}T00:00", periods=rows, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "location_name": location,
            "observation_time": times,
            "temperature_2m": [21.0] * rows,
            "relative_humidity_2m": [55.0] * rows,
            "precipitation": [0.0] * rows,
            "wind_speed_10m": [10.0] * rows,
            "wind_gusts_10m": [15.0] * rows,
            "surface_pressure": [1012.0] * rows,
            "source_file": f"weather_{location}_20260722T120000Z.json",
        }
    )


class TestCleanFrame:
    def test_full_day_passes(self):
        report = check_frame(make_weather_df(), "hourly_weather")
        assert report.ok
        assert report.errors == []
        assert report.warnings == []
        assert report.row_count == 24

    def test_empty_frame_passes(self):
        report = check_frame(pd.DataFrame(), "hourly_weather")
        assert report.ok
        assert report.row_count == 0


class TestDuplicateKeys:
    def test_duplicate_key_is_error(self):
        df = pd.concat([make_weather_df(rows=2), make_weather_df(rows=2)], ignore_index=True)
        report = check_frame(df, "hourly_weather")
        assert not report.ok
        assert any("duplicate" in e for e in report.errors)


class TestNullFraction:
    def test_column_over_null_threshold_fails(self):
        df = make_weather_df(rows=10)
        # 5/10 = 50% null, above the 20% default threshold.
        df.loc[:4, "temperature_2m"] = None
        report = check_frame(df, "hourly_weather")
        assert not report.ok
        assert any("temperature_2m" in e and "null" in e for e in report.errors)

    def test_null_below_threshold_passes(self):
        df = make_weather_df(rows=24)
        # 1/24 ~ 4% null, under the threshold.
        df.loc[0, "temperature_2m"] = None
        report = check_frame(df, "hourly_weather")
        assert report.ok


class TestValueRanges:
    def test_humidity_above_100_fails(self):
        df = make_weather_df(rows=24)
        df.loc[0, "relative_humidity_2m"] = 150.0
        report = check_frame(df, "hourly_weather")
        assert not report.ok
        assert any("relative_humidity_2m" in e and "above" in e for e in report.errors)

    def test_negative_precipitation_fails(self):
        df = make_weather_df(rows=24)
        df.loc[0, "precipitation"] = -1.0
        report = check_frame(df, "hourly_weather")
        assert not report.ok
        assert any("precipitation" in e and "below" in e for e in report.errors)


class TestCompleteness:
    def test_partial_day_warns_but_passes(self):
        report = check_frame(make_weather_df(rows=10), "hourly_weather")
        assert report.ok  # warning only, not a hard failure
        assert any("10/24" in w for w in report.warnings)
