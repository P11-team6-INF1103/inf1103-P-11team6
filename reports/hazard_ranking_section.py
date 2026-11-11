# Daniel
from reports.ranking_section import RankingSection


class HazardRankingSection(RankingSection):
    # The hazard types behind the incidents, named the way the rest of the app names them.
    def __init__(self, hazard_names: dict[str, str] | None = None) -> None:
        self._names = hazard_names or {}

    @property
    def key(self) -> str:
        return "hazards"

    def _label(self, incident: dict) -> str:
        hazard = incident.get("hazard_type") or incident.get("hazard_category") or "unassessed"
        return self._names.get(hazard, str(hazard))

    def notes(self, data: list[dict]) -> list[str]:
        return [f"The most common hazard was {data[0]['name'].lower()} ({data[0]['share']}% of incidents)."] if data else []
