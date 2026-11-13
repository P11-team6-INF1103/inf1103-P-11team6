# Lennart
import json

from exporters.incident_exporter import IncidentExporter
from models.incident import Incident


class JsonIncidentExporter(IncidentExporter):
    # The same rows as a JSON list, for another program; lists stay lists.
    @property
    def extension(self) -> str:
        return "json"

    @property
    def content_type(self) -> str:
        return "application/json"

    def export(self, incidents: list[Incident]) -> str:
        return json.dumps(self.rows(incidents), indent=2, ensure_ascii=False) + "\n"
