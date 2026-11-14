# Sufi

from logic_rules.outcome_rule import OutcomeRule
from models.incident import Incident


class PhotoMismatchRule(OutcomeRule):
    # New in Part 2: the AI says the uploaded photo does not show what the description says.
    @property
    def outcome(self) -> str:
        return "photo_review"

    def applies(self, incident: Incident, history: list) -> bool:
        return incident.get("photo_matches_description") is False
