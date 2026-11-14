# Lennart
import os
import threading
from typing import TYPE_CHECKING

from flask import Flask, jsonify
from flask_cors import CORS

from io_helpers.report_printer import ReportPrinter
from logic_rules.constants import OUTCOME_ACTIONS, SEVERITY_LEVELS
from models.incident import Incident
from models.incident_photo import IncidentPhoto
from web_support.rate_limiter import RateLimiter
from workflow import PRIORITY_LEVELS, WorkflowStore

if TYPE_CHECKING:
    from main import IncidentTriageApp

# Local Vite dev server; on Render set FRONTEND_ORIGINS to the Netlify address.
_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


class WebApi:
    # The advanced feature (GUI): a REST layer for the React dashboard. It holds no business rules:
    # validation is InputValidator's, the pipeline is IncidentTriageApp's, wording is ReportPrinter's.

    # Uses the app it is given (association) and creates its own Flask server and rate limiter (composition).
    # There are no accounts: anyone who can open the dashboard can use every route.
    def __init__(self, app: "IncidentTriageApp", origins: list[str], post_limit: int = 10) -> None:
        self._app = app
        self._workflow = WorkflowStore(app.database)
        self._printer = ReportPrinter(SEVERITY_LEVELS, OUTCOME_ACTIONS)
        self._limiter = RateLimiter(post_limit)
        # One pipeline run at a time: two at once could both append to incidents.json and lose a record.
        self._lock = threading.Lock()
        self.flask = Flask(__name__)
        self.flask.config["MAX_CONTENT_LENGTH"] = IncidentPhoto.MAX_BYTES + 1024 * 1024
        CORS(self.flask, resources={r"/api/*": {"origins": origins}})
        self._add_routes()
        self._app.start_up()

    # Builds the web API the way the server runs it: the app from .env and the settings from the environment.
    @classmethod
    def from_environment(cls) -> "WebApi":
        from main import IncidentTriageApp  # here, not at the top: main.py is wired together after this file
        origins = [o.strip() for o in os.environ.get("FRONTEND_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()]
        return cls(IncidentTriageApp.create(), origins, int(os.environ.get("POST_LIMIT", "10")))

    # Connects each URL to the method that handles it. Each route's owner adds their own line here.
    def _add_routes(self) -> None:
        routes = [
            ("/api/health", "GET", self.health),
            ("/api/meta", "GET", self.meta),
            ("/api/incidents", "GET", self.list_incidents),
            ("/api/incidents/<int:number>", "GET", self.get_incident),
        ]
        for path, method, handler in routes:
            self.flask.add_url_rule(path, f"{method}_{path}", handler, methods=[method])
        self.flask.register_error_handler(413, self._too_large)

    # One saved version (a dict from an incident's history) as the browser sees it: no server paths.
    @staticmethod
    def _version_json(data: dict) -> dict:
        data = dict(data)
        data["has_photo"] = bool(data.pop("photo_saved_path", None))
        return data

    # One incident as the browser sees it: its 1-based number, the plain-English problems, and no server paths.
    # With history=True it also lists the older versions (oldest first).
    # rows are the saved workflow rows (priority, resolved); leave them out to read them fresh.
    def _to_json(self, incident: Incident, number: int, history: bool = False, rows: dict | None = None) -> dict:
        data = incident.to_dict()
        data.pop("history", None)
        has_photo = bool(data.pop("photo_saved_path", None))
        data.update({"id": number, "has_photo": has_photo, "problems": self._printer.friendly_problems(incident),
                     "version": incident.version, "version_count": incident.version})
        rows = self._workflow.all() if rows is None else rows
        data.update(WorkflowStore.view(data, rows.get(incident.timestamp)))
        if history:
            data["history"] = [self._version_json(v) for v in incident.history]
        return data

    # The incident with a 1-based number, or None if there is no such incident.
    def _find(self, number: int) -> Incident | None:
        records = self._app.records
        return records[number - 1] if 1 <= number <= len(records) else None

    @staticmethod
    def _too_large(_error: Exception) -> tuple:
        return jsonify({"errors": ["The photo is larger than 5 MB. Please use a smaller photo."]}), 413

    def health(self) -> tuple:
        return jsonify({"status": "ok", "incidents": len(self._app.records)}), 200

    # Labels and meanings, so the dashboard uses the same wording as the terminal app.
    def meta(self) -> tuple:
        return jsonify({
            "severity_levels": {str(k): {"name": n, "meaning": m} for k, (n, m) in SEVERITY_LEVELS.items()},
            "outcome_actions": OUTCOME_ACTIONS,
            "outcome_names": ReportPrinter.OUTCOME_NAMES,
            "hazard_names": ReportPrinter.HAZARD_NAMES,
            "priority_levels": {str(k): v for k, v in PRIORITY_LEVELS.items()},
        }), 200

    def list_incidents(self) -> tuple:
        with self._lock:
            records = self._app.reload_records()
        rows = self._workflow.all()
        return jsonify([self._to_json(r, n, rows=rows) for n, r in enumerate(records, start=1)]), 200

    def get_incident(self, number: int) -> tuple:
        incident = self._find(number)
        if incident is None:
            return jsonify({"errors": [f"No incident #{number}."]}), 404
        return jsonify(self._to_json(incident, number, history=True)), 200
