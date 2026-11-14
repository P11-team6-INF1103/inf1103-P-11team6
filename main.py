import argparse
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
from models.constants import KEEP_PHOTO
from models.edit_result import EditResult
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

    # Command line entry point: the menu, or --batch FILE to process a JSON file and exit. Returns the exit code.
    @classmethod
    def cli(cls, argv: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(description="Workplace Safety Incident Triage System")
        parser.add_argument("--batch", metavar="FILE", help="process the incidents in FILE (JSON) and exit")
        arguments = parser.parse_args(argv)
        app = cls.create()
        return app.run_batch(arguments.batch) if arguments.batch else (app.run() or 0)

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

    # The names of the fields an edit would change, compared with the saved incident.
    def describe_changes(self, old: Incident, fields: dict, photo: object = KEEP_PHOTO) -> list[str]:
        changed = [name for name in _EDIT_FIELDS if fields.get(name, old.get(name)) != old.get(name)]
        old_path = old.get("photo_saved_path")
        if photo is None and old.get("photo_file") or isinstance(photo, IncidentPhoto) and (not old_path or os.path.splitext(
                os.path.basename(old_path))[0] != photo.fingerprint()):
            changed.append("photo")
        return changed

    # Saves 'new' as the newest version of the incident at a 0-based position, keeping the older versions.
    def _replace(self, index: int, new: Incident, old: Incident) -> EditResult:
        new.follow(old)
        if new.has_photo():
            new.update({"photo_saved_path": self._data.store_photo(new.photo)})
        if not self._data.replace_record(index, new):
            return EditResult("not_saved", previous=old,
                              message="The new version could not be written to disk, so the old one was kept.")
        self.reload_records()
        if not self._data.save_ai_cache(self._cache.export()):
            self._io.display_message("Warning: could not save the AI reply cache.")
        return EditResult("updated", self._records[index], old)

    # Edits the incident at a 0-based position and runs the AI and scoring again. 'fields' holds the new
    # description, location, reporter_role and injury (any left out stay as they are); 'photo' is a new
    # IncidentPhoto, None to remove the photo, or KEEP_PHOTO. Nothing is changed unless the new version succeeds.
    def edit_incident(self, index: int, fields: dict, photo: object = KEEP_PHOTO) -> EditResult:
        if not 0 <= index < len(self._records):
            return EditResult("failed", message="There is no such incident.")
        old = self._records[index]
        if not self.describe_changes(old, fields, photo):
            return EditResult("unchanged", old, old, "Nothing was changed, so the AI was not run again.")
        return self._save_new_version(index, fields, photo)

    # Runs the AI and scoring again on the incident as it is saved, with no change to its details, and saves the
    # result as the newest version (the old one is kept). Unlike an edit it never skips the AI and it ignores the
    # saved AI replies, so the AI really answers again. Use it after a wording-only edit (which keeps the old
    # analysis), after a failed AI step, or to ask for a fresh opinion. Nothing is changed unless it succeeds.
    def reanalyse_incident(self, index: int) -> EditResult:
        if not 0 <= index < len(self._records):
            return EditResult("failed", message="There is no such incident.")
        with self._cache.refresh():
            return self._save_new_version(index, {}, KEEP_PHOTO, reanalysed=True)

    # Builds the new version of the incident at a 0-based position from 'fields' and 'photo', analyses it, and saves it
    # as the newest version. 'reanalysed' marks a version made by reanalyse_incident, for the history list.
    def _save_new_version(self, index: int, fields: dict, photo: object, reanalysed: bool = False) -> EditResult:
        old = self._records[index]
        kept = self._data.load_photo(old) if photo == KEEP_PHOTO else photo
        merged = {name: fields.get(name, old.get(name)) for name in _EDIT_FIELDS}
        new = Incident(merged["description"], merged["location"], merged["reporter_role"], merged["injury"],
                       old.timestamp, kept if isinstance(kept, IncidentPhoto) else None)
        if photo == KEEP_PHOTO and old.get("photo_file"):
            new.update({"photo_file": old.get("photo_file")})  # the saved copy has a different file name
        if photo == KEEP_PHOTO and kept is None and old.get("photo_file"):
            # The saved photo is gone from disk: keep the record of it, but it cannot be analysed again.
            new.update({"photo_file": old.get("photo_file"), "photo_saved_path": old.get("photo_saved_path")})
        if reanalysed:
            new.update({"reanalysed": True})
        # The incident being edited must not count as an earlier incident (Rule 2 and the similar-incidents check).
        others = [record for position, record in enumerate(self._records) if position != index]
        reason = self._analyse(new, others)
        if reason is not None:
            return EditResult("rejected", previous=old, message=reason)
        if new.get("assessment_error"):
            return EditResult("failed", previous=old, message=new.get("assessment_error"))
        return self._replace(index, new, old)

    # Saves new wording for the description, location or reporter role as the newest version without running the AI:
    # the earlier analysis is kept as it was. Injury and photo changes need the AI, so they are refused here.
    def edit_incident_text(self, index: int, fields: dict) -> EditResult:
        if not 0 <= index < len(self._records):
            return EditResult("failed", message="There is no such incident.")
        old = self._records[index]
        if fields.get("injury", old.injury) != old.injury:
            return EditResult("failed", previous=old, message="Changing the injury answer needs the AI to run again.")
        text = {name: fields[name] for name in ("description", "location", "reporter_role")
                if name in fields and fields[name] != old.get(name)}
        if not text:
            return EditResult("unchanged", old, old, "Nothing was changed.")
        merged = {name: text.get(name, old.get(name)) for name in _EDIT_FIELDS}
        new = Incident(merged["description"], merged["location"], merged["reporter_role"], merged["injury"], old.timestamp)
        new.update({key: value for key, value in old.to_dict().items() if key != "history"})
        new.update({"text_only_edit": True})
        return self._replace(index, new, old)

    # Makes an older version the newest one (the older versions stay in the history); no AI is run.
    def revert_incident(self, index: int, version: int) -> EditResult:
        if not 0 <= index < len(self._records):
            return EditResult("failed", message="There is no such incident.")
        old = self._records[index]
        if not 1 <= version <= len(old.history):
            return EditResult("failed", previous=old, message=f"There is no version {version} to go back to.")
        copy = Incident.from_dict({key: value for key, value in old.history[version - 1].items() if key != "version"})
        copy.update({"reverted_from": version})
        return self._replace(index, copy, old)

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

    # Menu option 5: pick an incident, then edit it, re-analyse it, look at its older versions or go back to one of them.
    def edit_saved_incident(self) -> None:
        self.reload_records()
        if not self._records:
            self._io.display_message("No incidents to edit.")
            return
        self._io.display_summary(self._records, interactive=False)
        number = self._io.get_edit_choice(len(self._records))
        if number is None:
            return
        index = number - 1
        while True:
            action = self._io.get_edit_action(self._records[index])
            if action is None:
                return
            if action == "history":
                self._io.display_history(self._records[index])
            elif action == "edit":
                self._edit_by_prompt(index)
            elif action == "reanalyse":
                self._show_edit_result(self.reanalyse_incident(index))
            elif action == "revert":
                version = self._io.get_version_choice(self._records[index])
                if version is not None:
                    self._show_edit_result(self.revert_incident(index, version))

    # Asks for the changes, shows what changed and asks to confirm, then runs the edit.
    def _edit_by_prompt(self, index: int) -> None:
        old = self._records[index]
        draft = self._io.get_incident_edit(old)
        if draft is None:
            self._io.display_message("Cancelled. The incident was not changed.")
            return
        self._show_edit_result(self.edit_incident(index, draft["fields"], draft["photo"]))

    # Tells the user what an edit or revert did; for a new version, shows the report beside the old insight.
    def _show_edit_result(self, result: EditResult) -> None:
        if result.status == "updated":
            self._io.display_edit_result(result.previous, result.incident)
        else:
            self._io.display_message({
                "unchanged": result.message,
                "rejected": f"The edit was rejected, so the old version was kept: {result.message}",
                "failed": f"The AI could not assess the incident, so the old version was kept. {result.message}",
                "not_saved": result.message,
            }[result.status])

    # Menu option 2: reloads the saved incidents and shows the summary.
    def show_summary(self) -> None:
        self._io.display_summary(self.reload_records())

    # Menu option 3: asks for a location and a number of days and shows the incidents found.
    def run_location_query(self) -> None:
        query = self._io.get_location_query(self.locations())
        if query is not None:
            self._io.display_query_results(self.query_location(*query))

    # Menu option 4: shows the incidents, asks which one to delete, confirms, and removes it.
    def delete_incident(self) -> None:
        self.reload_records()
        if not self._records:
            self._io.display_message("No incidents to delete.")
            return
        self._io.display_summary(self._records, interactive=False)
        number = self._io.get_delete_choice(len(self._records))
        if number is None or not self._io.confirm_delete(self._records[number - 1], number):
            return
        if self.remove_incident(number - 1):
            self._io.display_message(f"Incident #{number} deleted.")
        else:
            self._io.display_message("Could not delete the incident: the data file could not be updated.")

    # The interactive menu loop.
    def run(self) -> None:
        self.start_up()
        actions = {"1": self.log_incident, "2": self.show_summary, "3": self.run_location_query,
                   "4": self.delete_incident, "5": self.edit_saved_incident}
        while True:
            choice = self._io.get_menu_choice()
            if choice == "7":
                self._io.display_message("Goodbye.")
                return
            action = actions.get(choice)
            if action is None:
                self._io.display_message("That option is not available yet.")
            else:
                action()

    # Processes every valid incident in a JSON file without prompting; returns 0, or 1 if nothing was valid.
    def run_batch(self, path: str) -> int:
        incidents, problems = self._io.read_incident_file(path)
        for problem in problems:
            self._io.display_message(f"Skipped: {problem}")
        if not incidents:
            self._io.display_message("No valid incidents to process.")
            return 1
        self.start_up()
        for incident in incidents:
            if self.process_incident(incident, interactive=False) is not None:
                self._io.display_outcome(incident)
        self._io.display_summary(self._records, interactive=False)
        return 0


if __name__ == "__main__":
    raise SystemExit(IncidentTriageApp.cli())
