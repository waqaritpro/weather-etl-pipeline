import json
from pathlib import Path

import pandas as pd
import pytest

from src.transform import (
    InvalidRawFilename,
    parse_filename,
    transform_air_quality_file,
    transform_directory,
    transform_weather_file,
)

WEATHER_PAYLOAD = {
    "latitude": 32.78,
    "longitude": -96.8,
    "hourly": {
        "time": ["2026-07-22T00:00", "2026-07-22T01:00"],
        "temperature_2m": [21.3, 20.9],
        "relative_humidity_2m": [55, 58],
        "precipitation": [0.0, 0.1],
        "wind_speed_10m": [10.1, 9.8],
        "wind_gusts_10m": [15.2, 14.9],
        "surface_pressure": [1012.3, 1012.1],
    },
}

AIR_QUALITY_PAYLOAD = {
    "latitude": 32.78,
    "longitude": -96.8,
    "hourly": {
        "time": ["2026-07-22T00:00", "2026-07-22T01:00"],
        "pm10": [12.0, 13.5],
        "pm2_5": [5.0, 5.5],
        "ozone": [30.0, 31.0],
        "nitrogen_dioxide": [8.0, 8.2],
        "us_aqi": [42, 44],
    },
}


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload))
    return path


class TestParseFilename:
    def test_weather_filename(self):
        meta = parse_filename(Path("weather_dallas_20260722T120000Z.json"))
        assert meta == {
            "source": "weather",
            "location": "dallas",
            "run_ts": "20260722T120000Z",
        }

    def test_air_quality_filename_with_underscored_location(self):
        meta = parse_filename(Path("air_quality_fort_worth_20260722T120000Z.json"))
        assert meta == {
            "source": "air_quality",
            "location": "fort_worth",
            "run_ts": "20260722T120000Z",
        }

    def test_invalid_filename_raises(self):
        with pytest.raises(InvalidRawFilename):
            parse_filename(Path("not_a_raw_file.json"))


class TestTransformWeatherFile:
    def test_shape_and_columns(self, tmp_path):
        path = write_json(tmp_path / "weather_dallas_20260722T120000Z.json", WEATHER_PAYLOAD)
        df = transform_weather_file(path)

        assert len(df) == 2
        assert list(df.columns) == [
            "location_name",
            "observation_time",
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "wind_speed_10m",
            "wind_gusts_10m",
            "surface_pressure",
            "source_file",
        ]
        assert (df["location_name"] == "dallas").all()
        assert df["source_file"].iloc[0] == "weather_dallas_20260722T120000Z.json"

    def test_observation_time_is_parsed_utc_datetime(self, tmp_path):
        path = write_json(tmp_path / "weather_dallas_20260722T120000Z.json", WEATHER_PAYLOAD)
        df = transform_weather_file(path)

        assert pd.api.types.is_datetime64_any_dtype(df["observation_time"])
        assert str(df["observation_time"].dt.tz) == "UTC"
        assert df["observation_time"].iloc[0] == pd.Timestamp("2026-07-22T00:00", tz="UTC")

    def test_values_preserved(self, tmp_path):
        path = write_json(tmp_path / "weather_plano_20260722T120000Z.json", WEATHER_PAYLOAD)
        df = transform_weather_file(path)

        assert df["temperature_2m"].tolist() == [21.3, 20.9]
        assert df["surface_pressure"].tolist() == [1012.3, 1012.1]

    def test_wrong_source_raises(self, tmp_path):
        path = write_json(
            tmp_path / "air_quality_dallas_20260722T120000Z.json", WEATHER_PAYLOAD
        )
        with pytest.raises(InvalidRawFilename):
            transform_weather_file(path)

    def test_missing_variable_becomes_null_column(self, tmp_path):
        payload = json.loads(json.dumps(WEATHER_PAYLOAD))
        del payload["hourly"]["wind_gusts_10m"]
        path = write_json(tmp_path / "weather_dallas_20260722T120000Z.json", payload)

        df = transform_weather_file(path)
        assert df["wind_gusts_10m"].isna().all()


class TestTransformAirQualityFile:
    def test_shape_and_columns(self, tmp_path):
        path = write_json(
            tmp_path / "air_quality_fort_worth_20260722T120000Z.json", AIR_QUALITY_PAYLOAD
        )
        df = transform_air_quality_file(path)

        assert len(df) == 2
        assert list(df.columns) == [
            "location_name",
            "observation_time",
            "pm10",
            "pm2_5",
            "ozone",
            "nitrogen_dioxide",
            "us_aqi",
            "source_file",
        ]
        assert (df["location_name"] == "fort_worth").all()

    def test_wrong_source_raises(self, tmp_path):
        path = write_json(
            tmp_path / "weather_dallas_20260722T120000Z.json", AIR_QUALITY_PAYLOAD
        )
        with pytest.raises(InvalidRawFilename):
            transform_air_quality_file(path)


class TestTransformDirectory:
    def test_combines_multiple_locations(self, tmp_path):
        write_json(tmp_path / "weather_dallas_20260722T120000Z.json", WEATHER_PAYLOAD)
        write_json(tmp_path / "weather_plano_20260722T120000Z.json", WEATHER_PAYLOAD)
        write_json(
            tmp_path / "air_quality_dallas_20260722T120000Z.json", AIR_QUALITY_PAYLOAD
        )

        weather_df, air_quality_df = transform_directory(tmp_path)

        assert set(weather_df["location_name"]) == {"dallas", "plano"}
        assert len(weather_df) == 4
        assert len(air_quality_df) == 2

    def test_dedups_on_location_and_hour_keeping_latest_run(self, tmp_path):
        earlier = json.loads(json.dumps(WEATHER_PAYLOAD))
        earlier["hourly"]["temperature_2m"] = [99.9, 99.9]
        write_json(tmp_path / "weather_dallas_20260722T060000Z.json", earlier)

        later = json.loads(json.dumps(WEATHER_PAYLOAD))
        later["hourly"]["temperature_2m"] = [21.3, 20.9]
        write_json(tmp_path / "weather_dallas_20260722T120000Z.json", later)

        weather_df, _ = transform_directory(tmp_path)

        assert len(weather_df) == 2
        assert weather_df["temperature_2m"].tolist() == [21.3, 20.9]
        assert (weather_df["source_file"] == "weather_dallas_20260722T120000Z.json").all()

    def test_skips_unrecognized_files(self, tmp_path):
        write_json(tmp_path / "weather_dallas_20260722T120000Z.json", WEATHER_PAYLOAD)
        (tmp_path / "README.txt").write_text("not json we care about")

        weather_df, air_quality_df = transform_directory(tmp_path)

        assert len(weather_df) == 2
        assert air_quality_df.empty

    def test_empty_directory_returns_empty_frames(self, tmp_path):
        weather_df, air_quality_df = transform_directory(tmp_path)

        assert weather_df.empty
        assert air_quality_df.empty
