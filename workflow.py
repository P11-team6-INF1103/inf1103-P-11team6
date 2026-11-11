# Daniel
from datetime import datetime

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

    def all(self) -> dict[str, dict]:
        with self._database.connect() as connection:
            rows = connection.execute("SELECT * FROM incident_workflow").fetchall()
        return {row["incident_key"]: dict(row) for row in rows}

    def _upsert(self, key: str, **fields: object) -> None:
        fields["updated_at"] = datetime.now().isoformat()
        columns = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        updates = ", ".join(f"{name} = excluded.{name}" for name in fields)
        with self._database.connect() as connection:
            connection.execute(
                f"INSERT INTO incident_workflow (incident_key, {columns}) VALUES (?, {marks}) "
                f"ON CONFLICT(incident_key) DO UPDATE SET {updates}", (key, *fields.values()))

    # Sets the priority (1 to 4), or None to go back to the suggested one.
    def set_priority(self, key: str, priority: int | None) -> None:
        self._upsert(key, priority=priority)

    def resolve(self, key: str, note: str = "") -> None:
        self._upsert(key, resolved=1, resolved_at=datetime.now().isoformat(),
                     resolution_note=note or None)

    def reopen(self, key: str) -> None:
        self._upsert(key, resolved=0, resolved_at=None, resolution_note=None)

    def delete(self, key: str) -> None:
        with self._database.connect() as connection:
            connection.execute("DELETE FROM incident_workflow WHERE incident_key = ?", (key,))

    # The workflow fields the browser sees for one incident, given its saved row (or None).
    @staticmethod
    def view(incident: dict, row: dict | None) -> dict:
        row = row or {}
        override = row.get("priority")
        priority = override or WorkflowStore.suggested_priority(incident)
        return {
            "priority": priority,
            "priority_name": PRIORITY_LEVELS[priority],
            "priority_source": "manual" if override else "auto",
            "resolved": bool(row.get("resolved")),
            "resolved_at": row.get("resolved_at"),
            "resolution_note": row.get("resolution_note"),
        }
