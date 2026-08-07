-- Weather ETL Pipeline schema
--
-- Star-ish layout: a small locations dimension plus two hourly fact tables,
-- one per raw source (weather, air quality). Both fact tables are keyed on
-- (location_name, observation_time) so loads can upsert idempotently --
-- re-running an ingest+load for a day never creates duplicate hours.

CREATE TABLE IF NOT EXISTS locations (
    name        TEXT PRIMARY KEY,
    latitude    DOUBLE PRECISION NOT NULL,
    longitude   DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS hourly_weather (
    location_name           TEXT NOT NULL REFERENCES locations (name),
    observation_time        TIMESTAMPTZ NOT NULL,
    temperature_2m          DOUBLE PRECISION,
    relative_humidity_2m    DOUBLE PRECISION,
    precipitation            DOUBLE PRECISION,
    wind_speed_10m           DOUBLE PRECISION,
    wind_gusts_10m           DOUBLE PRECISION,
    surface_pressure         DOUBLE PRECISION,
    source_file              TEXT NOT NULL,
    loaded_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (location_name, observation_time)
);

CREATE TABLE IF NOT EXISTS hourly_air_quality (
    location_name       TEXT NOT NULL REFERENCES locations (name),
    observation_time    TIMESTAMPTZ NOT NULL,
    pm10                 DOUBLE PRECISION,
    pm2_5                DOUBLE PRECISION,
    ozone                 DOUBLE PRECISION,
    nitrogen_dioxide      DOUBLE PRECISION,
    us_aqi                DOUBLE PRECISION,
    source_file           TEXT NOT NULL,
    loaded_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (location_name, observation_time)
);

CREATE INDEX IF NOT EXISTS idx_hourly_weather_observation_time
    ON hourly_weather (observation_time);

CREATE INDEX IF NOT EXISTS idx_hourly_air_quality_observation_time
    ON hourly_air_quality (observation_time);
