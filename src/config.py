"""Central configuration for the weather ETL pipeline."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths -----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

# --- Locations to ingest ---------------------------------------------------
# Add more dicts here to expand coverage — everything downstream is driven
# by this list.
LOCATIONS = [
    {"name": "dallas", "latitude": 32.7767, "longitude": -96.7970},
    {"name": "fort_worth", "latitude": 32.7555, "longitude": -97.3308},
    {"name": "plano", "latitude": 33.0198, "longitude": -96.6989},
]

# --- Open-Meteo endpoints --------------------------------------------------
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Historical backfill. The forecast endpoint only reaches ~92 days back, so
# weather backfills use the ERA5 archive host. The air quality endpoint serves
# its own history via start_date/end_date, so it needs no separate archive URL.
WEATHER_ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"

WEATHER_HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_gusts_10m",
    "surface_pressure",
]

AIR_QUALITY_HOURLY_VARS = [
    "pm10",
    "pm2_5",
    "ozone",
    "nitrogen_dioxide",
    "us_aqi",
]

# --- Request settings ------------------------------------------------------
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
PAST_DAYS = int(os.getenv("PAST_DAYS", "1"))  # how much history each run pulls

# --- PostgreSQL connection ---------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "weather_db")
DB_USER = os.getenv("DB_USER", "etl_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "change_me")
