"""Transform layer: parse raw Open-Meteo JSON into tidy hourly DataFrames.

Raw files are named `{source}_{location}_{run_ts}.json` by the ingest layer
(src/ingest.py). This module reads that raw layer and produces one tidy row
per (location, observation hour) for each of the two sources, ready to be
upserted by src/load.py.

Usage:
    from src.transform import transform_directory
    weather_df, air_quality_df = transform_directory()
"""

import json
import logging
import re
from pathlib import Path

import pandas as pd

from src.config import AIR_QUALITY_HOURLY_VARS, RAW_DATA_DIR, WEATHER_HOURLY_VARS

logger = logging.getLogger(__name__)

# Matches e.g. "weather_dallas_20260722T120000Z.json" or
# "air_quality_fort_worth_20260722T120000Z.json". The source alternation is
# matched first so it can't be confused with underscores in location names.
FILENAME_RE = re.compile(
    r"^(?P<source>weather|air_quality)_(?P<location>.+)_(?P<run_ts>\d{8}T\d{6}Z)\.json$"
)

WEATHER_SOURCE = "weather"
AIR_QUALITY_SOURCE = "air_quality"


class InvalidRawFilename(ValueError):
    """Raised when a raw JSON filename doesn't match the ingest naming pattern."""


def parse_filename(path: Path) -> dict:
    """Extract source, location, and run timestamp from a raw filename."""
    match = FILENAME_RE.match(path.name)
    if not match:
        raise InvalidRawFilename(f"Unrecognized raw filename: {path.name}")
    return match.groupdict()


def _hourly_to_frame(payload: dict, variables: list) -> pd.DataFrame:
    """Turn an Open-Meteo `hourly` block into a tidy, typed DataFrame."""
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []

    data = {"observation_time": times}
    for var in variables:
        values = hourly.get(var)
        data[var] = values if values is not None else [None] * len(times)

    frame = pd.DataFrame(data)
    frame["observation_time"] = pd.to_datetime(frame["observation_time"], utc=True)
    return frame


def _transform_file(path: Path, expected_source: str, variables: list) -> pd.DataFrame:
    meta = parse_filename(path)
    if meta["source"] != expected_source:
        raise InvalidRawFilename(
            f"{path.name} is a '{meta['source']}' file, expected '{expected_source}'"
        )

    payload = json.loads(path.read_text())
    frame = _hourly_to_frame(payload, variables)
    frame.insert(0, "location_name", meta["location"])
    frame["source_file"] = path.name
    return frame


def transform_weather_file(path: Path) -> pd.DataFrame:
    """Parse a single raw weather JSON file into a tidy hourly DataFrame."""
    return _transform_file(path, WEATHER_SOURCE, WEATHER_HOURLY_VARS)


def transform_air_quality_file(path: Path) -> pd.DataFrame:
    """Parse a single raw air quality JSON file into a tidy hourly DataFrame."""
    return _transform_file(path, AIR_QUALITY_SOURCE, AIR_QUALITY_HOURLY_VARS)


def _combine(frames: list) -> pd.DataFrame:
    """Concatenate per-file frames, keeping the most recent run for each hour."""
    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    # source_file ends in the run timestamp, which sorts chronologically as a
    # string (YYYYMMDDTHHMMSSZ), so the last duplicate is always the latest run.
    combined = combined.sort_values("source_file")
    combined = combined.drop_duplicates(
        subset=["location_name", "observation_time"], keep="last"
    )
    return combined.sort_values(["location_name", "observation_time"]).reset_index(drop=True)


def transform_directory(raw_dir: Path = RAW_DATA_DIR) -> tuple:
    """Parse every raw JSON file in `raw_dir` into tidy weather/air quality DataFrames.

    Returns a (weather_df, air_quality_df) tuple. Rows are deduplicated on
    (location_name, observation_time), preferring the most recently ingested run.
    """
    weather_frames = []
    air_quality_frames = []

    for path in sorted(Path(raw_dir).glob("*.json")):
        try:
            meta = parse_filename(path)
        except InvalidRawFilename:
            logger.warning("Skipping unrecognized raw file: %s", path.name)
            continue

        if meta["source"] == WEATHER_SOURCE:
            weather_frames.append(transform_weather_file(path))
        elif meta["source"] == AIR_QUALITY_SOURCE:
            air_quality_frames.append(transform_air_quality_file(path))

    return _combine(weather_frames), _combine(air_quality_frames)
