# Lennart
from abc import ABC, abstractmethod
from datetime import date

from exporters.constants import COLUMNS
from models.incident import Incident


class IncidentExporter(ABC):
    # Turns saved incidents into text for a file. This base class decides which facts are exported (one flat row per
    # incident, the same for every format); a subclass only decides how the rows are written, so a new format
    # (for example XML) is one new subclass and nothing else changes (open/closed).

    # The file ending without the dot, such as "csv".
    @property
    @abstractmethod
    def extension(self) -> str:
        ...

    # The HTTP Content-Type of the text.
    @property
    @abstractmethod
    def content_type(self) -> str:
        ...

    # Writes the rows (see rows()) as text in this format.
    @abstractmethod
    def export(self, incidents: list[Incident]) -> str:
        ...

    # The default file name, such as incidents_2026-11-13.csv.
    def file_name(self, day: date | None = None) -> str:
        return f"incidents_{(day or date.today()).isoformat()}.{self.extension}"

    # One flat dict per incident, keys in COLUMNS order. 'number' is the 1-based position in the saved list, the same
    # number the web page uses. A field the AI did not fill in is None (an incident that could not be assessed).
    @staticmethod
    def row(incident: Incident, number: int) -> dict:
        values = {
            "number": number,
            "version": incident.version,
            "logged_at": incident.timestamp,
            "location": incident.location,
            "reporter_role": incident.get("reporter_role"),
            "injury": "yes" if incident.injury else "no",
            "hazard": incident.get("hazard_type") or incident.get("hazard_category"),
            "severity": incident.get("severity_estimate"),
            "outcome": incident.get("outcome"),
            "recurrence": incident.get("likelihood_recurrence"),
            "ppe_status": incident.get("ppe_status"),
            "description": incident.description,
            "severity_reasons": list(incident.get("severity_reasons") or []),
            "prevention_actions": list(incident.get("review_prevention_actions") or []),
        }
        return {column: values[column] for column in COLUMNS}

    def rows(self, incidents: list[Incident]) -> list[dict]:
        return [self.row(incident, number) for number, incident in enumerate(incidents, start=1)]
