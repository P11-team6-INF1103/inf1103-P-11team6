# Daniel
from abc import ABC, abstractmethod
from datetime import date


class ReportSection(ABC):
    # Interface for one block of the summary (an overview, a ranking, a trend). TrendReport asks every section it
    # holds to build itself from the same two lists, so a new kind of block is a new subclass and nothing else changes.

    # Short name used as the key in the result and as the heading in the CSV.
    @property
    @abstractmethod
    def key(self) -> str:
        ...

    # The block's numbers for the current period; previous is the period just before it, for comparison.
    @abstractmethod
    def build(self, current: list[dict], previous: list[dict], days: int, today: date) -> dict | list:
        ...

    # Plain sentences worth showing at the top of the report; nothing if there is nothing to say.
    def notes(self, data: dict | list) -> list[str]:
        return []

    # Flat (item, value) pairs for the CSV export.
    @abstractmethod
    def rows(self, data: dict | list) -> list[tuple[str, object]]:
        ...
