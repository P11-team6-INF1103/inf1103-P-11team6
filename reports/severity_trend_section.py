# Daniel
from datetime import date, timedelta

from reports.constants import SEVERE
from reports.incident_facts import IncidentFacts
from reports.report_section import ReportSection


class SeverityTrendSection(ReportSection):
    # Incidents and average severity over time: one point per day for short periods, per week for long ones.
    DAILY_UP_TO = 14

    @property
    def key(self) -> str:
        return "trend"

    def build(self, current: list[dict], previous: list[dict], days: int, today: date) -> list[dict]:
        step = 1 if days <= self.DAILY_UP_TO else 7
        start = today - timedelta(days=days - 1)
        buckets = []
        for offset in range(0, days, step):
            first = start + timedelta(days=offset)
            last = min(first + timedelta(days=step - 1), today)
            inside = [i for i in current if first <= IncidentFacts.day(i) <= last]
            scores = IncidentFacts.scores(inside)
            buckets.append({"from": first.isoformat(), "to": last.isoformat(), "incidents": len(inside),
                            "severe": sum(1 for s in scores if s >= SEVERE), "average_severity": IncidentFacts.average(scores)})
        return buckets

    def rows(self, data: list[dict]) -> list[tuple[str, object]]:
        return [(f"{b['from']} to {b['to']}", f"{b['incidents']} incidents, average severity {b['average_severity']}") for b in data]
