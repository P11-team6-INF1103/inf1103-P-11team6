import ai_manager
import data_manager


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


# Lennart
def log_incident_flow():
    incident = get_incident_input()
    enriched = ai_manager.enrich_record(incident)
    history = query_by_location(enriched.get("location", ""), 30)
    assessed = assess_severity(enriched, history)
    final_record = dict(assessed)
    final_record["outcome"] = decide_outcome(assessed, history)
    save_record(final_record)
    display_outcome(final_record)
    return final_record


# Lennart
def main():
    while True:
        choice = get_menu_choice()
        if choice == "1":
            log_incident_flow()
        elif choice == "2":
            records = data_manager.load_records()
            display_summary(records)
        elif choice == "3":
            location = input("Location to search: ").strip()
            days_input = input("How many days back? ").strip()
            days = int(days_input) if days_input.isdigit() else 30
            results = query_by_location(location, days)
            if not results:
                print("No matching incidents found.")
            for item in results:
                print(f"[{item['timestamp']}] {item['location']} -> {item['outcome']}")
        elif choice == "4":
            print("Goodbye.")
            break


if __name__ == "__main__":
    main()
