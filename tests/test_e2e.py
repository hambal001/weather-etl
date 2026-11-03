"""End-to-end: run the real pipeline with the HTTP call replaced by fake data."""
from sqlalchemy import create_engine, text

from etl import config, pipeline


def fake_extract_all():
    hours = [f"2026-11-03T{h:02d}:00" for h in range(24)]
    return {
        "Lagos": {
            "hourly": {
                "time": hours,
                "temperature_2m": [26.0 + (h % 5) * 0.5 for h in range(24)],
                "relative_humidity_2m": [85] * 24,
                "precipitation": [0.0] * 24,
                "wind_speed_10m": [9.0] * 24,
            }
        }
    }


def test_pipeline_end_to_end(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(config, "DATABASE_URL", db_url)
    monkeypatch.setattr(pipeline, "extract_all", fake_extract_all)
    monkeypatch.chdir(tmp_path)  # so rejected_rows.csv lands in the temp dir

    assert pipeline.run() == 0
    assert pipeline.run() == 0  # second run must not duplicate

    with create_engine(db_url).connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM weather_hourly")).scalar() == 24
        assert conn.execute(text("SELECT COUNT(*) FROM etl_runs")).scalar() == 2
