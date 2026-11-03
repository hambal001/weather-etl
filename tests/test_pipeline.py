import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from etl.load import load
from etl.transform import clean, flatten, transform, validate


@pytest.fixture
def raw():
    """Fake API payload: 4 hourly rows for Lagos, including three bad ones."""
    return {
        "Lagos": {
            "hourly": {
                "time": [
                    "2026-11-03T00:00",
                    "2026-11-03T01:00",
                    "2026-11-03T02:00",
                    "2026-11-03T03:00",
                ],
                "temperature_2m": [26.1, 25.8, 999.0, 25.0],   # row 3 out of range
                "relative_humidity_2m": [88, 90, 85, None],      # row 4 missing
                "precipitation": [0.0, 0.2, 0.0, 0.0],
                "wind_speed_10m": [10.5, 9.8, 11.0, 8.0],
            }
        },
        "Abuja": {
            "hourly": {
                "time": ["2026-11-03T00:00"],
                "temperature_2m": [24.0],
                "relative_humidity_2m": [70],
                "precipitation": [0.0],
                "wind_speed_10m": [7.0],
            }
        },
    }


def test_flatten_shape_and_columns(raw):
    df = flatten("Lagos", raw["Lagos"])
    assert len(df) == 4
    assert list(df.columns[:2]) == ["city", "observed_at"]
    assert "temperature_c" in df.columns


def test_clean_drops_duplicates_and_bad_timestamps():
    df = pd.DataFrame(
        {
            "city": ["Lagos", "Lagos", "Lagos"],
            "observed_at": ["2026-11-03T00:00", "2026-11-03T00:00", "not a date"],
            "temperature_c": [26, 27, 28],
            "humidity_pct": [80, 80, 80],
            "precipitation_mm": [0, 0, 0],
            "wind_speed_kmh": [5, 5, 5],
        }
    )
    out = clean(df)
    assert len(out) == 1
    assert out.iloc[0]["temperature_c"] == 27  # keep="last"


def test_validate_splits_good_and_bad_rows(raw):
    valid, rejected = transform(raw)
    assert len(valid) == 3          # 2 good Lagos rows + 1 Abuja row
    assert len(rejected) == 2
    reasons = " ".join(rejected["reason"])
    assert "temperature_c:out_of_range" in reasons
    assert "humidity_pct:missing" in reasons


def test_load_is_idempotent(raw):
    engine = create_engine("sqlite:///:memory:")
    valid, rejected = transform(raw)
    load(engine, valid, rejected)
    load(engine, valid, rejected)  # run twice
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM weather_hourly")).scalar()
        runs = conn.execute(text("SELECT COUNT(*) FROM etl_runs")).scalar()
    assert n == 3      # no duplicates after a re-run
    assert runs == 2   # but both runs are logged


def test_daily_summary_view(raw):
    engine = create_engine("sqlite:///:memory:")
    valid, rejected = transform(raw)
    load(engine, valid, rejected)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT avg_temp_c, total_rain_mm FROM daily_summary WHERE city='Lagos'")
        ).one()
    assert round(row[0], 2) == 25.95
    assert round(row[1], 2) == 0.2
