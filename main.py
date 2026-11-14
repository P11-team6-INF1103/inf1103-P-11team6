import logging
import os

from dotenv import load_dotenv

from ai_clients.gemini_client import GeminiClient
from ai_clients.groq_search_client import GroqSearchClient
from ai_clients.response_cache import ResponseCache
from ai_clients.weather_client import WeatherClient
from ai_manager import AIManager
from data_manager import DataManager
from database import Database
from db.database_unavailable import DatabaseUnavailable
from io_manager import IOManager
from logic_manager import LogicManager
from logic_rules.constants import OUTCOME_ACTIONS, SEVERITY_LEVELS
from models.incident import Incident
from models.incident_photo import IncidentPhoto
from site_plan.site_plan import SitePlan

_EDIT_FIELDS = ("description", "location", "reporter_role", "injury")


class IncidentTriageApp:
    # Holds the four managers it is given and runs the pipeline between them (association).
    def __init__(self, io: IOManager, ai: AIManager, logic: LogicManager, data: DataManager,
                 cache: ResponseCache, notice: str | None = None) -> None:
        self._io = io
        self._ai = ai
        self._logic = logic
        self._data = data
        self._cache = cache
        self._notice = notice
        self._records: list[Incident] = []

    # The incidents loaded so far, in saved order (a copy, so callers cannot change the app's list).
    @property
    def records(self) -> list[Incident]:
        return list(self._records)

    # (bytes, MIME type) of a photo kept in the database, or None.
    def read_photo(self, reference: str) -> tuple[bytes, str] | None:
        return self._data.read_photo(reference)

    @property
    def database(self) -> Database:
        return self._data.database

    # Reads the saved incidents again from disk.
    def reload_records(self) -> list[Incident]:
        self._records = self._data.load_records()
        return self.records

    # Incidents at one location in the last N days, newest first.
    def query_location(self, location: str, days: int) -> list[Incident]:
        return self._data.query_by_location(location, days, records=self._records)

    # Saved locations with their incident counts.
    def locations(self) -> list[tuple[str, int]]:
        return self._data.list_locations(self._records)

    # Deletes the incident at a 0-based position and reloads; returns False if it could not be removed.
    def remove_incident(self, index: int) -> bool:
        removed = self._data.delete_record(index)
        self.reload_records()
        return removed

    # The saved site plan for the site map, or None.
    def site_plan(self) -> SitePlan | None:
        return self._data.load_site_plan()

    # Reads an uploaded plan image into a draft plan with the AI; the draft is not saved. Raises SitePlanError.
    def read_site_plan(self, image: IncidentPhoto, width_m: float, aspect: float, name: str = "") -> SitePlan:
        try:
            return self._ai.read_site_plan(image, width_m, aspect, name)
        finally:
            self._data.save_ai_cache(self._cache.export())

    def save_site_plan(self, plan: SitePlan) -> bool:
        return self._data.save_site_plan(plan)

    def delete_site_plan(self) -> bool:
        return self._data.delete_site_plan()

    # Chooses where everything is kept. DATABASE_URL (a Postgres URL or a SQLite file path) means a database; without
    # it, or if the database cannot be opened, the app keeps working with local files in the data folder.
    # Returns the data manager and a message for the user when it is not using the database they asked for.
    @staticmethod
    def open_storage(url: str | None) -> tuple[DataManager, str | None]:
        if not url:
            return DataManager(), f"DATABASE_URL is not set, so incidents are saved in local files ({DataManager.default_folder()})."
        try:
            return DataManager(shared_database=Database(url)), None
        except DatabaseUnavailable as error:
            return DataManager(), (f"Warning: {error}. Saving to local files ({DataManager.default_folder()}) instead; "
                                   "check DATABASE_URL.")

    # Builds the real app: API keys from .env, saved AI replies from storage, logging to the console.
    @classmethod
    def create(cls) -> "IncidentTriageApp":
        load_dotenv()
        data, notice = cls.open_storage(os.environ.get("DATABASE_URL"))
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        cache = ResponseCache(data.load_ai_cache())
        ai = AIManager(GeminiClient(cache), GroqSearchClient(cache), WeatherClient(cache), OUTCOME_ACTIONS)
        return cls(IOManager(SEVERITY_LEVELS, OUTCOME_ACTIONS), ai, LogicManager(LogicManager.default_rules()),
                   data, cache, notice)

    # Tells the user where data is kept if that is not the database they asked for, warns about a corrupt incidents file.
    def start_up(self) -> None:
        if self._notice:
            self._io.display_message(self._notice)
        problem = self._data.check_records_file()
        if problem:
            self._io.display_message(f"Warning: {problem}. Starting with no saved incidents.")
        self._records = self._data.load_records()
        self._io.display_message(f"Loaded {len(self._records)} saved incident(s).")

    # Saves the incident (asking to retry if allowed) and the AI reply cache.
    def _save(self, incident: Incident, interactive: bool) -> None:
        if incident.has_photo():
            incident.update({"photo_saved_path": self._data.store_photo(incident.photo)})
        saved = self._data.save_record(incident)
        while not saved and interactive and self._io.ask_retry_save():
            saved = self._data.save_record(incident)
        if not saved:
            self._io.display_message("Warning: could not save this incident to disk.")
        self._records.append(incident)
        if not self._data.save_ai_cache(self._cache.export()):
            self._io.display_message("Warning: could not save the AI reply cache.")

    # The AI and rule steps for one incident, without saving; 'records' is what counts as earlier incidents.
    # Returns the reason it was rejected, or None if it was accepted and scored.
    def _analyse(self, incident: Incident, records: list[Incident]) -> str | None:
        self._logic.derive_context(incident)
        with self._io.show_loading("AI is analysing the incident"):
            self._ai.extract_hazards(incident)
            accepted, reason = self._logic.screen_incident(incident)
            if accepted:
                self._ai.gather_evidence(incident, records)
                self._logic.apply_site_conditions(incident)
                self._logic.apply_photo_evidence(incident)
                self._ai.write_review(incident)
        if not accepted:
            incident.update({"reject_reason": reason})
            return reason
        history = self._data.query_by_location(incident.location, 30, as_of=incident.timestamp, records=records)
        self._logic.assess_severity(incident, history)
        self._logic.decide_outcome(incident, history)
        return None

    # The whole pipeline for one incident: AI, rules, outcome, save; returns None if the AI rejected it.
    def process_incident(self, incident: Incident, interactive: bool = True) -> Incident | None:
        reason = self._analyse(incident, self._records)
        if reason is not None:
            self._io.display_message("Incident rejected: " + reason)
            return None
        self._save(incident, interactive)
        return incident

    # Menu option 1: asks for an incident, processes it and shows the report; offers to re-enter a rejected one.
    def log_incident(self) -> None:
        while True:
            incident = self._io.get_incident_input()
            if incident is None:
                self._io.display_message("Cancelled. Returning to the main menu.")
                return
            if self.process_incident(incident) is not None:
                self._io.display_outcome(incident)
                return
            if not self._io.ask_try_again():
                return
