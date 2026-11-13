# Daniel
from datetime import date

from reports.constants import SEVERE
from reports.incident_facts import IncidentFacts
from reports.report_section import ReportSection


class OverviewSection(ReportSection):
    # Totals for the period against the one before it: how many, how severe, how many still open.
    @property
    def key(self) -> str:
        return "overview"

    def build(self, current: list[dict], previous: list[dict], days: int, today: date) -> dict:
        scores = IncidentFacts.scores(current)
        before = IncidentFacts.scores(previous)
        return {
            "total": len(current), "previous_total": len(previous), "change": len(current) - len(previous),
            "severe": sum(1 for s in scores if s >= SEVERE), "previous_severe": sum(1 for s in before if s >= SEVERE),
            "average_severity": IncidentFacts.average(scores), "previous_average_severity": IncidentFacts.average(before),
            "injuries": sum(1 for i in current if i.get("injury")),
            "open": sum(1 for i in current if not i.get("resolved")),
            "resolved": sum(1 for i in current if i.get("resolved")),
        }

    def notes(self, data: dict) -> list[str]:
        if not data["total"]:
            return ["No incidents were logged in this period."]
        notes = []
        change = data["change"]
        if data["previous_total"] == 0:
            notes.append(f"{data['total']} incident(s) logged; there were none in the period before.")
        elif change:
            notes.append(f"Incidents are {'up' if change > 0 else 'down'} by {abs(change)} "
                         f"({data['previous_total']} before, {data['total']} now).")
        else:
            notes.append(f"Incidents are unchanged at {data['total']}.")
        if data["severe"] > data["previous_severe"]:
            notes.append(f"Severe incidents (severity {SEVERE}+) rose from {data['previous_severe']} to {data['severe']}.")
        if data["open"]:
            notes.append(f"{data['open']} of these are still open.")
        return notes

    def rows(self, data: dict) -> list[tuple[str, object]]:
        return list(data.items())
