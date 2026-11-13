# Lennart
import os

from exporters.csv_incident_exporter import CsvIncidentExporter
from exporters.incident_exporter import IncidentExporter
from exporters.json_incident_exporter import JsonIncidentExporter


class ExporterFactory:
    # Picks the exporter for a format name. To support a new format, add its subclass here and nowhere else.
    _FORMATS = {"csv": CsvIncidentExporter, "json": JsonIncidentExporter}

    # The format names that can be chosen, such as ("csv", "json").
    @classmethod
    def names(cls) -> tuple[str, ...]:
        return tuple(cls._FORMATS)

    # A new exporter for 'name' (any capitals); raises ValueError for a format that does not exist.
    @classmethod
    def create(cls, name: str) -> IncidentExporter:
        exporter = cls._FORMATS.get(str(name).strip().lower())
        if exporter is None:
            raise ValueError(f"Unknown export format '{name}'. Choose one of: {', '.join(cls._FORMATS)}.")
        return exporter()

    # The exporter for a file path, chosen by its ending (incidents.csv, incidents.json); ValueError if it has none that fits.
    @classmethod
    def for_path(cls, path: str) -> IncidentExporter:
        return cls.create(os.path.splitext(path)[1].lstrip("."))
