# Daniel
from abc import ABC, abstractmethod


class DocumentStore(ABC):
    # Interface for one stored JSON document. DataManager only calls these three methods, so a file and a database
    # row are interchangeable (Liskov) and a new kind of storage is a new subclass, not a change to DataManager (open/closed).

    # The stored value (an empty list or dict if there is none) and a message if something was wrong; never raises.
    @abstractmethod
    def read(self) -> tuple[dict | list, str | None]:
        ...

    # Replaces the stored value; returns False instead of raising.
    @abstractmethod
    def write(self, data: dict | list) -> bool:
        ...

    # Removes the stored value; returns False only if it exists and cannot be removed.
    @abstractmethod
    def delete(self) -> bool:
        ...
