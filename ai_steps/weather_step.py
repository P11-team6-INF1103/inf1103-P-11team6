# Darrel
from ai_clients.weather_client import WeatherClient
from ai_steps.enrichment_step import EnrichmentStep
from models.incident import Incident


class WeatherStep(EnrichmentStep):
    name = "Weather lookup"

    def __init__(self, weather: WeatherClient) -> None:
        self._weather = weather
