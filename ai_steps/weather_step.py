# Darrel
from ai_clients.weather_client import WeatherClient
from ai_steps.enrichment_step import EnrichmentStep
from models.incident import Incident


class WeatherStep(EnrichmentStep):
    name = "Weather lookup"

    def __init__(self, weather: WeatherClient) -> None:
        self._weather = weather

    # Only when the description mentions weather.
    def should_run(self, incident: Incident) -> bool:
        return bool(incident.get("run_weather"))

    def skipped_fields(self) -> dict:
        return {"weather_available": False, "temperature_c": None, "humidity_pct": None,
                "precipitation_mm": None, "enrichment_error": None}

    def run(self, incident: Incident, history: list[Incident]) -> dict:
        weather = self._weather.get_weather(incident.timestamp)
        if weather is None:
            return self.error_fields("Weather data unavailable or invalid")
        return {"weather_available": True, "enrichment_error": None, **weather}
