# Sufi

from logic_rules.constants import SYSTEMIC_INCIDENT_COUNT
from logic_rules.outcome_rule import OutcomeRule
from models.incident import Incident


class SystemicRiskRule(OutcomeRule):
    # Rule 2: this location already has 3 or more incidents in the history window.
    @property
    def outcome(self) -> str:
        return "systemic_escalation"

    def applies(self, incident: Incident, history: list) -> bool:
        return len(history) >= SYSTEMIC_INCIDENT_COUNT
