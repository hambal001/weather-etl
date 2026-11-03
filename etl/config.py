"""Pipeline configuration. Override the database with the DATABASE_URL env var."""
import os

# SQLite by default (zero setup). For PostgreSQL use e.g.
# postgresql+psycopg2://user:password@localhost:5432/weather
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///weather.db")

API_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_FIELDS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
]

# name -> (latitude, longitude)
CITIES = {
    "Lagos": (6.5244, 3.3792),
    "Abuja": (9.0765, 7.3986),
    "Kano": (12.0022, 8.5920),
    "Port Harcourt": (4.8156, 7.0498),
}

TIMEZONE = "Africa/Lagos"

# Validation limits used by the transform step
LIMITS = {
    "temperature_c": (-10.0, 60.0),
    "humidity_pct": (0.0, 100.0),
    "precipitation_mm": (0.0, 500.0),
    "wind_speed_kmh": (0.0, 400.0),
}
