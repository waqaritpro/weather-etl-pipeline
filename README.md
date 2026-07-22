# Weather ETL Pipeline

Batch ETL pipeline that ingests hourly weather and air quality data for the Dallas–Fort Worth metro from the [Open-Meteo API](https://open-meteo.com/), stages the raw payloads, transforms them with Python, and loads them into PostgreSQL on a daily schedule.

> **Status:** 🚧 Week 1 — ingestion layer complete. Transformations, Postgres load, and scheduling land over the next three weeks. See [Roadmap](#roadmap).

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
- **No API keys.** Open-Meteo is free and keyless, which keeps the repo fully reproducible by anyone who clones it.

## Tech stack

Python 3.11 · requests · pandas · PostgreSQL · SQL · cron · python-dotenv

## Project structure

```
weather-etl-pipeline/
├── src/
│   ├── config.py        # locations, API endpoints, settings
│   └── ingest.py        # pulls weather + air quality, writes raw JSON
├── sql/                 # DDL and load queries (week 2)
├── tests/               # unit tests (week 2)
├── data/raw/            # timestamped raw API payloads (gitignored)
├── .env.example         # environment variable template
└── requirements.txt
```

## Getting started

```bash
git clone https://github.com/waqaritpro/weather-etl-pipeline.git
cd weather-etl-pipeline

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # defaults work out of the box

python -m src.ingest            # pull today's data into data/raw/
```

## Roadmap

- [x] **Week 1** — Repo scaffold, ingestion of weather + air quality raw JSON
- [ ] **Week 2** — Postgres schema (DDL), transform layer, upsert loads, unit tests
- [ ] **Week 3** — Daily cron scheduling, data quality checks, backfill support
- [ ] **Week 4** — Analysis queries, README case study polish, sample dashboards

## Author

**Dan Waqar** — AI-first full-stack & data engineer, Dallas TX
