# Ren Xiang
from tests.fakes import WEB_REPLY


class FakeSearch:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def search_json(self, prompt: str, schema: dict, subject: str | None = None) -> dict:
        if self.error:
            raise self.error
        return WEB_REPLY