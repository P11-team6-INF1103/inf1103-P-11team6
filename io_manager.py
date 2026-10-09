import re
import shutil
import sys
import textwrap
import threading
from contextlib import contextmanager
from datetime import datetime

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

#Loading Interface
@contextmanager
def show_loading(message="AI is thinking"):
    """Shows an animated spinner on the terminal while the `with` block runs,
    then clears the line. Does nothing when stdout isn't a terminal (piped
    output, tests), so it never pollutes captured output."""
    if not sys.stdout.isatty():
        yield
        return

    stop = threading.Event()

    def animate():
        frame = 0
        while not stop.is_set():
            dots = "." * (frame // 3 % 4)
            spinner = _SPINNER_FRAMES[frame % len(_SPINNER_FRAMES)]
            sys.stdout.write(f"\r{spinner} {message}{dots:<3}")
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


#incident log interface 
def get_menu_choice():
    print("\n=== Workplace Safety Incident Triage System ===")
    print("1. Log a new incident")
    print("2. View summary of all incidents")
    print("3. Query incidents by location")
    print("4. Exit")
    choice = input("Choose an option (1-4): ").strip()
    while choice not in ("1", "2", "3", "4"):
        choice = input("Invalid choice. Please enter 1, 2, 3 or 4: ").strip()
    return choice

#Input Validation for incident input
_MIN_DESCRIPTION = 10
_MAX_DESCRIPTION = 500
_MAX_LOCATION = 100
_MAX_ROLE = 40
_LOCATION_CHARS = re.compile(r"^[A-Za-z0-9 \-,./()#]+$")
_ROLE_CHARS = re.compile(r"^[A-Za-z _/\-]+$")


def _sanitise(text):
    """Collapses runs of whitespace and drops control characters."""
    text = " ".join(str(text).split())
    return "".join(ch for ch in text if ch.isprintable())


def _check_description(text):
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


def _check_location(text):
    if text == "":
        return "Location cannot be empty."
    if len(text) > _MAX_LOCATION:
        return f"Location is too long (maximum {_MAX_LOCATION} characters)."
    if not _LOCATION_CHARS.match(text):
        return "Location may only contain letters, digits, spaces and - , . / ( ) #"
    if not re.search(r"[A-Za-z]", text):
        return "Location must contain at least one letter, e.g. 'Site A - Block 3'."
    return None


def _check_role(text):
    if text == "":
        return "Role cannot be empty."
    if len(text) < 2:
        return "Role is too short, e.g. 'site_supervisor'."
    if len(text) > _MAX_ROLE:
        return f"Role is too long (maximum {_MAX_ROLE} characters)."
    if not _ROLE_CHARS.match(text):
        return "Role may only contain letters, spaces, _ - and /"
    return None


def _ask_valid(prompt, check):
    """Asks until the (sanitised) answer passes `check`; prints why each
    rejected answer was rejected."""
    while True:
        value = _sanitise(input(prompt))
        error = check(value)
        if error is None:
            return value
        print("Error: " + error)
        prompt = "Try again: "


def ask_try_again():
    """After the AI rejects an incident as not a real safety incident: asks
    whether to enter it again. Returns True for yes."""
    answer = input("Enter the incident again? (yes/no): ").strip().lower()
    while answer not in ("yes", "no", "y", "n"):
        answer = input("Please answer yes or no: ").strip().lower()
    return answer in ("yes", "y")

#incident input interface
def get_incident_input():
    """Prompts for description, location, reporter role, and injury flag.
    Validates and reprompts on bad input (empty, symbols, too short or too
    long, wrong characters). Returns an `incident` dict matching
    contracts.md section 1."""
    print("\n--- Log a New Incident ---")

    description = _ask_valid("Describe what happened: ", _check_description)
    location = _ask_valid("Location (e.g. 'Site A - Block 3'): ", _check_location)
    reporter_role = _ask_valid("Your role (e.g. 'site_supervisor'): ", _check_role)

    injury_input = input("Was anyone injured? (yes/no): ").strip().lower()
    while injury_input not in ("yes", "no", "y", "n"):
        injury_input = input("Please answer yes or no: ").strip().lower()
    injury = injury_input in ("yes", "y")

    return {
        "description": description,
        "location": location,
        "reporter_role": reporter_role,
        "injury": injury,
        "timestamp": datetime.now().isoformat(),
    }

#Helper functions for formatting output display_outcome() / display_summary()
def _format_time(timestamp):
    try:
        return datetime.fromisoformat(timestamp).strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        return str(timestamp)

_LABEL_WIDTH = 14

def _report_width():
    """Wrap width for the full report: the terminal width, kept readable."""
    return min(max(shutil.get_terminal_size((100, 24)).columns, 60), 90)

def _clean(text):
    """Tidies web/AI text for the terminal: drops citation markers like
    【9†L109-L112】 and swaps fancy hyphens/quotes for plain ones."""
    text = re.sub(r"【[^】]*】", "", str(text))
    text = text.translate({0x2011: "-", 0x2010: "-", 0x2019: "'", 0x2018: "'"})
    # Close up "word ." / "word ," but leave ".env" (dot followed by a letter) alone.
    return re.sub(r"\s+([.,;])(?=\s|$)", r"\1", " ".join(text.split()))

def _field(label, value, width, indent=2, label_width=_LABEL_WIDTH):
    """Prints `label  value` with wrapped lines hanging under the value. A
    list value prints one '- ' bullet per item."""
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

def _section(title, width):
    print(f"\n── {title} " + "─" * max(width - len(title) - 4, 3))


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

_OUTCOME_NAMES = {
    "stop_work_review": "STOP WORK - safety review",
    "systemic_escalation": "ESCALATE to management",
    "log_only": "LOG ONLY",
    "pending_review": "NEEDS MANUAL REVIEW",
}

_WIDTH = 64

#print incident report
def _print_incident_report(record, severity_levels=None, outcome_actions=None, number=None):
    severity_levels = severity_levels or {}
    outcome_actions = outcome_actions or {}
    width = _report_width()

    title = f"INCIDENT #{number}" if number else "INCIDENT REPORT"
    print("=" * width)
    print(f"{title}   {record.get('location')}   {_format_time(record.get('timestamp'))}")
    print("=" * width)

    # --- What was logged ---
    hazard = record.get("hazard_type")
    _field("What happened", record.get("description"), width, indent=1, label_width=15)
    _field("Reported by", record.get("reporter_role"), width, indent=1, label_width=15)
    _field("Anyone injured", "Yes" if record.get("injury") else "No", width, indent=1, label_width=15)
    _field("Type of hazard", _HAZARD_NAMES.get(hazard, hazard), width, indent=1, label_width=15)

    # --- Severity and action ---
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

    # --- Weather: only when it was checked ---
    if record.get("weather_available"):
        _section("WEATHER AT THE TIME", width)
        _field("Conditions", (
            f"{str(record.get('condition')).capitalize()}, {record.get('temperature_c')}°C, "
            f"{record.get('humidity_pct')}% humidity"
        ), width)
        if record.get("monsoon_season") in _SEASON_TEXT:
            _field("Season", _SEASON_TEXT[record["monsoon_season"]], width)

    # --- Known industry issue (web) ---
    if record.get("web_industry_context"):
        _section("IS THIS A KNOWN ISSUE IN THE INDUSTRY?", width)
        _field("", record["web_industry_context"], width, label_width=0)

    # --- Similar real incidents (web) ---
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

    # --- Similar incidents on our own sites ---
    if record.get("similar_incidents"):
        _section("SIMILAR INCIDENTS ON OUR OWN SITES", width)
        for i, item in enumerate(record["similar_incidents"], start=1):
            date = _format_time(item.get("timestamp"))[:11]
            outcome_name = _OUTCOME_NAMES.get(item.get("outcome"), item.get("outcome"))
            print(textwrap.fill(
                f"\"{item.get('description')}\" - {item.get('location')}, {date}", width,
                initial_indent=f"  {i}. ", subsequent_indent="     ", break_long_words=False))
            _field("Action taken", outcome_name, width, indent=5)

    # --- After-action review (AI) ---
    if record.get("review_likely_causes"):
        _section("WHY IT LIKELY HAPPENED", width)
        _field("", record["review_likely_causes"], width, label_width=0)
    if record.get("review_prevention_actions"):
        _section("HOW TO PREVENT IT", width)
        _field("", record["review_prevention_actions"], width, label_width=0)

    # --- Anything the AI couldn't do, in one place ---
    problems = []
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
    print("═" * width)
    print()

def display_outcome(record, severity_levels=None, outcome_actions=None):
    print()
    _print_incident_report(record, severity_levels, outcome_actions)

#Serverity Level
def display_severity_guide(severity_levels):
    print("\nWHAT THE SEVERITY LEVELS MEAN")
    for level in sorted(severity_levels):
        name, meaning = severity_levels[level]
        print(f"  {level} {name:<9} {meaning}")

_HAZARD_SHORT = {
    "fall": "Fall (ground level)",
    "fall_from_height": "Fall from height",
    "electrical": "Electrical",
    "chemical": "Chemical",
    "vehicular": "Vehicle / mobile machinery",
    "struck_by_machinery": "Struck by machinery",
    "low_visibility": "Poor visibility",
    "other": "Other",
    "unassessed": "Not assessed",
}

_OUTCOME_SHORT = {
    "stop_work_review": "STOP WORK",
    "systemic_escalation": "ESCALATE",
    "log_only": "Log only",
    "pending_review": "MANUAL REVIEW",
}

def display_summary(records, severity_levels=None, outcome_actions=None):
    print("\n" + "#" * _WIDTH)
    print("INCIDENT SUMMARY / AFTER-ACTION REVIEW")
    print("#" * _WIDTH)
    if not records:
        print("No incidents logged yet.")
        return

    outcome_counts = {}
    hazard_counts = {}
    for record in records:
        outcome = _OUTCOME_NAMES.get(record.get("outcome"), record.get("outcome"))
        hazard = _HAZARD_NAMES.get(record.get("hazard_type"), record.get("hazard_type"))
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        hazard_counts[hazard] = hazard_counts.get(hazard, 0) + 1

    print(f"Total incidents: {len(records)}")
    print("By action: " + ", ".join(f"{k} ({v})" for k, v in sorted(outcome_counts.items())))
    print("By hazard: " + ", ".join(f"{k} ({v})" for k, v in sorted(hazard_counts.items())))

    ordered = sorted(
        enumerate(records, start=1),
        key=lambda pair: (
            pair[1].get("outcome") == "pending_review",
            pair[1].get("severity_estimate") or 0,
        ),
        reverse=True,
    )
    print("\nOVERVIEW (needs manual review first, then most severe)")
    for number, record in ordered:
        hazard = _HAZARD_NAMES.get(record.get("hazard_type"), record.get("hazard_type"))
        outcome = _OUTCOME_NAMES.get(record.get("outcome"), record.get("outcome"))
        print(
            f"  #{number}  {_format_time(record.get('timestamp'))}  {record.get('location')}  "
            f"- {hazard}, severity {record.get('severity_estimate')} -> {outcome}"
        )

    if severity_levels:
        display_severity_guide(severity_levels)

    print()
    for number, record in ordered:
        _print_incident_report(record, severity_levels, outcome_actions, number=number)
    print("#" * _WIDTH)
    print("END OF SUMMARY")
    print("#" * _WIDTH)
