import json
import os
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from io_helpers.draft_command import DraftCommand
from io_helpers.input_validator import InputValidator
from io_helpers.report_printer import ReportPrinter
from models.constants import KEEP_PHOTO
from models.incident import Incident
from models.incident_photo import IncidentPhoto
from models.photo_error import PhotoError


# Daniel
class IOManager:
    _SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    # The questions of an incident form, in the order they are asked.
    _DRAFT_FIELDS = ("description", "location", "role", "injury", "photo")
    _DRAFT_LABELS = {"description": "What happened", "location": "Location", "role": "Your role",
                     "injury": "Anyone injured", "photo": "Photo"}
    _BACK = object()

    # Creates and owns its report printer (composition).
    def __init__(self, severity_levels: dict, outcome_actions: dict) -> None:
        self._printer = ReportPrinter(severity_levels, outcome_actions)
        self._validator = InputValidator()
        self._accept_commands = False

    # Reads one answer; while an incident form is open, /undo and /redo are raised as DraftCommand instead.
    def _read(self, prompt: str) -> str:
        answer = input(prompt)
        command = answer.strip().lower()
        if self._accept_commands and command in ("/undo", "/redo"):
            raise DraftCommand(command[1:])
        return answer

    # Prints one line of text; the only way other classes show messages.
    def display_message(self, text: str) -> None:
        print(text)

    # Shows a spinner in a background thread while the with-block runs; does nothing if output is not a terminal.
    @contextmanager
    def show_loading(self, message: str = "AI is thinking") -> Iterator[None]:
        if not sys.stdout.isatty():
            yield
            return
        stop = threading.Event()

        def animate() -> None:
            frame = 0
            while not stop.is_set():
                sys.stdout.write(f"\r{self._SPINNER_FRAMES[frame % 10]} {message}{'.' * (frame // 3 % 4):<3}")
                sys.stdout.flush()
                frame += 1
                stop.wait(0.1)

        thread = threading.Thread(target=animate, daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join()
            sys.stdout.write("\r" + " " * (len(message) + 6) + "\r")
            sys.stdout.flush()

    # Asks until the sanitised answer passes the check; pressing Enter twice on a blank answer returns None.
    def _ask_valid(self, prompt: str, check: Callable[[str], str | None], back: str = "the main menu") -> str | None:
        blank_before = False
        while True:
            answer = self._read(prompt)
            if answer.strip() == "":
                if blank_before:
                    return None
                blank_before = True
                print(f"Nothing entered. Type your answer, or press Enter again to go back to {back}.")
                prompt = "Try again: "
                continue
            blank_before = False
            value = self._validator.sanitise(answer)
            error = check(value)
            if error is None:
                return value
            print("Error: " + error)
            prompt = "Try again: "

    # Asks until the answer is yes or no; returns None if allow_back is set and Enter is pressed twice.
    def _ask_yes_no(self, prompt: str, allow_back: bool = False) -> bool | None:
        answer = self._read(prompt).strip().lower()
        blank_before = False
        while answer not in ("yes", "no", "y", "n"):
            if allow_back and answer == "":
                if blank_before:
                    return None
                blank_before = True
                answer = self._read("Please answer yes or no, or press Enter again to go back: ").strip().lower()
            else:
                blank_before = False
                answer = self._read("Please answer yes or no: ").strip().lower()
        return answer in ("yes", "y")

    # New in Part 2: asks for an optional photo path until a usable photo is given or Enter skips it.
    # When editing, 'current' is the photo's name: Enter keeps it and 'none' removes it (returns None).
    def ask_for_photo(self, current: str | None = None) -> IncidentPhoto | str | None:
        print("Attach a photo of the scene? Type or drag in the file path (.png .jpg .jpeg .webp, max 5 MB).")
        if current:
            print(f"Current photo: {current}. Press Enter to keep it, or type 'none' to remove it.")
        prompt = "Photo path (or press Enter to keep it): " if current else "Photo path (or press Enter to skip): "
        while True:
            answer = self._read(prompt)
            if answer.strip() == "":
                return KEEP_PHOTO if current else None
            if current and answer.strip().lower() == "none":
                return None
            try:
                photo = IncidentPhoto.from_file(self._validator.clean_path(answer))
            except PhotoError as error:
                print(f"Error: {error}")
                prompt = "Try another path (or press Enter to skip): "
                continue
            print(f"Photo attached: {photo.file_name}")
            return photo

    # Shows the main menu and returns '1' to '7'; Ctrl+C or closed input returns '7'.
    def get_menu_choice(self) -> str:
        print("\n=== Workplace Safety Incident Triage System ===")
        print("1. Log a new incident (with optional photo)")
        print("2. View summary of all incidents")
        print("3. Query incidents by location")
        print("4. Delete an incident")
        print("5. Edit or re-analyse an incident")
        print("6. Export incidents to a file (CSV or JSON)")
        print("7. Exit")
        try:
            choice = input("Choose an option (1-7): ").strip()
            while choice not in ("1", "2", "3", "4", "5", "6", "7"):
                choice = input("Invalid choice. Please enter 1, 2, 3, 4, 5, 6 or 7: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return "7"
        return choice

    # Asks one question of the incident form; returns the answer, or _BACK if the user gave up on it.
    def _ask_field(self, field: str, in_review: bool, keep_photo: str | None = None) -> object:
        back = "the review screen" if in_review else "the main menu"
        v = self._validator
        if field == "photo":
            return self.ask_for_photo(keep_photo)
        if field == "injury":
            answer = self._ask_yes_no("Was anyone injured? (yes/no): ", allow_back=True)
        else:
            prompt, check = {
                "description": ("Describe what happened: ", v.check_description),
                "location": ("Location (e.g. 'Site A - Block 3'): ", v.check_location),
                "role": ("Your role (e.g. 'site_supervisor'): ", v.check_role),
            }[field]
            answer = self._ask_valid(prompt, check, back)
        return self._BACK if answer is None else answer

    # Text for one answer on the review screen.
    @staticmethod
    def _draft_text(field: str, value: object, original: dict | None) -> str:
        if field == "injury":
            return "Yes" if value else "No"
        if field == "photo":
            if value == KEEP_PHOTO:
                return (original or {}).get("photo") or "none"
            if isinstance(value, IncidentPhoto):
                return value.file_name
            return value if isinstance(value, str) and value else "none"
        return str(value)

    # Shows every answer, and for an edit what each changed field used to be.
    def _show_draft(self, answers: dict, original: dict | None) -> None:
        print("\n--- Review ---" if original is None else "\n--- Review your changes ---")
        for number, field in enumerate(self._DRAFT_FIELDS, start=1):
            text = self._draft_text(field, answers[field], original)
            was = ""
            if original is not None:
                before = self._draft_text(field, original[field], original)
                if before != text or (field == "photo" and isinstance(answers[field], IncidentPhoto)):
                    was = f"   (was: {before})"
            print(f"  {number}. {self._DRAFT_LABELS[field]:<15}{text}{was}")

    # Asks whether to send the form, change an answer or throw it away.
    def _ask_review(self, answers: dict, original: dict | None) -> str:
        self._show_draft(answers, original)
        if original is not None:
            print("Nothing is changed or sent to the AI until you choose 'send'.")
            question = "Save these changes and run the AI again? (send/edit/cancel): "
        else:
            print("Nothing is sent to the AI or saved until you choose 'send'.")
            question = "Send this report? (send/edit/cancel): "
        while True:
            choice = self._read(question).strip().lower()
            if choice in ("send", "s", "yes", "y"):
                return "send"
            if choice in ("edit", "e"):
                return "edit"
            if choice in ("cancel", "c", "no", "n"):
                return "cancel"
            question = "Please type send, edit or cancel: "

    # Applies /undo (take back the last answer) or /redo (put it back).
    def _apply_command(self, name: str, answers: dict, redo: list) -> None:
        if name == "undo":
            if not answers:
                print("Nothing to undo.")
                return
            field, value = answers.popitem()
            redo.append((field, value))
            print(f"Undid '{self._DRAFT_LABELS[field]}'. You can answer it again, or type /redo to put it back.")
        else:
            if not redo:
                print("Nothing to redo.")
                return
            field, value = redo.pop()
            answers[field] = value
            print(f"Restored '{self._DRAFT_LABELS[field]}': {self._draft_text(field, value, None)}")

    # Fills the form one question at a time, then shows the review screen; returns the answers, or None to cancel.
    def _collect_draft(self, answers: dict, original: dict | None = None) -> dict | None:
        redo: list = []
        keep_photo = (original or {}).get("photo")
        while True:
            try:
                if len(answers) < len(self._DRAFT_FIELDS):
                    field = self._DRAFT_FIELDS[len(answers)]
                    value = self._ask_field(field, False, keep_photo)
                    if value is self._BACK:
                        return None
                    answers[field] = value
                    redo.clear()
                    continue
                choice = self._ask_review(answers, original)
                if choice == "send":
                    return answers
                if choice == "cancel":
                    return None
                number = self._ask_number("Which answer do you want to change? (1-5, or press Enter to go back): ", 5)
                if number is None:
                    continue
                field = self._DRAFT_FIELDS[number - 1]
                value = self._ask_field(field, True, keep_photo)
                if value is not self._BACK:
                    answers[field] = value
                    redo.clear()
            except DraftCommand as command:
                self._apply_command(command.name, answers, redo)

    # Asks for the incident details and an optional photo, then a review screen to send, edit or cancel.
    # /undo and /redo work at every prompt. Returns None if the user cancels.
    def get_incident_input(self) -> Incident | None:
        print("\n--- Log a New Incident ---")
        print("(Type /undo to take back your last answer, /redo to put it back.")
        print(" Press Enter twice on a blank answer to return to the main menu.)")
        self._accept_commands = True
        try:
            answers = self._collect_draft({})
        finally:
            self._accept_commands = False
        if answers is None:
            return None
        return Incident(answers["description"], answers["location"], answers["role"], answers["injury"],
                        photo=answers["photo"])

    # Shows the saved answers of an incident and lets the user change them; returns
    # {'fields': {...new typed fields}, 'photo': IncidentPhoto | None | KEEP_PHOTO}, or None to cancel.
    def get_incident_edit(self, incident: Incident) -> dict | None:
        original = {"description": incident.description, "location": incident.location,
                    "role": incident.get("reporter_role"), "injury": incident.injury,
                    "photo": incident.get("photo_file")}
        print(f"\n--- Edit Incident (version {incident.version}) ---")
        print("(Choose 'edit' to change an answer. /undo and /redo work here too.)")
        self._accept_commands = True
        try:
            answers = self._collect_draft({**original, "photo": KEEP_PHOTO}, original)
        finally:
            self._accept_commands = False
        if answers is None:
            return None
        return {"fields": {"description": answers["description"], "location": answers["location"],
                           "reporter_role": answers["role"], "injury": answers["injury"]},
                "photo": answers["photo"]}

    # Asks whether to enter a rejected incident again.
    def ask_try_again(self) -> bool:
        return self._ask_yes_no("Enter the incident again? (yes/no): ")

    # Warns that the incident is not on disk and asks whether to try saving again.
    def ask_retry_save(self) -> bool:
        print("\n" + "!" * 60)
        print("  INCIDENT NOT SAVED: it could not be written to disk and")
        print("  will be lost when you exit the program.")
        print("!" * 60)
        return self._ask_yes_no("Try saving again? (yes/no): ")

    # Asks for a number from 1 to count; returns None if the user presses Enter, Ctrl+C or closes the input.
    def _ask_number(self, prompt: str, count: int) -> int | None:
        while True:
            try:
                choice = self._read(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return None
            if choice == "":
                return None
            if choice.isdigit() and 1 <= int(choice) <= count:
                return int(choice)
            print(f"Please enter a number from 1 to {count}.")

    # Asks which incident number to delete.
    def get_delete_choice(self, count: int) -> int | None:
        return self._ask_number(f"Enter the incident # to delete (1-{count}, or press Enter to go back): ", count)

    # Shows the incident about to be deleted and asks the user to confirm.
    def confirm_delete(self, incident: Incident, number: int) -> bool:
        print(f"\nIncident #{number}: {incident.location} - {incident.description}")
        return self._ask_yes_no("Delete this incident permanently? (yes/no): ")

    # Asks for a location (or 'list') and a number of days; returns (location, days), or None to go back.
    def get_location_query(self, known_locations: list[tuple[str, int]]) -> tuple[str, int] | None:
        prompt = "Location to search, type 'list' to pick from saved locations (or press Enter to go back): "
        while True:
            location = self._validator.sanitise(input(prompt))
            if location == "":
                return None
            if location.lower() == "list":
                if not known_locations:
                    print("No incidents have been saved yet, so there are no locations to list.")
                    return None
                for number, (name, count) in enumerate(known_locations, start=1):
                    print(f"  {number}. {name} ({count} incident{'s' if count != 1 else ''})")
                picked = self._ask_number("Choose a number (or press Enter to go back): ", len(known_locations))
                if picked is None:
                    return None
                location = known_locations[picked - 1][0]
            error = self._validator.check_location(location)
            if error is None:
                break
            print("Error: " + error)
            prompt = "Try again (or press Enter to go back to the menu): "
        days = input("How many days back? (Enter for 30): ").strip()
        while days != "" and not (days.isdigit() and int(days) > 0):
            days = input("Please enter a whole number of days, 1 or more: ").strip()
        return location, int(days) if days else 30

    # Prints the incidents found by a location query.
    def display_query_results(self, results: list[Incident]) -> None:
        if not results:
            print("No matching incidents found.")
            return
        print(f"{len(results)} matching incident(s):")
        for incident in results:
            outcome = incident.get("outcome")
            print(f"[{self._printer.format_time(incident.timestamp)}] {incident.location} -> "
                  f"{self._printer.OUTCOME_NAMES.get(outcome, outcome)}")

    # Asks which incident number to edit.
    def get_edit_choice(self, count: int) -> int | None:
        return self._ask_number(f"Enter the incident # to edit (1-{count}, or press Enter to go back): ", count)

    # Asks what to do with the chosen incident; returns 'edit', 'reanalyse', 'history', 'revert' or None to go back.
    def get_edit_action(self, incident: Incident) -> str | None:
        older = len(incident.history)
        print(f"\n{incident.location} - {incident.description}")
        print(f"This is version {incident.version}" + (f" ({older} older version(s) kept)." if older else "."))
        options = {"1": ("edit", "Edit the details and run the AI again"),
                   "2": ("reanalyse", "Re-analyse: ask the AI again with the same details (no retyping)")}
        if older:
            options["3"] = ("history", "View the version history")
            options["4"] = ("revert", "Go back to an older version")
        for key, (_, text) in options.items():
            print(f"  {key}. {text}")
        try:
            choice = input("Choose (or press Enter to go back): ").strip()
            while choice != "" and choice not in options:
                choice = input(f"Please choose {', '.join(options)} (or press Enter to go back): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        return options[choice][0] if choice else None

    # Prints the version list of an incident.
    def display_history(self, incident: Incident) -> None:
        self._printer.print_history(incident)

    # Asks which older version to go back to and confirms; returns its number, or None.
    def get_version_choice(self, incident: Incident) -> int | None:
        self._printer.print_history(incident)
        count = len(incident.history)
        number = self._ask_number(f"Go back to which version? (1-{count}, or press Enter to go back): ", count)
        if number is None:
            return None
        if not self._ask_yes_no(f"Copy version {number} in as the newest version? Nothing is deleted. (yes/no): "):
            return None
        return number

# Lennart
    # Asks which export format and file name to use; 'defaults' maps each format name to its usual file name. Returns
    # (format, path), or None to go back. An existing file is only replaced after a yes.
    def get_export_choice(self, defaults: dict[str, str]) -> tuple[str, str] | None:
        names = list(defaults)
        print("\nExport every saved incident to a file:")
        for number, name in enumerate(names, start=1):
            print(f"  {number}. {name.upper()}")
        number = self._ask_number(f"Export as (1-{len(names)}, or press Enter to go back): ", len(names))
        if number is None:
            return None
        name = names[number - 1]
        path = self._read(f"File name (press Enter for {defaults[name]}): ").strip() or defaults[name]
        if os.path.exists(path) and not self._ask_yes_no(f"{path} already exists. Replace it? (yes/no): "):
            return None
        return name, path

# Daniel
    # Prints what changed against the previous version, then the new full report.
    def display_edit_result(self, previous: Incident, current: Incident) -> None:
        self._printer.print_incident(current)
        self._printer.print_comparison(previous, current)
        print()

    # Prints the full report for one processed incident.
    def display_outcome(self, incident: Incident) -> None:
        self._printer.print_incident(incident)

    # Prints the summary and severity guide; when interactive, lets the user open any incident's full report.
    def display_summary(self, records: list[Incident], interactive: bool = True) -> None:
        self._printer.print_summary(records)
        if not records:
            return
        self._printer.print_severity_guide()
        print()
        while interactive:
            number = self._ask_number("Enter an incident # for its full report (or press Enter to go back): ",
                                      len(records))
            if number is None:
                break
            self._printer.print_incident(records[number - 1], number)

    # Checks one batch item with the same rules as typed input; returns (incident, []) or (None, problems).
    def _validate_batch_item(self, item: dict, base_folder: str) -> tuple[Incident | None, list[str]]:
        fields, bad = self._validator.validate_fields(item)
        photo = None
        if item.get("photo_path"):
            try:
                photo = IncidentPhoto.from_file(os.path.join(base_folder, str(item["photo_path"])))
            except PhotoError as error:
                bad.append(f"photo_path ({error})")
        if bad:
            return None, bad
        return Incident(**fields, photo=photo), []

    # Reads a JSON list of incidents for batch mode; returns (valid incidents, problem messages), never raises.
    def read_incident_file(self, path: str) -> tuple[list[Incident], list[str]]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                items = json.load(f)
        except (OSError, ValueError) as error:
            return [], [f"Could not read {path}: {error}"]
        if not isinstance(items, list):
            return [], [f"{path} must contain a JSON list of incidents"]
        incidents, problems = [], []
        for number, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                problems.append(f"Item {number}: not an object")
                continue
            incident, bad = self._validate_batch_item(item, os.path.dirname(os.path.abspath(path)))
            if incident is None:
                problems.append(f"Item {number}: missing or invalid " + ", ".join(bad))
            else:
                incidents.append(incident)
        return incidents, problems
