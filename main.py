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
