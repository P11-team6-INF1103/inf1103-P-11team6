import ai_manager
import data_manager
<<<<<<< HEAD


def get_incident_input():
    return {
        "description": "Worker slipped near wet scaffolding",
        "location": "Site A - Block 3",
        "reporter_role": "site_supervisor",
        "injury": False,
        "timestamp": "2026-09-28T09:00:00",
    }


def get_menu_choice():
    return input("1) Log incident  2) View summary  3) Query location  4) Exit\n> ").strip()


def display_outcome(record):
    print(record)


def display_summary(records):
    for record in records:
        print(record)


def assess_severity(record, history):
    result = dict(record)
    result["hazard_type"] = record.get("hazard_category") or "unassessed"
    result["severity_estimate"] = 1
    result["likelihood_recurrence"] = "low"
    result["severity_reasons"] = []
    result["assessment_error"] = None
    return result


def decide_outcome(record, history):
    return "log_only"


def query_by_location(location, days):
    return []


def save_record(record):
    pass
=======
import io_manager
import logic_manager
import trial

# Real functions are used wherever a teammate's module already has them.
# Anything not merged yet falls back to the matching stand-in in trial.py.
decide_outcome = getattr(logic_manager, "decide_outcome", trial.fake_decide_outcome)
save_record = getattr(data_manager, "save_record", trial.fake_save_record)
SEVERITY_LEVELS = getattr(logic_manager, "SEVERITY_LEVELS", None)
OUTCOME_ACTIONS = getattr(logic_manager, "OUTCOME_ACTIONS", None)
>>>>>>> origin/main


# Lennart
def log_incident_flow():
<<<<<<< HEAD
    incident = get_incident_input()
    enriched = ai_manager.enrich_record(incident)
    history = query_by_location(enriched.get("location", ""), 30)
    assessed = assess_severity(enriched, history)
    final_record = dict(assessed)
    final_record["outcome"] = decide_outcome(assessed, history)
    save_record(final_record)
    display_outcome(final_record)
=======
    incident = io_manager.get_incident_input()
    enriched = ai_manager.enrich_record(incident)
    history = data_manager.query_by_location(enriched.get("location", ""), 30)
    assessed = logic_manager.assess_severity(enriched, enriched, history)
    final_record = dict(assessed)
    final_record["outcome"] = decide_outcome(assessed, history)
    save_record(final_record)
    io_manager.display_outcome(final_record, SEVERITY_LEVELS, OUTCOME_ACTIONS)
>>>>>>> origin/main
    return final_record


# Lennart
def main():
    while True:
<<<<<<< HEAD
        choice = get_menu_choice()
=======
        choice = io_manager.get_menu_choice()
>>>>>>> origin/main
        if choice == "1":
            log_incident_flow()
        elif choice == "2":
            records = data_manager.load_records()
<<<<<<< HEAD
            display_summary(records)
=======
            io_manager.display_summary(records, SEVERITY_LEVELS, OUTCOME_ACTIONS)
>>>>>>> origin/main
        elif choice == "3":
            location = input("Location to search: ").strip()
            days_input = input("How many days back? ").strip()
            days = int(days_input) if days_input.isdigit() else 30
<<<<<<< HEAD
            results = query_by_location(location, days)
=======
            results = data_manager.query_by_location(location, days)
>>>>>>> origin/main
            if not results:
                print("No matching incidents found.")
            for item in results:
                print(f"[{item['timestamp']}] {item['location']} -> {item['outcome']}")
        elif choice == "4":
            print("Goodbye.")
            break


if __name__ == "__main__":
    main()
