# Ren Xiang

class FakeWeather:
    def __init__(self, weather: dict | None = None) -> None:
        self.weather = weather

    def get_weather(self, timestamp: str | None) -> dict | None:
        return self.weather