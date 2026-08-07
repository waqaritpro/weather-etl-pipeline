"""Load layer: idempotent upserts of tidy hourly data into PostgreSQL.

Reads every raw file in data/raw/ via src.transform, then upserts into the
tables defined by sql/schema.sql. Upserts key on (location_name,
observation_time), so re-running a day's load is always safe.

Usage:
    python -m src.load
"""

import logging
import sys

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from src.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER, LOCATIONS, RAW_DATA_DIR
from src.transform import transform_directory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

WEATHER_COLUMNS = [
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

AIR_QUALITY_COLUMNS = [
    "location_name",
    "observation_time",
    "pm10",
    "pm2_5",
    "ozone",
    "nitrogen_dioxide",
    "us_aqi",
    "source_file",
]

CONFLICT_KEY = ("location_name", "observation_time")


def get_connection():
    """Open a new PostgreSQL connection using the configured credentials."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def load_locations(conn) -> None:
    """Upsert the configured locations dimension."""
    rows = [(loc["name"], loc["latitude"], loc["longitude"]) for loc in LOCATIONS]
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO locations (name, latitude, longitude)
            VALUES %s
            ON CONFLICT (name) DO UPDATE SET
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude
            """,
            rows,
        )
    conn.commit()


def _upsert(conn, df: pd.DataFrame, table: str, columns: list) -> int:
    """Upsert a tidy DataFrame into `table`, keyed on CONFLICT_KEY."""
    if df.empty:
        return 0

    rows = list(df[columns].itertuples(index=False, name=None))
    update_cols = [c for c in columns if c not in CONFLICT_KEY]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)

    query = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT ({', '.join(CONFLICT_KEY)}) DO UPDATE SET {set_clause}"
    )

    with conn.cursor() as cur:
        execute_values(cur, query, rows)
    conn.commit()
    return len(rows)


def load_weather(conn, df: pd.DataFrame) -> int:
    """Upsert tidy hourly weather rows. Returns the number of rows upserted."""
    return _upsert(conn, df, "hourly_weather", WEATHER_COLUMNS)


def load_air_quality(conn, df: pd.DataFrame) -> int:
    """Upsert tidy hourly air quality rows. Returns the number of rows upserted."""
    return _upsert(conn, df, "hourly_air_quality", AIR_QUALITY_COLUMNS)


def main() -> int:
    weather_df, air_quality_df = transform_directory(RAW_DATA_DIR)

    if weather_df.empty and air_quality_df.empty:
        logger.warning("No raw files found in %s; nothing to load", RAW_DATA_DIR)
        return 0

    conn = get_connection()
    try:
        load_locations(conn)
        weather_rows = load_weather(conn, weather_df)
        air_quality_rows = load_air_quality(conn, air_quality_df)
        logger.info(
            "Upserted %d weather rows and %d air quality rows",
            weather_rows,
            air_quality_rows,
        )
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
