from datetime import datetime

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

#incident input interface
def get_incident_input():
    """Prompts for description, location, reporter role, and injury flag.
    Validates and reprompts on bad input. Returns an `incident` dict
    matching contracts.md section 1."""
    print("\n--- Log a New Incident ---")

    description = input("Describe what happened: ").strip()
    while description == "":
        description = input("Description cannot be empty. Try again: ").strip()

    location = input("Location (e.g. 'Site A - Block 3'): ").strip()
    while location == "":
        location = input("Location cannot be empty. Try again: ").strip()

    reporter_role = input("Your role (e.g. 'site_supervisor'): ").strip()
    while reporter_role == "":
        reporter_role = input("Role cannot be empty. Try again: ").strip()

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
    """'2026-09-27T20:44:10' -> '27 Sep 2026, 20:44'."""
    try:
        return datetime.fromisoformat(timestamp).strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        return str(timestamp)

def _heading(title):
    print(f"\n{title}")

def _bullets(items, indent="  "):
    for item in items:
        print(f"{indent}- {item}")

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
    """Prints one incident for non-technical readers: what was logged, the
    severity level and action, then only the AI findings that apply to
    this incident. Sections with nothing useful to say are left out.
    Works with older records that are missing newer fields."""
    severity_levels = severity_levels or {}
    outcome_actions = outcome_actions or {}

    title = f"INCIDENT #{number}" if number else "INCIDENT REPORT"
    print("=" * _WIDTH)
    print(f"{title}  |  {record.get('location')}  |  {_format_time(record.get('timestamp'))}")
    print("=" * _WIDTH)

    # --- What was logged ---
    print(f"What happened:  {record.get('description')}")
    print(f"Reported by:    {record.get('reporter_role')}")
    print(f"Anyone injured: {'Yes' if record.get('injury') else 'No'}")
    hazard = record.get("hazard_type")
    print(f"Type of hazard: {_HAZARD_NAMES.get(hazard, hazard)}")

    # --- Severity and action ---
    outcome = record.get("outcome")
    severity = record.get("severity_estimate")
    if record.get("assessment_error"):
        _heading("SEVERITY: NOT ASSESSED")
        print("  The AI could not analyse this incident, so it was not scored.")
    else:
        level = severity_levels.get(severity)
        name = f" - {level[0].upper()}" if level else ""
        _heading(f"SEVERITY: {severity} out of 5{name}")
        if level:
            print(f"  {level[1]}")
        reasons = [r for r in record.get("severity_reasons") or []
                   if not r.startswith(("Base score", "Capped"))]
        if reasons:
            print("  Why:")
            _bullets(reasons, indent="    ")
        print(f"  Chance of it happening again: {record.get('likelihood_recurrence')}")

    _heading(f"ACTION: {_OUTCOME_NAMES.get(outcome, outcome)}")
    if outcome in outcome_actions:
        print(f"  {outcome_actions[outcome]}")

    # --- Weather: only when it was checked ---
    if record.get("weather_available"):
        _heading("WEATHER AT THE TIME")
        print(
            f"  {str(record.get('condition')).capitalize()}, {record.get('temperature_c')}°C, "
            f"{record.get('humidity_pct')}% humidity"
        )
        if record.get("monsoon_season") in _SEASON_TEXT:
            print(f"  {_SEASON_TEXT[record['monsoon_season']]}")

    # --- Known industry issue (web) ---
    if record.get("web_industry_context"):
        _heading("IS THIS A KNOWN ISSUE IN THE INDUSTRY?")
        print(f"  {record['web_industry_context']}")

    # --- Similar real incidents (web) ---
    if record.get("web_incidents"):
        _heading("SIMILAR INCIDENTS REPORTED ELSEWHERE")
        for i, item in enumerate(record["web_incidents"], start=1):
            print(f"  {i}. {item.get('summary')}")
            print(f"     Where / when:  {item.get('location')}, {item.get('date')}")
            print(f"     What was done: {item.get('action_taken')}")
            print(f"     Source:        {item.get('source_url')}")

    # --- Similar incidents on our own sites ---
    if record.get("similar_incidents"):
        _heading("SIMILAR INCIDENTS ON OUR OWN SITES")
        for i, item in enumerate(record["similar_incidents"], start=1):
            date = _format_time(item.get("timestamp"))[:11]
            outcome_name = _OUTCOME_NAMES.get(item.get("outcome"), item.get("outcome"))
            print(f"  {i}. \"{item.get('description')}\" - {item.get('location')}, {date}")
            print(f"     Action taken: {outcome_name}")

    # --- After-action review (AI) ---
    if record.get("review_likely_causes"):
        _heading("WHY IT LIKELY HAPPENED")
        _bullets(record["review_likely_causes"])
    if record.get("review_prevention_actions"):
        _heading("HOW TO PREVENT IT")
        _bullets(record["review_prevention_actions"])

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
        _heading("NOTE: SOME AI STEPS DID NOT WORK")
        _bullets(problems)
    print()
    
