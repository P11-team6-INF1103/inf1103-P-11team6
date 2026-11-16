# Daniel
from abc import ABC, abstractmethod


class DocumentStore(ABC):
    # Interface for one stored JSON document. A file and a database row are interchangeable (LSP), and a new
    # storage is a new subclass (OCP).

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
