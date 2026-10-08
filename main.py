import argparse
import json
import logging

import ai_manager
import data_manager
import io_manager
import logic_manager
import trial

# Real functions are used wherever a teammate's module already has them.
# Anything not merged yet falls back to the matching stand-in in fakes.py.
decide_outcome = getattr(logic_manager, "decide_outcome", trial.fake_decide_outcome)
save_record = getattr(data_manager, "save_record", trial.fake_save_record)
SEVERITY_LEVELS = getattr(logic_manager, "SEVERITY_LEVELS", None)
OUTCOME_ACTIONS = getattr(logic_manager, "OUTCOME_ACTIONS", None)
derive_context = getattr(logic_manager, "derive_context", dict)
apply_lighting = getattr(logic_manager, "apply_lighting", dict)
generate_incident_review = getattr(ai_manager, "generate_incident_review", lambda record: {})


# Lennart
def start_up():
    log_path = data_manager.get_log_path()
    if log_path:
        logging.basicConfig(
            filename=log_path, level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    problem = data_manager.check_records_file()
    if problem:
        print(f"Warning: {problem}. Starting with no saved incidents.")
    records = data_manager.load_records()
    ai_manager.load_response_cache(data_manager.load_ai_cache())
    print(f"Loaded {len(records)} saved incident(s).")
    return records


# Lennart
def process_incident(incident, records):
    with_context = derive_context(incident)
    enriched = ai_manager.enrich_record(with_context, records)
    enriched = apply_lighting(enriched)
    enriched.update(generate_incident_review(enriched))

    history = data_manager.query_by_location(
        enriched.get("location", ""), 30, as_of=enriched.get("timestamp"), records=records
    )
    weather_data = {
        "weather_available": enriched.get("weather_available"),
        "condition": enriched.get("condition"),
        "temperature_c": enriched.get("temperature_c"),
        "humidity_pct": enriched.get("humidity_pct"),
    }
    assessed = logic_manager.assess_severity(enriched, weather_data, history)

    final_record = dict(assessed)
    final_record["outcome"] = decide_outcome(assessed, history)

    if save_record(final_record) is False:
        print("Warning: could not save this incident to disk.")
    records.append(final_record)
    if not data_manager.save_ai_cache(ai_manager.export_response_cache()):
        print("Warning: could not save the AI reply cache.")
    return final_record


# Lennart
def log_incident_flow(records):
    incident = io_manager.get_incident_input()
    final_record = process_incident(incident, records)
    io_manager.display_outcome(final_record, SEVERITY_LEVELS, OUTCOME_ACTIONS)
    return final_record


# Lennart
def main():
    records = start_up()
    while True:
        choice = io_manager.get_menu_choice()
        if choice == "1":
            log_incident_flow(records)
        elif choice == "2":
            records = data_manager.load_records()
            io_manager.display_summary(records, SEVERITY_LEVELS, OUTCOME_ACTIONS)
        elif choice == "3":
            location = input("Location to search: ").strip()
            days_input = input("How many days back? ").strip()
            days = int(days_input) if days_input.isdigit() else 30
            results = data_manager.query_by_location(location, days)
            if not results:
                print("No matching incidents found.")
            for item in results:
                print(f"[{item['timestamp']}] {item['location']} -> {item['outcome']}")
        elif choice == "4":
            print("Goodbye.")
            break


if __name__ == "__main__":
    main()
