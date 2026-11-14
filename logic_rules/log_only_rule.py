# Sufi

from logic_rules.outcome_rule import OutcomeRule
from models.incident import Incident


class LogOnlyRule(OutcomeRule):
    # Always applies, so it must be last.
    @property
    def outcome(self) -> str:
        return "log_only"

    def applies(self, incident: Incident, history: list) -> bool:
        return True
