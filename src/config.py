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
