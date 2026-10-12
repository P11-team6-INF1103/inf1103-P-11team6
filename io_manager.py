import json
import re
import shutil
import sys
import textwrap
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


# Draws the spinner on one line until stop is set.
def _animate_spinner(stop: threading.Event, message: str) -> None:
    frame = 0
    while not stop.is_set():
        dots = "." * (frame // 3 % 4)
        spinner = _SPINNER_FRAMES[frame % len(_SPINNER_FRAMES)]
        sys.stdout.write(f"\r{spinner} {message}{dots:<3}")
        sys.stdout.flush()
        frame += 1
        stop.wait(0.1)


# Shows a spinner and message while the with-block runs; does nothing if output is not a terminal.
@contextmanager
def show_loading(message: str = "AI is thinking") -> Iterator[None]:
    if not sys.stdout.isatty():
        yield
        return

    stop = threading.Event()
    thread = threading.Thread(target=_animate_spinner, args=(stop, message), daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
        sys.stdout.write("\r" + " " * (len(message) + 6) + "\r")
        sys.stdout.flush()


# Input validation. Each _check_* returns an error message, or None when the text is fine.
_MIN_DESCRIPTION = 10
_MAX_DESCRIPTION = 500
_MAX_LOCATION = 100
_MAX_ROLE = 40
_LOCATION_CHARS = re.compile(r"^[A-Za-z0-9 \-,./()#]+$")
_ROLE_CHARS = re.compile(r"^[A-Za-z _/\-]+$")


# Collapses whitespace and drops unprintable characters from typed text.
def _sanitise(text: object) -> str:
    text = " ".join(str(text).split())
    return "".join(ch for ch in text if ch.isprintable())


# Error message if the description is not acceptable (empty, too short or long, not words), else None.
def _check_description(text: str) -> str | None:
    if text == "":
        return "Description cannot be empty."
    if len(text) < _MIN_DESCRIPTION:
        return f"Description is too short. Say what happened in at least {_MIN_DESCRIPTION} characters."
    if len(text) > _MAX_DESCRIPTION:
        return f"Description is too long (maximum {_MAX_DESCRIPTION} characters)."
    no_spaces = text.replace(" ", "")
    if sum(ch.isalpha() for ch in no_spaces) < len(no_spaces) / 2:
        return "Description must be mostly words, not symbols or numbers."
    if len(re.findall(r"[A-Za-z]{2,}", text)) < 2:
        return "Description must contain at least 2 real words."
    if len({ch for ch in text.lower() if ch.isalpha()}) < 4:
        return "Description looks like repeated characters. Describe the incident in words."
    return None


# Error message if the location is not acceptable, else None.
def _check_location(text: str) -> str | None:
    if text == "":
        return "Location cannot be empty."
    if len(text) > _MAX_LOCATION:
        return f"Location is too long (maximum {_MAX_LOCATION} characters)."
    if not _LOCATION_CHARS.match(text):
        return "Location may only contain letters, digits, spaces and - , . / ( ) #"
    if not re.search(r"[A-Za-z]", text):
        return "Location must contain at least one letter, e.g. 'Site A - Block 3'."
    return None


# Error message if the reporter role is not acceptable, else None.
def _check_role(text: str) -> str | None:
    if text == "":
        return "Role cannot be empty."
    if len(text) < 2:
        return "Role is too short, e.g. 'site_supervisor'."
    if len(text) > _MAX_ROLE:
        return f"Role is too long (maximum {_MAX_ROLE} characters)."
    if not _ROLE_CHARS.match(text):
        return "Role may only contain letters, spaces, _ - and /"
    return None


# Asks until the sanitised answer passes the check, saying why each answer was rejected; pressing Enter twice on a blank answer returns None.
def _ask_valid(prompt: str, check: Callable[[str], str | None]) -> str | None:
    blank_before = False
    while True:
        answer = input(prompt)
        if answer.strip() == "":
            if blank_before:
                return None
            blank_before = True
            print("Nothing entered. Type your answer, or press Enter again to go back to the main menu.")
            prompt = "Try again: "
            continue
        blank_before = False
        value = _sanitise(answer)
        error = check(value)
        if error is None:
            return value
        print("Error: " + error)
        prompt = "Try again: "


# Asks until the answer is yes or no; returns True for yes, or None if allow_back is set and the user presses Enter twice on a blank answer.
def _ask_yes_no(prompt: str, allow_back: bool = False) -> bool | None:
    answer = input(prompt).strip().lower()
    blank_before = False
    while answer not in ("yes", "no", "y", "n"):
        if allow_back and answer == "":
            if blank_before:
                return None
            blank_before = True
            message = "Please answer yes or no, or press Enter again to go back: "
        else:
            blank_before = False
            message = "Please answer yes or no: "
        answer = input(message).strip().lower()
    return answer in ("yes", "y")


# Asks whether to enter a rejected incident again.
def ask_try_again() -> bool:
    return _ask_yes_no("Enter the incident again? (yes/no): ")


# Warns that the incident is not on disk and asks whether to try saving again.
def ask_retry_save() -> bool:
    print()
    print("!" * 60)
    print("  INCIDENT NOT SAVED: it could not be written to disk and")
    print("  will be lost when you exit the program.")
    print("!" * 60)
    return _ask_yes_no("Try saving again? (yes/no): ")


# Daniel
# Shows the main menu and returns '1' to '5'; Ctrl+C or closed input returns '5'.
def get_menu_choice() -> str:
    print("\n=== Workplace Safety Incident Triage System ===")
    print("1. Log a new incident")
    print("2. View summary of all incidents")
    print("3. Query incidents by location")
    print("4. Delete an incident")
    print("5. Exit")
    try:
        choice = input("Choose an option (1-5): ").strip()
        while choice not in ("1", "2", "3", "4", "5"):
            choice = input("Invalid choice. Please enter 1, 2, 3, 4 or 5: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "5"
    return choice


# Asks which incident number to delete; returns it, or None if the user presses Enter, Ctrl+C or closes the input.
def get_delete_choice(count: int) -> int | None:
    while True:
        try:
            choice = input(f"Enter the incident # to delete (1-{count}, or press Enter to go back): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if choice == "":
            return None
        if choice.isdigit() and 1 <= int(choice) <= count:
            return int(choice)
        print(f"Please enter a number from 1 to {count}.")


# Shows the incident about to be deleted and asks the user to confirm.
def confirm_delete(record: dict, number: int) -> bool:
    print(f"\nIncident #{number}: {record.get('location')} - {record.get('description')}")
    return _ask_yes_no("Delete this incident permanently? (yes/no): ")


# Ren Xiang
# Asks for description, location, reporter role and injury, re-prompting until each is valid; pressing Enter twice on a blank answer returns None.
def get_incident_input() -> dict | None:
    print("\n--- Log a New Incident ---")
    print("(Press Enter twice on a blank answer to return to the main menu.)")

    description = _ask_valid("Describe what happened: ", _check_description)
    if description is None:
        return None
    location = _ask_valid("Location (e.g. 'Site A - Block 3'): ", _check_location)
    if location is None:
        return None
    reporter_role = _ask_valid("Your role (e.g. 'site_supervisor'): ", _check_role)
    if reporter_role is None:
        return None
    injury = _ask_yes_no("Was anyone injured? (yes/no): ", allow_back=True)
    if injury is None:
        return None

    return {
        "description": description,
        "location": location,
        "reporter_role": reporter_role,
        "injury": injury,
        "timestamp": datetime.now().isoformat(),
    }


# Prints one line of text; the only way other modules show messages.
def display_message(text: str) -> None:
    print(text)


# Lists the saved locations and returns the one picked, or None to go back.
def _choose_location(known_locations: list) -> str | None:
    if not known_locations:
        print("No incidents have been saved yet, so there are no locations to list.")
        return None
    print("Saved locations:")
    for number, (location, count) in enumerate(known_locations, start=1):
        noun = "incident" if count == 1 else "incidents"
        print(f"  {number}. {location} ({count} {noun})")
    while True:
        picked = input("Choose a number (or press Enter to go back): ").strip()
        if picked == "":
            return None
        if picked.isdigit() and 1 <= int(picked) <= len(known_locations):
            return known_locations[int(picked) - 1][0]
        print(f"Please enter a number from 1 to {len(known_locations)}.")


# Asks for a location (or 'list') and a number of days; returns (location, days), or None to go back.
def get_location_query(known_locations: list | None = None) -> tuple[str, int] | None:
    if known_locations is None:
        prompt = "Location to search (or press Enter to go back to the menu): "
    else:
        prompt = ("Location to search, type 'list' to pick from saved locations "
                  "(or press Enter to go back to the menu): ")
    while True:
        location = _sanitise(input(prompt))
        if location == "":
            return None
        if known_locations is not None and location.lower() == "list":
            location = _choose_location(known_locations)
            if location is None:
                return None
        error = _check_location(location)
        if error is None:
            break
        print("Error: " + error)
        prompt = "Try again (or press Enter to go back to the menu): "

    days_input = input("How many days back? (Enter for 30): ").strip()
    while days_input != "" and not (days_input.isdigit() and int(days_input) > 0):
        days_input = input("Please enter a whole number of days, 1 or more: ").strip()
    return location, int(days_input) if days_input else 30


# Prints the incidents found by a location query.
def display_query_results(results: list) -> None:
    if not results:
        print("No matching incidents found.")
        return
    print(f"{len(results)} matching incident(s):")
    for item in results:
        print(f"[{_format_time(item.get('timestamp'))}] {item.get('location')} -> "
              f"{_OUTCOME_NAMES.get(item.get('outcome'), item.get('outcome'))}")


# Lookup tables for display_outcome() / display_summary()
_SEASON_TEXT = {
    "northeast_monsoon": "Northeast monsoon season (Dec to early Mar): wet and windy, heavy rain spells",
    "southwest_monsoon": "Southwest monsoon season (Jun to Sep): hot, early-morning squalls, possible haze",
    "inter_monsoon": "Inter-monsoon season (Apr-May, Oct-Nov): hot, afternoon thunderstorms and lightning",
}

_HAZARD_NAMES = {
    "fall": "Slip, trip or fall (ground level)",
    "fall_from_height": "Fall from height",
    "electrical": "Electrical",
    "chemical": "Chemical",
    "vehicular": "Vehicle or mobile machinery",
    "struck_by_machinery": "Struck by machinery",
    "low_visibility": "Poor visibility",
    "other": "Other",
    "unassessed": "Not assessed",
}

_HAZARD_SHORT = dict(_HAZARD_NAMES, fall="Fall (ground level)", vehicular="Vehicle / mobile machinery")

_OUTCOME_NAMES = {
    "stop_work_review": "STOP WORK - safety review",
    "systemic_escalation": "ESCALATE to management",
    "log_only": "LOG ONLY",
    "pending_review": "NEEDS MANUAL REVIEW",
}

_OUTCOME_SHORT = {
    "stop_work_review": "STOP WORK",
    "systemic_escalation": "ESCALATE",
    "log_only": "Log only",
    "pending_review": "MANUAL REVIEW",
}

_WIDTH = 64
_LABEL_WIDTH = 14


# Formats an ISO timestamp as '05 Oct 2026, 09:00', or returns it unchanged if unreadable.
def _format_time(timestamp: object) -> str:
    try:
        return datetime.fromisoformat(timestamp).strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        return str(timestamp)


# Report width: the terminal width kept between 60 and 90 columns.
def _report_width() -> int:
    return min(max(shutil.get_terminal_size((100, 24)).columns, 60), 90)


# Removes citation markers and swaps fancy hyphens and quotes for plain ones.
def _clean(text: object) -> str:
    text = re.sub(r"【[^】]*】", "", str(text))
    text = text.translate({0x2011: "-", 0x2010: "-", 0x2019: "'", 0x2018: "'"})
    return re.sub(r"\s+([.,;])(?=\s|$)", r"\1", " ".join(text.split()))


# Prints a section heading line.
def _section(title: str, width: int) -> None:
    print(f"\n── {title} " + "─" * max(width - len(title) - 4, 3))


# Prints 'label  value' with wrapped lines hanging under the value; a list prints one bullet per item.
def _field(label: str, value: object, width: int, indent: int = 2, label_width: int = _LABEL_WIDTH) -> None:
    items = value if isinstance(value, list) else [value]
    bullets = isinstance(value, list)
    hang = " " * (indent + label_width)
    for position, item in enumerate(items):
        lead = " " * indent + label.ljust(label_width) if position == 0 else hang
        print(textwrap.fill(
            ("- " if bullets else "") + _clean(item), width,
            initial_indent=lead, subsequent_indent=hang + ("  " if bullets else ""),
            break_long_words=False, break_on_hyphens=False,
        ))


# Plain-English text for each *_error field a record can carry. The raw
# error text (HTTP codes, model names) goes to the log, not to the user.
_PROBLEM_MESSAGES = (
    ("context_flags_error", ("Hazard details (type, injury, height, PPE) could not be read "
     "automatically, so default values were used. Please check the severity score manually.")),
    ("assessment_error", ("The AI service is unavailable, so this incident was not scored. "
     "Please assess it manually and try again later.")),
    ("enrichment_error", ("Current weather could not be retrieved, so weather was not "
     "factored into this report.")),
    ("web_search_error", ("We couldn't look up similar incidents or industry information "
     "online right now. The rest of this report is unaffected.")),
    ("similar_incidents_error", ("We couldn't compare this with earlier incidents on our "
     "own sites right now.")),
    ("review_error", ("Causes and prevention advice couldn't be generated. Please discuss "
     "prevention steps with your safety officer.")),
)
_ALL_AI_DOWN_MESSAGE = (
    "AI services are currently unavailable (check your internet connection or API keys). "
    "This record was saved, but needs manual review."
)
_KEY_HINT = "An API key looks missing: check GEMINI_API_KEY and GROQ_API_KEY in the .env file."


# Plain-English messages for each *_error field on the record.
def _friendly_problems(record: dict) -> list:
    problems = [text for field, text in _PROBLEM_MESSAGES if record.get(field)]
    if all(record.get(f) for f in ("context_flags_error", "web_search_error", "review_error")):
        problems.insert(0, _ALL_AI_DOWN_MESSAGE)
    raw = " ".join(str(record.get(field) or "") for field, _ in _PROBLEM_MESSAGES)
    if "API_KEY" in raw:
        problems.append(_KEY_HINT)
    return problems


# Prints the report banner and the fields the supervisor logged.
def _print_report_header(record: dict, width: int, number: int | None) -> None:
    title = f"INCIDENT #{number}" if number else "INCIDENT REPORT"
    print("═" * width)
    print(f" {title}   {record.get('location')}   {_format_time(record.get('timestamp'))}")
    print("═" * width)

    hazard = record.get("hazard_type")
    _field("What happened", record.get("description"), width, indent=1, label_width=15)
    _field("Reported by", record.get("reporter_role"), width, indent=1, label_width=15)
    _field("Anyone injured", "Yes" if record.get("injury") else "No", width, indent=1, label_width=15)
    _field("Type of hazard", _HAZARD_NAMES.get(hazard, hazard), width, indent=1, label_width=15)


# Prints the severity gauge, the reasons behind it, how likely it is to recur and the action to take.
def _print_severity_section(record: dict, width: int, severity_levels: dict, outcome_actions: dict) -> None:
    outcome = record.get("outcome")
    severity = record.get("severity_estimate")
    _section("SEVERITY AND ACTION", width)
    if record.get("assessment_error"):
        _field("Severity", "NOT ASSESSED - the AI could not analyse this incident, so it was not scored.", width)
    else:
        level = severity_levels.get(severity)
        gauge = "█" * (severity or 0) + "░" * (5 - (severity or 0))
        name = f"  {level[0].upper()}" if level else ""
        _field("Severity", f"{gauge}  {severity}/5{name}", width)
        if level:
            _field("", level[1], width)
        reasons = [r for r in record.get("severity_reasons") or []
                   if not r.startswith(("Base score", "Capped"))]
        if reasons:
            _field("Why", reasons, width)
        _field("Could recur", record.get("likelihood_recurrence"), width)
    _field("Action", _OUTCOME_NAMES.get(outcome, outcome), width)
    if outcome in outcome_actions:
        _field("", outcome_actions[outcome], width)


# Prints the weather and season at the time; nothing if the weather was not checked.
def _print_weather_section(record: dict, width: int) -> None:
    if record.get("weather_available"):
        _section("WEATHER AT THE TIME", width)
        _field("Conditions", (
            f"{str(record.get('condition')).capitalize()}, {record.get('temperature_c')}°C, "
            f"{record.get('humidity_pct')}% humidity"
        ), width)
        if record.get("monsoon_season") in _SEASON_TEXT:
            _field("Season", _SEASON_TEXT[record["monsoon_season"]], width)


# Prints the web-search findings: industry context and similar incidents reported elsewhere.
def _print_web_sections(record: dict, width: int) -> None:
    if record.get("web_industry_context"):
        _section("IS THIS A KNOWN ISSUE IN THE INDUSTRY?", width)
        _field("", record["web_industry_context"], width, label_width=0)

    if record.get("web_incidents"):
        _section("SIMILAR INCIDENTS REPORTED ELSEWHERE", width)
        for i, item in enumerate(record["web_incidents"], start=1):
            print(textwrap.fill(_clean(item.get("summary")), width, initial_indent=f"  {i}. ",
                                subsequent_indent="     ", break_long_words=False))
            _field("Where / when", f"{item.get('location')}, {item.get('date')}", width, indent=5)
            _field("What was done", item.get("action_taken"), width, indent=5)
            _field("Source", item.get("source_url"), width, indent=5)
            if i < len(record["web_incidents"]):
                print()


# Prints similar incidents found in our own saved records.
def _print_similar_sites_section(record: dict, width: int) -> None:
    if record.get("similar_incidents"):
        _section("SIMILAR INCIDENTS ON OUR OWN SITES", width)
        for i, item in enumerate(record["similar_incidents"], start=1):
            date = _format_time(item.get("timestamp"))[:11]
            outcome_name = _OUTCOME_NAMES.get(item.get("outcome"), item.get("outcome"))
            print(textwrap.fill(
                f"\"{item.get('description')}\" - {item.get('location')}, {date}", width,
                initial_indent=f"  {i}. ", subsequent_indent="     ", break_long_words=False))
            _field("Action taken", outcome_name, width, indent=5)


# Prints the AI after-action review: likely causes and prevention actions.
def _print_review_sections(record: dict, width: int) -> None:
    if record.get("review_likely_causes"):
        _section("WHY IT LIKELY HAPPENED", width)
        _field("", record["review_likely_causes"], width, label_width=0)
    if record.get("review_prevention_actions"):
        _section("HOW TO PREVENT IT", width)
        _field("", record["review_prevention_actions"], width, label_width=0)


# Prints everything the AI could not do, in one place; nothing if every step worked.
def _print_problems_section(record: dict, width: int) -> None:
    problems = _friendly_problems(record)
    if record.get("assessment_error"):
        problems.append(f"Assessment: {record['assessment_error']}")
    if record.get("web_search_error"):
        problems.append(f"Web search: {record['web_search_error']}")
    if record.get("review_error"):
        problems.append(f"Review: {record['review_error']}")
    if record.get("similar_incidents_error"):
        problems.append(f"Own-site search: {record['similar_incidents_error']}")
    if problems:
        _section("NOTE: SOME AI STEPS DID NOT WORK", width)
        _field("", problems, width, label_width=0)


# Prints the full report for one incident, one section after another, leaving out empty sections.
def _print_incident_report(record: dict, severity_levels: dict | None = None, outcome_actions: dict | None = None, number: int | None = None) -> None:
    severity_levels = severity_levels or {}
    outcome_actions = outcome_actions or {}
    width = _report_width()

    _print_report_header(record, width, number)
    _print_severity_section(record, width, severity_levels, outcome_actions)
    _print_weather_section(record, width)
    _print_web_sections(record, width)
    _print_similar_sites_section(record, width)
    _print_review_sections(record, width)
    _print_problems_section(record, width)
    print("═" * width)
    print()


# Ren Xiang
# Prints the full report for one processed incident.
def display_outcome(record: dict, severity_levels: dict | None = None, outcome_actions: dict | None = None) -> None:
    print()
    _print_incident_report(record, severity_levels, outcome_actions)


# Ren Xiang
# Prints what each severity level means.
def display_severity_guide(severity_levels: dict) -> None:
    print("\nWHAT THE SEVERITY LEVELS MEAN")
    for level in sorted(severity_levels):
        name, meaning = severity_levels[level]
        print(f"  {level} {name:<9} {meaning}")


# One horizontal border line of the boxed table.
def _table_border(widths: list, left: str, mid: str, right: str) -> str:
    return left + mid.join("─" * (w + 2) for w in widths) + right


# Prints a boxed table; long cells wrap inside their column.
def _print_table(headers: list, rows: list, widths: list) -> None:
    print(_table_border(widths, "┌", "┬", "┐"))
    all_rows = [headers] + rows
    for index, row in enumerate(all_rows):
        cells = [textwrap.wrap(str(cell), w) or [""] for cell, w in zip(row, widths)]
        for i in range(max(len(c) for c in cells)):
            parts = [(c[i] if i < len(c) else "").ljust(w) for c, w in zip(cells, widths)]
            print("│ " + " │ ".join(parts) + " │")
        if index < len(all_rows) - 1:
            print(_table_border(widths, "├", "┼", "┤"))
    print(_table_border(widths, "└", "┴", "┘"))


# How many incidents have each outcome and each hazard, by display name.
def _count_by_outcome_and_hazard(records: list) -> tuple[dict, dict]:
    outcome_counts = {}
    hazard_counts = {}
    for record in records:
        outcome = _OUTCOME_NAMES.get(record.get("outcome"), record.get("outcome"))
        hazard = _HAZARD_NAMES.get(record.get("hazard_type"), record.get("hazard_type"))
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        hazard_counts[hazard] = hazard_counts.get(hazard, 0) + 1

    return outcome_counts, hazard_counts


# Column widths for the summary table; Location and Description share the width left over.
def _summary_columns() -> list[int]:
    fixed = [3, 11, 18, 3, 13]
    total_width = max(shutil.get_terminal_size((100, 24)).columns, 100)
    spare = total_width - sum(fixed) - (3 * 7 + 1)
    location_width = max(spare * 2 // 5, 12)
    description_width = max(spare - location_width, 20)
    widths = [fixed[0], fixed[1], location_width, fixed[2], fixed[3], fixed[4], description_width]
    return widths


# One table row per incident, with pending review first and then the most severe.
def _summary_rows(records: list) -> list[list]:
    ordered = sorted(
        enumerate(records, start=1),
        key=lambda pair: (
            pair[1].get("outcome") == "pending_review",
            pair[1].get("severity_estimate") or 0,
        ),
        reverse=True,
    )

    rows = []
    for number, record in ordered:
        date, _, time = _format_time(record.get("timestamp")).partition(", ")
        hazard = record.get("hazard_type")
        outcome = record.get("outcome")
        rows.append([
            number,
            f"{date} {time}".strip(),
            record.get("location"),
            _HAZARD_SHORT.get(hazard, hazard),
            record.get("severity_estimate") if not record.get("assessment_error") else "-",
            _OUTCOME_SHORT.get(outcome, outcome),
            record.get("description"),
        ])
    return rows


# Asks for an incident number and prints its full report, until the user presses Enter.
def _open_report_loop(records: list, severity_levels: dict | None, outcome_actions: dict | None) -> None:
    while True:
        try:
            choice = input("Enter an incident # for its full report (or press Enter to go back): ").strip()
        except EOFError:
            break
        if choice == "":
            break
        if choice.isdigit() and 1 <= int(choice) <= len(records):
            print()
            _print_incident_report(records[int(choice) - 1], severity_levels, outcome_actions,
                                   number=int(choice))
        else:
            print(f"Please enter a number from 1 to {len(records)}.")


# Ren Xiang
# Prints counts by outcome and hazard, a table of all incidents and the severity guide; can open a full report.
def display_summary(records: list, severity_levels: dict | None = None, outcome_actions: dict | None = None, interactive: bool = True) -> None:
    print("\n" + "#" * _WIDTH)
    print("INCIDENT SUMMARY / AFTER-ACTION REVIEW")
    print("#" * _WIDTH)
    if not records:
        print("No incidents logged yet.")
        return

    outcome_counts, hazard_counts = _count_by_outcome_and_hazard(records)
    print(f"Total incidents: {len(records)}")
    print("By action: " + ", ".join(f"{k} ({v})" for k, v in sorted(outcome_counts.items())))
    print("By hazard: " + ", ".join(f"{k} ({v})" for k, v in sorted(hazard_counts.items())))

    print("\nOVERVIEW (needs manual review first, then most severe)")
    _print_table(["#", "When", "Location", "Hazard", "Sev", "Action", "What happened"],
                 _summary_rows(records), _summary_columns())

    if severity_levels:
        display_severity_guide(severity_levels)

    print()
    if interactive:
        _open_report_loop(records, severity_levels, outcome_actions)


# Checks one batch item with the same rules as typed input; returns (incident, []) or (None, bad fields).
def _validate_incident_item(item: dict) -> tuple[dict | None, list[str]]:
    bad = []
    for key, check in (("description", _check_description),
                       ("location", _check_location),
                       ("reporter_role", _check_role)):
        if not isinstance(item.get(key), str):
            bad.append(key)
            continue
        item[key] = _sanitise(item[key]).strip()
        error = check(item[key])
        if error:
            bad.append(f"{key} ({error})")
    injury = item.get("injury")
    if isinstance(injury, str) and injury.strip().lower() in ("yes", "y", "no", "n"):
        injury = injury.strip().lower() in ("yes", "y")
    if not isinstance(injury, bool):
        bad.append("injury (true/false)")
    timestamp = item.get("timestamp") or datetime.now().isoformat()
    try:
        datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        bad.append("timestamp (ISO format)")
    if bad:
        return None, bad
    return {
        "description": item["description"],
        "location": item["location"],
        "reporter_role": item["reporter_role"],
        "injury": injury,
        "timestamp": timestamp,
    }, []


# Reads a JSON list of incidents for batch mode; returns (valid incidents, problem messages), never raises.
def read_incident_file(path: str) -> tuple[list, list]:
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
        incident, bad = _validate_incident_item(item)
        if incident is None:
            problems.append(f"Item {number}: missing or invalid " + ", ".join(bad))
        else:
            incidents.append(incident)
    return incidents, problems
