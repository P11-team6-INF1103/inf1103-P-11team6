# Darrel
import logging

import requests

from ai_clients.response_cache import ResponseCache

logger = logging.getLogger(__name__)


class WeatherClient:
    # Every incident is on a Singapore construction site, so the weather is looked up for Singapore.
    _LATITUDE = 1.3521
    _LONGITUDE = 103.8198
