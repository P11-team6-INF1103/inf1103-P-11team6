# Daniel
import csv
import io
from datetime import date, timedelta

from reports.hazard_ranking_section import HazardRankingSection
from reports.incident_facts import IncidentFacts
from reports.location_ranking_section import LocationRankingSection
from reports.overview_section import OverviewSection
from reports.report_section import ReportSection
from reports.severity_trend_section import SeverityTrendSection


class TrendReport:
    # Builds the summary report: it owns its sections (composition) and runs each one over the incidents of the
    # chosen period and the period before it. It holds no section-specific rules itself.
    MIN_DAYS = 1
    MAX_DAYS = 180

    def __init__(self, sections: list[ReportSection]) -> None:
        self._sections = list(sections)

    # The usual set of sections, with the hazard names the rest of the app uses.
    @classmethod
    def standard(cls, hazard_names: dict[str, str] | None = None) -> "TrendReport":
        return cls([OverviewSection(), HazardRankingSection(hazard_names), LocationRankingSection(), SeverityTrendSection()])

    # The report for the last `days` days ending today, compared with the same number of days before them.
    # Incidents whose timestamp cannot be read are left out and counted in "skipped".
    def build(self, incidents: list[dict], days: int, today: date | None = None) -> dict:
        today = today or date.today()
        start = today - timedelta(days=days - 1)
        before_start = start - timedelta(days=days)
        current, previous, skipped = [], [], 0
        for incident in incidents:
            day = IncidentFacts.day(incident)
            if day is None:
                skipped += 1
            elif start <= day <= today:
                current.append(incident)
            elif before_start <= day < start:
                previous.append(incident)
        sections, notes = {}, []
        for section in self._sections:
            data = section.build(current, previous, days, today)
            sections[section.key] = data
            notes.extend(section.notes(data))
        return {"days": days, "from": start.isoformat(), "to": today.isoformat(), "skipped": skipped,
                "notes": notes, "sections": sections}

    # The same report as CSV text (section, item, value), for a spreadsheet.
    def to_csv(self, report: dict) -> str:
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["section", "item", "value"])
        writer.writerow(["period", "from", report["from"]])
        writer.writerow(["period", "to", report["to"]])
        for section in self._sections:
            for item, value in section.rows(report["sections"][section.key]):
                writer.writerow([section.key, item, value])
        return out.getvalue()
