# Darrel
import logging

import requests

from ai_clients.response_cache import ResponseCache

logger = logging.getLogger(__name__)


class WeatherClient:
    # Every incident is on a Singapore construction site, so the weather is looked up for Singapore.
    _LATITUDE = 1.3521
    _LONGITUDE = 103.8198

    def __init__(self, cache: ResponseCache) -> None:
        self._cache = cache

    # True if the weather dict has a sensible temperature, humidity and rainfall.
    @staticmethod
    def is_valid(weather: object) -> bool:
        if not isinstance(weather, dict):
            return False
        temperature, humidity, rain = (weather.get(k) for k in ("temperature_c", "humidity_pct", "precipitation_mm"))
        if not isinstance(rain, (int, float)) or rain < 0:
            return False
        if not isinstance(temperature, (int, float)) or not -10 <= temperature <= 50:
            return False
        return isinstance(humidity, (int, float)) and 0 <= humidity <= 100

    # Fetches the current Singapore weather from Open-Meteo; returns None if the call fails.
    def _call_api(self) -> dict | None:
        try:
            response = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": self._LATITUDE,
                    "longitude": self._LONGITUDE,
                    "current": "temperature_2m,relative_humidity_2m,precipitation",
                    "timezone": "Asia/Singapore",
                },
                timeout=8,
            )
            response.raise_for_status()
            current = response.json().get("current", {})
        except Exception as error:
            logger.warning("Weather API failed: %s", error)
            return None
        return {
            "temperature_c": current.get("temperature_2m"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "precipitation_mm": current.get("precipitation"),
        }

    # Validated weather for the incident hour (from the cache when present), or None.
    def get_weather(self, timestamp: str | None) -> dict | None:
        key = ResponseCache.make_key("weather", str(timestamp or "")[:13])
        weather = self._cache.get(key)
        if not self.is_valid(weather):
            weather = self._call_api()
        if not self.is_valid(weather):
            return None
        self._cache.put(key, weather)
        return weather
