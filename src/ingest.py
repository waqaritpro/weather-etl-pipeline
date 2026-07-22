"""Ingestion layer: pull weather + air quality data and persist raw JSON.

Raw payloads are written untouched to data/raw/ with a timestamped filename:
    data/raw/weather_dallas_20260722T120000Z.json
    data/raw/air_quality_dallas_20260722T120000Z.json

Keeping an immutable raw layer means transforms can be re-run or fixed
without re-hitting the API, and no source data is ever lost.

Usage:
    python -m src.ingest
"""

import json
import logging
import sys
from datetime import datetime, timezone

import requests

from src.config import (
    AIR_QUALITY_API_URL,
    AIR_QUALITY_HOURLY_VARS,
    LOCATIONS,
    PAST_DAYS,
    RAW_DATA_DIR,
    REQUEST_TIMEOUT_SECONDS,
    WEATHER_API_URL,
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


def ingest_location(location: dict, run_ts: str) -> None:
    """Pull weather and air quality data for a single location."""
    base_params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "timezone": "UTC",
        "past_days": PAST_DAYS,
    }

    weather = fetch_json(
        WEATHER_API_URL,
        {**base_params, "hourly": ",".join(WEATHER_HOURLY_VARS)},
    )
    write_raw(weather, "weather", location["name"], run_ts)

    air_quality = fetch_json(
        AIR_QUALITY_API_URL,
        {**base_params, "hourly": ",".join(AIR_QUALITY_HOURLY_VARS)},
    )
    write_raw(air_quality, "air_quality", location["name"], run_ts)


def main() -> int:
    run_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    logger.info("Starting ingestion run %s for %d locations", run_ts, len(LOCATIONS))

    failures = 0
    for location in LOCATIONS:
        try:
            ingest_location(location, run_ts)
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
