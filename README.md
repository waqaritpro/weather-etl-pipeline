# Weather ETL Pipeline

Batch ETL pipeline that ingests hourly weather and air quality data for the Dallas–Fort Worth metro from the [Open-Meteo API](https://open-meteo.com/), stages the raw payloads, transforms them with Python, and loads them into PostgreSQL on a daily schedule.

> **Status:** 🚧 Week 3 — daily scheduling, a data quality gate, and historical backfill are in. Analysis queries and dashboards are next. See [Roadmap](#roadmap).

## Problem

Weather and air quality data is published hourly, but the raw API responses are deeply nested JSON that's awkward to query, join, or trend over time. This pipeline turns that feed into clean, analysis-ready tables — the same raw-to-warehouse pattern used in production data platforms, at portfolio scale.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────────┐
│ Open-Meteo   │     │  Raw layer   │     │  Transform    │     │ PostgreSQL │
│ Weather API  │────▶│  (JSON files │────▶│  (Python /    │────▶│  weather_db │
│ Air Quality  │     │  data/raw/)  │     │   pandas)     │     │            │
└─────────────┘     └──────────────┘     └──────────────┘     └────────────┘
       ▲                                                             │
       └──────────────── cron (daily @ 06:00 CT) ────────────────────┘
```

**Design decisions**

- **Raw layer first.** API responses are persisted as timestamped JSON before any transformation, so the pipeline can be re-run/backfilled without re-hitting the API, and transform bugs never lose source data.
- **Idempotent loads.** Target tables use natural keys (location + observation hour) with upserts, so re-running a day is safe.
- **Quality gate before load.** Transformed data is validated (null rates, physical value ranges, duplicate keys, per-day completeness) before any upsert. Hard failures abort the run with a non-zero exit code, so bad data never reaches the warehouse.
- **No API keys.** Open-Meteo is free and keyless, which keeps the repo fully reproducible by anyone who clones it.

## Tech stack

Python 3.11 · requests · pandas · psycopg2 · PostgreSQL · Docker Compose · SQL · cron / Task Scheduler · python-dotenv · pytest

## Project structure

```
weather-etl-pipeline/
├── src/
│   ├── config.py          # locations, API endpoints, DB + quality settings
│   ├── ingest.py          # pulls weather + air quality, writes raw JSON (daily or backfill)
│   ├── transform.py       # parses raw JSON into tidy hourly DataFrames
│   ├── quality.py         # data quality gate run before load
│   ├── load.py            # quality-gated idempotent upserts into PostgreSQL
│   └── run_pipeline.py    # ingest -> load entrypoint for the scheduler
├── sql/
│   └── schema.sql         # locations + hourly_weather + hourly_air_quality DDL
├── tests/
│   ├── test_transform.py  # unit tests for the transform layer
│   └── test_quality.py    # unit tests for the quality gate
├── data/raw/              # timestamped raw API payloads (gitignored)
├── docker-compose.yml     # local Postgres (schema auto-applied on first boot)
├── .env.example           # environment variable template
├── requirements.txt
└── requirements-dev.txt   # + pytest, for running the test suite
```

## Getting started

```bash
git clone https://github.com/waqaritpro/weather-etl-pipeline.git
cd weather-etl-pipeline

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # defaults match the bundled Postgres (port 5433)

docker compose up -d            # start Postgres; schema.sql is applied automatically

python -m src.run_pipeline      # ingest today's data, then quality-check + load
```

`run_pipeline` runs ingestion followed by the quality-gated load and returns a
non-zero exit code if any stage fails. The stages can still be run individually
(`python -m src.ingest`, `python -m src.load`) for debugging.

> Not using Docker? Point `DB_*` in `.env` at any Postgres instance, then apply
> the schema once with `psql "$DATABASE_URL" -f sql/schema.sql`.

## Backfill

The daily run pulls the last `PAST_DAYS` days. To load a historical range, pass
`--start`/`--end` (inclusive, `YYYY-MM-DD`); weather comes from Open-Meteo's ERA5
archive and air quality from its history endpoint. Raw filenames are identical to
daily runs, so transform and load treat backfilled data no differently:

```bash
python -m src.run_pipeline --start 2026-01-01 --end 2026-01-31
```

Because loads are idempotent, overlapping backfills and daily runs are safe to
re-run — each (location, hour) is upserted, never duplicated.

## Data quality

Before any upsert, `src/quality.py` validates each transformed frame:

- **Duplicate keys** — no repeated (location, hour) rows *(hard fail)*
- **Null fraction** — each column's null share ≤ `MAX_NULL_FRACTION` *(hard fail)*
- **Value ranges** — each measurement within a plausible physical range, e.g. humidity 0–100% *(hard fail)*
- **Completeness** — flags any location/day with fewer than 24 hourly rows *(warning)*

Any hard failure aborts the load with a non-zero exit code, so malformed data
never reaches Postgres. Thresholds live in `src/config.py`.

## Scheduling

`run_pipeline` is designed to be driven by a scheduler. To run daily at
06:00 America/Chicago:

```bash
# Linux / macOS — crontab -e
CRON_TZ=America/Chicago
0 6 * * * cd /path/to/weather-etl-pipeline && venv/bin/python -m src.run_pipeline >> logs/pipeline.log 2>&1
```

```powershell
# Windows Task Scheduler — run once to register
$py = "C:\path\to\weather-etl-pipeline\venv\Scripts\python.exe"
$action  = New-ScheduledTaskAction -Execute $py -Argument "-m src.run_pipeline" -WorkingDirectory "C:\path\to\weather-etl-pipeline"
$trigger = New-ScheduledTaskTrigger -Daily -At 6:00AM
Register-ScheduledTask -TaskName "weather-etl-daily" -Action $action -Trigger $trigger
```

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

## Roadmap

- [x] **Week 1** — Repo scaffold, ingestion of weather + air quality raw JSON
- [x] **Week 2** — Postgres schema (DDL), transform layer, upsert loads, unit tests
- [x] **Week 3** — Dockerized Postgres, daily scheduling (cron / Task Scheduler), data quality gate, historical backfill
- [ ] **Week 4** — Analysis queries, README case study polish, sample dashboards

## Author

**Dan Waqar** — AI-first full-stack & data engineer, Dallas TX
