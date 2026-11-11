# Daniel
from reports.ranking_section import RankingSection


class LocationRankingSection(RankingSection):
    # The places with the most incidents, so the busiest sites stand out.
    @property
    def key(self) -> str:
        return "locations"

    def _label(self, incident: dict) -> str:
        return str(incident.get("location") or "Unknown").strip() or "Unknown"

    def notes(self, data: list[dict]) -> list[str]:
        if not data:
            return []
        top = data[0]
        return [f"{top['name']} had the most incidents ({top['count']}, worst severity {top['worst_severity']})."]
