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
