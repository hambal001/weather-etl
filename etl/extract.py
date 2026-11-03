"""Extract: pull hourly weather from the free Open-Meteo API (no API key)."""
import logging
import time

import requests

from etl import config

log = logging.getLogger(__name__)


def fetch_city(city: str, lat: float, lon: float, retries: int = 3, timeout: int = 20) -> dict:
    """Return the raw JSON payload for one city, retrying on transient errors."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(config.HOURLY_FIELDS),
        "timezone": config.TIMEZONE,
        "forecast_days": 2,
    }
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(config.API_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
            if "hourly" not in payload:
                raise ValueError(f"No 'hourly' block in response for {city}")
            return payload
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            wait = 2 ** attempt
            log.warning("Fetch %s failed (attempt %d/%d): %s", city, attempt, retries, exc)
            time.sleep(wait)
    raise RuntimeError(f"Could not fetch {city} after {retries} attempts") from last_error


def extract_all(cities: dict | None = None) -> dict[str, dict]:
    """Fetch every configured city. A failing city is logged and skipped, not fatal."""
    cities = cities or config.CITIES
    results = {}
    for name, (lat, lon) in cities.items():
        try:
            results[name] = fetch_city(name, lat, lon)
        except RuntimeError as exc:
            log.error("Skipping %s: %s", name, exc)
    return results
