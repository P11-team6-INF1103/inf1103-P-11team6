# Daniel
# Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
import json

from data_stores.document_store import DocumentStore
from database import Database


class DbJson(DocumentStore):
    # The same job as JsonFile, but the dict lives in the database's documents table, so it survives a server restart.
    def __init__(self, database: Database, name: str, expected_type: type) -> None:
        self._database = database
        self._name = name
        self._expected_type = expected_type

    def read(self) -> tuple[dict | list, str | None]:
        try:
            with self._database.connect() as connection:
                row = connection.execute("SELECT data FROM documents WHERE name = ?", (self._name,)).fetchone()
            data = json.loads(row["data"]) if row else self._expected_type()
        except (json.JSONDecodeError, TypeError):
            return self._expected_type(), f"{self._name} was corrupt in the database"
        except Exception as error:
            return self._expected_type(), f"could not read {self._name}: {error}"
        if not isinstance(data, self._expected_type):
            return self._expected_type(), f"{self._name} had the wrong format"
        return data, None

    def write(self, data: dict | list) -> bool:
        try:
            with self._database.connect() as connection:
                connection.execute(
                    "INSERT INTO documents (name, data) VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET data = excluded.data",
                    (self._name, json.dumps(data, default=str, sort_keys=True)))
            return True
        except Exception:
            return False

    def delete(self) -> bool:
        try:
            with self._database.connect() as connection:
                connection.execute("DELETE FROM documents WHERE name = ?", (self._name,))
            return True
        except Exception:
            return False
