"""Load: write validated rows to a SQL database idempotently."""
import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import DateTime, bindparam, create_engine, text

log = logging.getLogger(__name__)

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS weather_hourly (
        city TEXT NOT NULL,
        observed_at TIMESTAMP NOT NULL,
        temperature_c REAL,
        humidity_pct REAL,
        precipitation_mm REAL,
        wind_speed_kmh REAL,
        PRIMARY KEY (city, observed_at)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS etl_runs (
        run_at TIMESTAMP NOT NULL,
        rows_loaded INTEGER NOT NULL,
        rows_rejected INTEGER NOT NULL,
        status TEXT NOT NULL
    )
    """,
]

VIEW_BODY = """
    VIEW daily_summary AS
    SELECT city,
           DATE(observed_at) AS day,
           AVG(temperature_c) AS avg_temp_c,
           MAX(temperature_c) AS max_temp_c,
           MIN(temperature_c) AS min_temp_c,
           SUM(precipitation_mm) AS total_rain_mm
    FROM weather_hourly
    GROUP BY city, DATE(observed_at)
"""


def get_engine(url: str):
    return create_engine(url)


def init_db(engine) -> None:
    with engine.begin() as conn:
        for stmt in SCHEMA:
            conn.execute(text(stmt))
        # CREATE VIEW syntax differs slightly between SQLite and PostgreSQL
        if engine.dialect.name == "sqlite":
            conn.execute(text("CREATE " + VIEW_BODY.replace("VIEW", "VIEW IF NOT EXISTS", 1)))
        else:
            conn.execute(text("CREATE OR REPLACE" + VIEW_BODY))


def load(engine, valid: pd.DataFrame, rejected: pd.DataFrame) -> int:
    """Upsert valid rows (delete the overlapping window, then insert) and log the run.

    Safe to re-run: running twice on the same data never creates duplicates.
    """
    init_db(engine)
    with engine.begin() as conn:
        # Typed binds make SQLAlchemy format datetimes the same way pandas.to_sql
        # does, so the BETWEEN window matches the stored values on every backend.
        delete_stmt = text(
            "DELETE FROM weather_hourly WHERE city = :city "
            "AND observed_at BETWEEN :lo AND :hi"
        ).bindparams(bindparam("lo", type_=DateTime), bindparam("hi", type_=DateTime))
        for city, group in valid.groupby("city"):
            conn.execute(
                delete_stmt,
                {"city": city, "lo": group["observed_at"].min().to_pydatetime(),
                 "hi": group["observed_at"].max().to_pydatetime()},
            )
        if not valid.empty:
            valid.to_sql("weather_hourly", conn, if_exists="append", index=False)
        conn.execute(
            text(
                "INSERT INTO etl_runs (run_at, rows_loaded, rows_rejected, status) "
                "VALUES (:run_at, :loaded, :rejected, :status)"
            ).bindparams(bindparam("run_at", type_=DateTime)),
            {
                "run_at": datetime.now(timezone.utc).replace(tzinfo=None),
                "loaded": int(len(valid)),
                "rejected": int(len(rejected)),
                "status": "ok" if not valid.empty else "empty",
            },
        )
    log.info("Loaded %d rows (%d rejected)", len(valid), len(rejected))
    return len(valid)
