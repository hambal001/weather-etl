"""Transform: flatten raw API JSON, clean it, and validate it."""
import logging

import pandas as pd

from etl import config

log = logging.getLogger(__name__)

RENAME = {
    "time": "observed_at",
    "temperature_2m": "temperature_c",
    "relative_humidity_2m": "humidity_pct",
    "precipitation": "precipitation_mm",
    "wind_speed_10m": "wind_speed_kmh",
}
NUMERIC = ["temperature_c", "humidity_pct", "precipitation_mm", "wind_speed_kmh"]


def flatten(city: str, payload: dict) -> pd.DataFrame:
    """Turn one city's column-oriented JSON into a tidy DataFrame (one row per hour)."""
    df = pd.DataFrame(payload["hourly"]).rename(columns=RENAME)
    df.insert(0, "city", city)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Fix types, drop unusable rows and duplicates."""
    df = df.copy()
    df["observed_at"] = pd.to_datetime(df["observed_at"], errors="coerce")
    for col in NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["observed_at"])
    df = df.drop_duplicates(subset=["city", "observed_at"], keep="last")
    return df


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split into (valid, rejected). Rejected rows carry a 'reason' column."""
    reasons = pd.Series("", index=df.index)
    for col, (low, high) in config.LIMITS.items():
        bad_null = df[col].isna()
        bad_range = (df[col] < low) | (df[col] > high)
        reasons = reasons.where(~bad_null, reasons + f"{col}:missing;")
        reasons = reasons.where(~bad_range, reasons + f"{col}:out_of_range;")
    rejected = df[reasons != ""].copy()
    rejected["reason"] = reasons[reasons != ""]
    valid = df[reasons == ""].copy()
    return valid, rejected


def transform(raw: dict[str, dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Full transform for all cities. Returns (valid_rows, rejected_rows)."""
    if not raw:
        empty = pd.DataFrame(columns=["city", "observed_at", *NUMERIC])
        return empty, empty.assign(reason=[])
    frames = [flatten(city, payload) for city, payload in raw.items()]
    df = clean(pd.concat(frames, ignore_index=True))
    valid, rejected = validate(df)
    log.info("Transform: %d valid, %d rejected", len(valid), len(rejected))
    return valid, rejected
