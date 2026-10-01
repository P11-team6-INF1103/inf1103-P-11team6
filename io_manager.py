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
