# Daniel
from abc import abstractmethod
from collections import Counter, defaultdict
from datetime import date

from reports.incident_facts import IncidentFacts
from reports.report_section import ReportSection


class RankingSection(ReportSection):
    # Shared work of the two rankings: count incidents per label, compare with the period before, keep the top few.
    # A subclass only says which field to group by and how to name it.
    TOP = 5

    @abstractmethod
    def _label(self, incident: dict) -> str:
        ...

    def build(self, current: list[dict], previous: list[dict], days: int, today: date) -> list[dict]:
        groups: dict[str, list[dict]] = defaultdict(list)
        for incident in current:
            groups[self._label(incident)].append(incident)
        earlier = Counter(self._label(i) for i in previous)
        ranked = []
        for label, items in groups.items():
            scores = IncidentFacts.scores(items)
            ranked.append({"name": label, "count": len(items), "previous_count": earlier.get(label, 0),
                           "share": round(100 * len(items) / len(current)),
                           "worst_severity": max(scores, default=0), "average_severity": IncidentFacts.average(scores)})
        ranked.sort(key=lambda r: (-r["count"], -r["worst_severity"], r["name"]))
        return ranked[: self.TOP]

    def rows(self, data: list[dict]) -> list[tuple[str, object]]:
        return [(f"{r['name']}", f"{r['count']} incidents, worst severity {r['worst_severity']}") for r in data]
