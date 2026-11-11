# Daniel
from database import Database

PRIORITY_LEVELS = {1: "Urgent", 2: "High", 3: "Normal", 4: "Low"}


class WorkflowStore:
    # An incident's manually set priority, and whether it is resolved.
    # Rows are keyed by the incident's timestamp, which an edit or revert keeps and a delete removes.
    def __init__(self, database: Database) -> None:
        self._database = database

    # The priority the rules suggest from the AI's assessment; a person can override it.
    @staticmethod
    def suggested_priority(incident: dict) -> int:
        severity = 0 if incident.get("assessment_error") else int(incident.get("severity_estimate") or 0)
        outcome = incident.get("outcome")
        if severity >= 5:
            return 1
        if severity >= 4 or outcome in ("stop_work_review", "systemic_escalation"):
            return 2
        if severity == 3 or outcome in ("pending_review", "photo_review") or incident.get("assessment_error"):
            return 3
        return 4
