# Lennart
import io
import os
import re
import threading
from typing import TYPE_CHECKING

from flask import Flask, Response, jsonify, request, send_file
from flask_cors import CORS

from io_helpers.input_validator import InputValidator
from io_helpers.report_printer import ReportPrinter
from logic_rules.constants import OUTCOME_ACTIONS, SEVERITY_LEVELS
from models.constants import KEEP_PHOTO
from models.incident import Incident
from models.incident_photo import IncidentPhoto
from models.photo_error import PhotoError
from search_engine import IncidentSearch
from trend_report import TrendReport
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
        self._search = IncidentSearch(ReportPrinter.HAZARD_NAMES)
        self._summary = TrendReport.standard(ReportPrinter.HAZARD_NAMES)
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
            ("/api/incidents/search", "GET", self.search_incidents),
            ("/api/reports/summary", "GET", self.summary_report),
            ("/api/incidents/<int:number>/priority", "PUT", self.set_priority),
            ("/api/incidents/<int:number>/resolve", "POST", self.resolve_incident),
            ("/api/incidents/<int:number>/reopen", "POST", self.reopen_incident),
            ("/api/incidents/<int:number>", "GET", self.get_incident),
            ("/api/locations", "GET", self.list_locations),
            ("/api/locations/query", "GET", self.query_location),
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

    # Ren Xiang
    # The form fields from a multipart upload (with an optional 'photo' file) or a JSON body.
    @staticmethod
    def _read_form() -> tuple[dict, object]:
        if request.is_json:
            body = request.get_json(silent=True)
            return (body if isinstance(body, dict) else {}), None
        return request.form.to_dict(), request.files.get("photo")

    # Runs one incident through the whole pipeline. 422 with 'errors' for a bad form, 422 with 'rejected'
    # when the AI says it is not a safety incident, 201 with the saved incident otherwise.
    def create_incident(self) -> tuple:
        form, upload = self._read_form()
        fields, problems = InputValidator.validate_fields(form)
        photo = None
        if upload is not None and upload.filename:
            try:
                photo = IncidentPhoto.from_bytes(upload.filename, upload.read())
            except PhotoError as error:
                problems.append(f"photo ({error})")
        if problems:
            return jsonify({"errors": problems}), 422
        client = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
        if self._limiter.too_many(client):
            return jsonify({"errors": ["Too many incidents from this connection. Try again in a few minutes."]}), 429
        incident = Incident(**fields, photo=photo)
        with self._lock:
            result = self._app.process_incident(incident, interactive=False)
            number = len(self._app.records)
        if result is None:
            return jsonify({"rejected": incident.get("reject_reason")}), 422
        return jsonify(self._to_json(result, number, history=True)), 201

    # Edits an incident and runs the AI again: send any of description, location, reporter_role, injury,
    # a new 'photo' file, or remove_photo=true; fields left out keep their value. 200 with the new version
    # (history[-1] is the version it replaced) or status 'unchanged'; rerun_ai=false saves only new wording
    # (description, location, role) without the AI and keeps the earlier analysis; 422 for a bad form or an AI rejection;
    # 502 if the AI could not assess it, in which case the old version stays current.
    def edit_incident(self, number: int) -> tuple:
        old = self._find(number)
        if old is None:
            return jsonify({"errors": [f"No incident #{number}."]}), 404
        form, upload = self._read_form()
        current = {"description": old.description, "location": old.location,
                   "reporter_role": old.get("reporter_role"), "injury": old.injury}
        fields, problems = InputValidator.validate_fields({**current, **form, "timestamp": old.timestamp})
        photo: object = KEEP_PHOTO
        if upload is not None and upload.filename:
            try:
                photo = IncidentPhoto.from_bytes(upload.filename, upload.read())
            except PhotoError as error:
                problems.append(f"photo ({error})")
        elif str(form.get("remove_photo", "")).lower() in ("true", "1", "yes"):
            photo = None
        if problems:
            return jsonify({"errors": problems}), 422
        fields.pop("timestamp")
        if str(form.get("rerun_ai", "true")).lower() in ("false", "0", "no"):
            if photo is not KEEP_PHOTO:
                return jsonify({"errors": ["Changing the photo needs the AI to run again."]}), 422
            with self._lock:
                result = self._app.edit_incident_text(number - 1, fields)
            return self._edit_response(result, number)
        if not self._app.describe_changes(old, fields, photo):
            return jsonify({"status": "unchanged", **self._to_json(old, number, history=True)}), 200
        client = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
        if self._limiter.too_many(client):
            return jsonify({"errors": ["Too many incidents from this connection. Try again in a few minutes."]}), 429
        with self._lock:
            result = self._app.edit_incident(number - 1, fields, photo)
        return self._edit_response(result, number)

    # Turns an EditResult into the HTTP answer.
    def _edit_response(self, result: object, number: int) -> tuple:
        if result.status == "updated":
            return jsonify({"status": "updated", **self._to_json(result.incident, number, history=True)}), 200
        if result.status == "unchanged":
            return jsonify({"status": "unchanged", **self._to_json(result.incident, number, history=True)}), 200
        if result.status == "rejected":
            return jsonify({"rejected": result.message}), 422
        if result.status == "failed" and result.previous is None:
            return jsonify({"errors": [result.message]}), 404
        return jsonify({"errors": [result.message], "kept_version": result.previous.version}), \
            (400 if result.status == "failed" and "no version" in str(result.message) else 502)

    # Copies an older version in as the newest one. Body: {"version": 1}. No AI call.
    def revert_incident(self, number: int) -> tuple:
        if self._find(number) is None:
            return jsonify({"errors": [f"No incident #{number}."]}), 404
        body = request.get_json(silent=True)
        version = body.get("version") if isinstance(body, dict) else None
        if not isinstance(version, int) or isinstance(version, bool):
            return jsonify({"errors": ["version must be a whole number."]}), 422
        with self._lock:
            result = self._app.revert_incident(number - 1, version)
        return self._edit_response(result, number)

    def delete_incident(self, number: int) -> tuple:
        with self._lock:
            incident = self._find(number)
            if incident is None:
                return jsonify({"errors": [f"No incident #{number}."]}), 404
            if not self._app.remove_incident(number - 1):
                return jsonify({"errors": ["The data file could not be updated."]}), 500
            self._workflow.delete(incident.timestamp)
        return jsonify({"deleted": number}), 200

    # The saved photo of an incident (or of an older version with ?version=N), if it is still on the server's disk.
    def get_photo(self, number: int) -> object:
        incident = self._find(number)
        path = incident.get("photo_saved_path") if incident else None
        version = request.args.get("version", "")
        if incident and version.isdigit() and 1 <= int(version) <= len(incident.history):
            path = incident.history[int(version) - 1].get("photo_saved_path")
        stored = self._app.read_photo(path) if path else None
        if stored:
            return send_file(io.BytesIO(stored[0]), mimetype=stored[1])
        if not path or not os.path.isfile(path):
            return jsonify({"errors": ["No photo saved for this incident."]}), 404
        return send_file(path)
    
    # Daniel
    def list_locations(self) -> tuple:
        return jsonify([{"location": name, "count": count} for name, count in self._app.locations()]), 200

    # Same as terminal menu option 3: incidents at a location in the last N days.
    def query_location(self) -> tuple:
        location = InputValidator.sanitise(request.args.get("location", ""))
        error = InputValidator.check_location(location)
        days = request.args.get("days", "30")
        if error or not (days.isdigit() and int(days) > 0):
            return jsonify({"errors": [error or "Days must be a whole number, 1 or more."]}), 422
        records = self._app.records
        found = self._app.query_location(location, int(days))
        rows = self._workflow.all()
        return jsonify([self._to_json(r, records.index(r) + 1, rows=rows) for r in found]), 200

    # Daniel
    # Ranked search. Query string: q (words, "phrases", #number) and the filters severity_min, hazard, outcome,
    # location, priority, status (open or resolved), date_from, date_to (YYYY-MM-DD), has_photo.
    def search_incidents(self) -> tuple:
        args = request.args
        filters: dict = {key: args.get(key, "").strip() for key in ("hazard", "outcome", "location", "date_from", "date_to")}
        filters["status"] = args.get("status", "") if args.get("status") in ("open", "resolved") else ""
        filters["has_photo"] = args.get("has_photo", "").lower() in ("true", "1", "yes")
        problems = []
        for key, low, high in (("severity_min", 1, 5), ("priority", 1, 4)):
            raw = args.get(key, "")
            if raw == "":
                filters[key] = None
            elif raw.isdigit() and low <= int(raw) <= high:
                filters[key] = int(raw)
            else:
                problems.append(f"{key} must be a whole number from {low} to {high}.")
        for key in ("date_from", "date_to"):
            if filters[key] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", filters[key]):
                problems.append(f"{key} must look like 2026-10-31.")
        if problems:
            return jsonify({"errors": problems}), 422
        with self._lock:
            records = self._app.reload_records()
        rows = self._workflow.all()
        everything = [self._to_json(r, n, rows=rows) for n, r in enumerate(records, start=1)]
        results = self._search.search(everything, args.get("q", ""), filters)
        return jsonify({"query": args.get("q", ""), "count": len(results), "total": len(everything),
                        "results": results}), 200

    # The trend and summary report: ?days=7 (1 to 180) compared with the same number of days before, and
    # ?format=csv to download it as a spreadsheet instead of JSON.
    def summary_report(self) -> tuple:
        raw = request.args.get("days", "7")
        if not raw.isdigit() or not TrendReport.MIN_DAYS <= int(raw) <= TrendReport.MAX_DAYS:
            low, high = TrendReport.MIN_DAYS, TrendReport.MAX_DAYS
            return jsonify({"errors": [f"days must be a whole number from {low} to {high}."]}), 422
        with self._lock:
            records = self._app.reload_records()
        rows = self._workflow.all()
        report = self._summary.build([self._to_json(r, n, rows=rows) for n, r in enumerate(records, start=1)], int(raw))
        if request.args.get("format") == "csv":
            return Response(self._summary.to_csv(report), 200, {
                "Content-Type": "text/csv; charset=utf-8",
                "Content-Disposition": f'attachment; filename="incident_summary_{raw}_days.csv"'})
        return jsonify(report), 200

    # Set the priority (1 Urgent to 4 Low), or null to go back to the suggested one. Body: {"priority": 2}.
    def set_priority(self, number: int) -> tuple:
        incident = self._find(number)
        if incident is None:
            return jsonify({"errors": [f"No incident #{number}."]}), 404
        body = request.get_json(silent=True)
        priority = body.get("priority") if isinstance(body, dict) else "bad"
        if priority is not None and (not isinstance(priority, int) or isinstance(priority, bool)
                                     or priority not in PRIORITY_LEVELS):
            return jsonify({"errors": ["priority must be 1 (Urgent), 2 (High), 3 (Normal), 4 (Low) or null."]}), 422
        self._workflow.set_priority(incident.timestamp, priority)
        return jsonify(self._to_json(incident, number, history=True)), 200

    # Mark an incident resolved, with an optional note. Body: {"note": "Guard rail fixed"}.
    def resolve_incident(self, number: int) -> tuple:
        incident = self._find(number)
        if incident is None:
            return jsonify({"errors": [f"No incident #{number}."]}), 404
        body = request.get_json(silent=True)
        note = InputValidator.sanitise(str(body.get("note", ""))) if isinstance(body, dict) else ""
        if len(note) > 500:
            return jsonify({"errors": ["The note must be 500 characters or fewer."]}), 422
        self._workflow.resolve(incident.timestamp, note)
        return jsonify(self._to_json(incident, number, history=True)), 200

    def reopen_incident(self, number: int) -> tuple:
        incident = self._find(number)
        if incident is None:
            return jsonify({"errors": [f"No incident #{number}."]}), 404
        self._workflow.reopen(incident.timestamp)
        return jsonify(self._to_json(incident, number, history=True)), 200


# Used by gunicorn on Render: gunicorn "web_api:create_app()". gunicorn needs a plain function here, so it only hands over.
def create_app() -> Flask:
    return WebApi.from_environment().flask


if __name__ == "__main__":
    create_app().run(port=int(os.environ.get("PORT", "8000")), debug=False)
