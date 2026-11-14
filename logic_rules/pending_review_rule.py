# Sufi

from logic_rules.outcome_rule import OutcomeRule
from models.incident import Incident


class PendingReviewRule(OutcomeRule):
    # The AI could not assess the incident, so a person must.
    @property
    def outcome(self) -> str:
        return "pending_review"

    def applies(self, incident: Incident, history: list) -> bool:
        return bool(incident.get("assessment_error"))
