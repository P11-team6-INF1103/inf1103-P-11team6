# Lennart
import csv
import io
from datetime import date

import pytest

from exporters.constants import COLUMNS
from exporters.csv_incident_exporter import CsvIncidentExporter
from exporters.incident_exporter import IncidentExporter
from models.incident import Incident


def scored(description="Scaffold plank fell from level 4 near a worker", location="Site B", injury=True):
    incident = Incident(description, location, "safety_officer", injury, "2026-10-21T21:40:00")
    incident.update({"hazard_type": "fall_from_height", "severity_estimate": 4, "outcome": "stop_work_review",
                     "likelihood_recurrence": "high", "ppe_status": "not_worn",
                     "severity_reasons": ["Someone was injured", "Working at height"],
                     "review_prevention_actions": ["Inspect scaffolds daily", "Tie down planks"]})
    return incident


class LineExporter(IncidentExporter):
    extension = "txt"
    content_type = "text/plain"

    def export(self, incidents):
        return "\n".join(f"{row['number']} {row['location']}" for row in self.rows(incidents))


def test_a_row_holds_every_column_in_order_with_the_saved_facts():
    row = IncidentExporter.row(scored(), 3)
    assert list(row) == list(COLUMNS)
    assert row["number"] == 3 and row["version"] == 1 and row["logged_at"] == "2026-10-21T21:40:00"
    assert row["injury"] == "yes" and row["hazard"] == "fall_from_height" and row["severity"] == 4
    assert row["outcome"] == "stop_work_review" and row["recurrence"] == "high" and row["ppe_status"] == "not_worn"
    assert row["severity_reasons"] == ["Someone was injured", "Working at height"]
    assert row["prevention_actions"] == ["Inspect scaffolds daily", "Tie down planks"]


def test_an_incident_the_ai_never_scored_has_empty_fields_instead_of_an_error():
    bare = Incident("Worker slipped", "Site A", "officer", False, "2026-10-21T10:00:00")
    row = IncidentExporter.row(bare, 1)
    assert row["injury"] == "no" and row["severity"] is None and row["outcome"] is None
    assert row["severity_reasons"] == [] and row["prevention_actions"] == []


def test_the_hazard_falls_back_to_the_ai_category_when_there_is_no_score_yet():
    incident = Incident("Worker slipped", "Site A", "officer", False)
    incident.update({"hazard_category": "fall"})
    assert IncidentExporter.row(incident, 1)["hazard"] == "fall"


def test_the_version_counts_the_saved_older_versions():
    first, second = scored(), scored(location="Site C")
    second.follow(first)
    assert IncidentExporter.row(second, 1)["version"] == 2


def test_rows_are_numbered_from_one_in_saved_order():
    rows = LineExporter().rows([scored(), scored(location="Site C")])
    assert [row["number"] for row in rows] == [1, 2] and rows[1]["location"] == "Site C"


def test_the_default_file_name_holds_the_date_and_the_format_ending():
    assert LineExporter().file_name(date(2026, 11, 13)) == "incidents_2026-11-13.txt"
    assert LineExporter().file_name().endswith(".txt")


def test_a_new_format_is_only_a_new_subclass():
    assert LineExporter().export([scored(), scored(location="Site C")]) == "1 Site B\n2 Site C"
    with pytest.raises(TypeError):
        IncidentExporter()  # the base class cannot be used on its own


def read_csv(text):
    return list(csv.reader(io.StringIO(text)))


def test_csv_has_a_header_and_one_row_per_incident():
    rows = read_csv(CsvIncidentExporter().export([scored(), scored("Cut hand on a saw", "Site A", False)]))
    assert rows[0] == list(COLUMNS) and len(rows) == 3
    first = dict(zip(COLUMNS, rows[1]))
    assert first["number"] == "1" and first["version"] == "1" and first["injury"] == "yes"
    assert first["severity"] == "4" and first["outcome"] == "stop_work_review" and first["hazard"] == "fall_from_height"
    assert first["severity_reasons"] == "Someone was injured | Working at height"
    assert first["prevention_actions"] == "Inspect scaffolds daily | Tie down planks"
    assert dict(zip(COLUMNS, rows[2]))["number"] == "2" and dict(zip(COLUMNS, rows[2]))["injury"] == "no"


def test_csv_keeps_commas_quotes_and_line_breaks_inside_one_cell():
    text = 'Plank fell, "narrowly" missed a worker\nand hit a pipe'
    rows = read_csv(CsvIncidentExporter().export([scored(text)]))
    assert len(rows) == 2 and dict(zip(COLUMNS, rows[1]))["description"] == text


@pytest.mark.parametrize("risky", ["=HYPERLINK(\"http://x\")", "+1+1", "-2+3", "@SUM(A1)", "\tcmd", "\rcmd"])
def test_csv_stops_a_spreadsheet_from_running_text_as_a_formula(risky):
    cell = dict(zip(COLUMNS, read_csv(CsvIncidentExporter().export([scored(risky)]))[1]))["description"]
    assert cell == "'" + risky


def test_csv_leaves_numbers_and_an_unassessed_incident_alone():
    bare = Incident("Worker slipped", "Site A", "officer", False, "2026-10-21T10:00:00")  # the AI never scored it
    row = dict(zip(COLUMNS, read_csv(CsvIncidentExporter().export([bare]))[1]))
    assert row["severity"] == "" and row["outcome"] == "" and row["severity_reasons"] == ""
    assert row["description"] == "Worker slipped"


def test_an_empty_csv_export_is_still_a_valid_file():
    assert read_csv(CsvIncidentExporter().export([])) == [list(COLUMNS)]


def test_csv_uses_proper_line_endings_and_names_the_format():
    exporter = CsvIncidentExporter()
    assert "\r\n" in exporter.export([scored()]) and isinstance(exporter, IncidentExporter)
    assert exporter.extension == "csv" and exporter.content_type == "text/csv"
    assert exporter.file_name(date(2026, 11, 13)) == "incidents_2026-11-13.csv"
