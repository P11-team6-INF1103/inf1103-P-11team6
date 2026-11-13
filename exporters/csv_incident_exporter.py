# Lennart
import csv
import io

from exporters.constants import COLUMNS, FORMULA_STARTS, LIST_SEPARATOR
from exporters.incident_exporter import IncidentExporter
from models.incident import Incident


class CsvIncidentExporter(IncidentExporter):
    # A spreadsheet file: one header row, then one row per incident.
    @property
    def extension(self) -> str:
        return "csv"

    @property
    def content_type(self) -> str:
        return "text/csv"

    # A cell as safe text: a list becomes one cell, and text that a spreadsheet would run as a formula gets a ' in front.
    @staticmethod
    def _cell(value: object) -> object:
        if value is None:
            return ""
        if isinstance(value, list):
            value = LIST_SEPARATOR.join(str(item) for item in value)
        if isinstance(value, str) and value.startswith(FORMULA_STARTS):
            return "'" + value
        return value

    def export(self, incidents: list[Incident]) -> str:
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(COLUMNS)
        for row in self.rows(incidents):
            writer.writerow([self._cell(row[column]) for column in COLUMNS])
        return out.getvalue()
