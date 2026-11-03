# Nigeria Weather ETL Pipeline

A small, production-style ETL pipeline in Python. It pulls hourly weather data for four
Nigerian cities (Lagos, Abuja, Kano, Port Harcourt) from the free Open-Meteo API,
validates and cleans it with pandas, and loads it into a SQL database.

**Stack:** Python, pandas, SQLAlchemy, SQLite (PostgreSQL-ready), pytest, GitHub Actions.

## Pipeline

```
Open-Meteo API  ->  extract.py  ->  transform.py  ->  load.py  ->  SQL database
                    (retries,       (flatten, clean,   (idempotent    weather_hourly
                     per-city        validate, reject   upsert +       etl_runs
                     failure         bad rows)          run log)       daily_summary (view)
                     isolation)
```

- **Extract:** HTTP calls with timeouts and exponential-backoff retries. One failing city is
  logged and skipped instead of crashing the whole run.
- **Transform:** flattens the column-oriented JSON into one row per city per hour, fixes types,
  removes duplicates, and validates ranges (e.g. humidity 0-100). Rows that fail validation
  go to `rejected_rows.csv` with a reason instead of being silently dropped.
- **Load:** idempotent. It deletes the overlapping time window and re-inserts in one
  transaction, so re-running never creates duplicates. Every run is logged in `etl_runs`.
- **Analytics:** the `daily_summary` view gives average, min and max temperature and total
  rainfall per city per day.

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q          # tests run offline, no network needed
python -m etl.pipeline       # creates weather.db
```

Query the result:

```bash
sqlite3 weather.db "SELECT * FROM daily_summary ORDER BY day, city;"
```

## Use PostgreSQL instead of SQLite

```bash
pip install psycopg2-binary
export DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/weather"
python -m etl.pipeline
```

The view is created with `CREATE OR REPLACE VIEW` on PostgreSQL and `CREATE VIEW IF NOT EXISTS`
on SQLite. The SQLite path is covered by the tests; the PostgreSQL path has not been tested
against a live server, so check it before relying on it.

## Scheduling

The included GitHub Actions workflow (`.github/workflows/etl.yml`) runs the tests and the
pipeline every 6 hours and uploads the resulting database as an artifact. Locally you can use
cron instead:

```
0 */6 * * *  cd /path/to/weather-etl && /usr/bin/python3 -m etl.pipeline >> etl.log 2>&1
```

## Tests

- Transform: flattening, de-duplication, range and missing-value validation
- Load: idempotency (running twice gives the same row count), run logging, the summary view
- End-to-end: the full pipeline with the API call replaced by fake data

One test caught a real bug during development: a timestamp-format mismatch between pandas and
a raw SQL `DELETE` that left a boundary row undeleted on re-runs. It is fixed with typed bind
parameters.

## Ideas to extend it

- Orchestrate with Airflow or Prefect instead of cron
- Add a Streamlit or Power BI dashboard on top of `daily_summary`
- Backfill historical data from Open-Meteo's archive endpoint
- Add data-quality alerts (e.g. email when more than 5% of rows are rejected)
