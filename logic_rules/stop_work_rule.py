# Sufi

from logic_rules.constants import HIGH_SEVERITY
from logic_rules.outcome_rule import OutcomeRule
from models.incident import Incident


class StopWorkRule(OutcomeRule):
    # Rule 1 (multi-condition, two AI-derived fields): severity 4 or more, or an injury with high recurrence likelihood.
    @property
    def outcome(self) -> str:
        return "stop_work_review"

    def applies(self, incident: Incident, history: list) -> bool:
        severity = incident.get("severity_estimate", 0) or 0
        recurrence = incident.get("likelihood_recurrence", "unknown")
        return severity >= HIGH_SEVERITY or (incident.injury and recurrence == "high")
