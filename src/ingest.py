"""Ingestion layer: pull weather + air quality data and persist raw JSON.

Raw payloads are written untouched to data/raw/ with a timestamped filename:
    data/raw/weather_dallas_20260722T120000Z.json
    data/raw/air_quality_dallas_20260722T120000Z.json

Keeping an immutable raw layer means transforms can be re-run or fixed
without re-hitting the API, and no source data is ever lost.

Two modes:
    python -m src.ingest                         # daily: last PAST_DAYS days
    python -m src.ingest --start 2026-01-01 \\
                         --end   2026-01-31       # backfill a date range

Backfills pull weather from the ERA5 archive endpoint (the forecast endpoint
only reaches ~92 days back) and air quality from its own history endpoint.
Raw filenames are identical across both modes, so transform/load are unaware
of how the data arrived.
"""

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone

import requests

from src.config import (
    AIR_QUALITY_API_URL,
    AIR_QUALITY_HOURLY_VARS,
    LOCATIONS,
    PAST_DAYS,
    RAW_DATA_DIR,
    REQUEST_TIMEOUT_SECONDS,
    WEATHER_API_URL,
    WEATHER_ARCHIVE_API_URL,
    WEATHER_HOURLY_VARS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_json(url: str, params: dict) -> dict:
    """GET a URL and return the parsed JSON payload, raising on HTTP errors."""
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def write_raw(payload: dict, source: str, location_name: str, run_ts: str) -> None:
    """Persist an untouched API payload to the raw layer."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DATA_DIR / f"{source}_{location_name}_{run_ts}.json"
    path.write_text(json.dumps(payload, indent=2))
    logger.info("Wrote %s", path.relative_to(RAW_DATA_DIR.parents[1]))


def ingest_location(
    location: dict, run_ts: str, start: str = None, end: str = None
) -> None:
    """Pull weather and air quality data for a single location.

    Daily mode (start/end omitted) pulls the last PAST_DAYS days from the live
    endpoints. Backfill mode (start and end given, as YYYY-MM-DD) pulls that
    inclusive date range from the archive/history endpoints instead.
    """
    base_params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "timezone": "UTC",
    }

    backfill = start is not None and end is not None
    if backfill:
        base_params["start_date"] = start
        base_params["end_date"] = end
        weather_url = WEATHER_ARCHIVE_API_URL
    else:
        base_params["past_days"] = PAST_DAYS
        weather_url = WEATHER_API_URL

    weather = fetch_json(
        weather_url,
        {**base_params, "hourly": ",".join(WEATHER_HOURLY_VARS)},
    )
    write_raw(weather, "weather", location["name"], run_ts)

    # Air quality serves its own history from the same endpoint via
    # start_date/end_date, so the URL is unchanged in both modes.
    air_quality = fetch_json(
        AIR_QUALITY_API_URL,
        {**base_params, "hourly": ",".join(AIR_QUALITY_HOURLY_VARS)},
    )
    write_raw(air_quality, "air_quality", location["name"], run_ts)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Open-Meteo weather + air quality data.")
    parser.add_argument(
        "--start",
        type=_valid_date,
        help="Backfill start date, YYYY-MM-DD (requires --end).",
    )
    parser.add_argument(
        "--end",
        type=_valid_date,
        help="Backfill end date, YYYY-MM-DD, inclusive (requires --start).",
    )
    args = parser.parse_args(argv)

    if bool(args.start) != bool(args.end):
        parser.error("--start and --end must be given together.")
    if args.start and args.start > args.end:
        parser.error("--start must not be after --end.")
    return args


def _valid_date(value: str) -> str:
    """Validate a YYYY-MM-DD string, returning it unchanged for the API call."""
    try:
        date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Not a valid YYYY-MM-DD date: {value!r}")
    return value


def main(argv=None) -> int:
    args = parse_args(argv)

    run_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.start:
        logger.info(
            "Starting backfill run %s (%s to %s) for %d locations",
            run_ts, args.start, args.end, len(LOCATIONS),
        )
    else:
        logger.info("Starting daily run %s for %d locations", run_ts, len(LOCATIONS))

    failures = 0
    for location in LOCATIONS:
        try:
            ingest_location(location, run_ts, args.start, args.end)
        except requests.RequestException:
            failures += 1
            logger.exception("Ingestion failed for %s", location["name"])

    if failures:
        logger.error("Run finished with %d/%d locations failed", failures, len(LOCATIONS))
        return 1

    logger.info("Run %s completed successfully", run_ts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
