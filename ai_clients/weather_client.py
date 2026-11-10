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
