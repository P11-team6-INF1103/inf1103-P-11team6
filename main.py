import argparse
import logging

import ai_manager
import data_manager
import io_manager
import logic_manager

decide_outcome = logic_manager.decide_outcome
save_record = data_manager.save_record
generate_incident_review = ai_manager.generate_incident_review
SEVERITY_LEVELS = logic_manager.SEVERITY_LEVELS
OUTCOME_ACTIONS = logic_manager.OUTCOME_ACTIONS

# Not written yet (Darrel). Until they land, each step passes the record through unchanged.
derive_context = logic_manager.derive_context
apply_weather = logic_manager.apply_weather
apply_lighting = logic_manager.apply_lighting


# Lennart
def start_up() -> list:
    log_path = data_manager.get_log_path()
    if log_path:
        logging.basicConfig(
            filename=log_path, level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    problem = data_manager.check_records_file()
    if problem:
        io_manager.display_message(f"Warning: {problem}. Starting with no saved incidents.")
    records = data_manager.load_records()
    ai_manager.load_response_cache(data_manager.load_ai_cache())
    io_manager.display_message(f"Loaded {len(records)} saved incident(s).")
    return records


# Lennart
# The mandatory AI call runs first. If it says this is not a real safety incident we stop
# here, before the weather and web-search calls are spent on it; process_incident rejects it.
def enrich_record(record: dict, history_records: list | None = None) -> dict:
    enriched = dict(record)

    flags = ai_manager.extract_hazard_context_flags(record.get("description", ""))
    enriched["is_valid_incident"] = flags.get("is_valid_incident", True)
    enriched["invalid_reason"] = flags.get("invalid_reason")
    if not enriched["is_valid_incident"]:
        return enriched

    weather_relevant = bool(record.get("weather_relevant"))

    enriched["weather_available"] = False
    enriched["condition"] = None
    enriched["temperature_c"] = None
    enriched["humidity_pct"] = None
    enriched["precipitation_mm"] = None
    enriched["enrichment_error"] = None
    if weather_relevant:
        weather = ai_manager.get_weather(record.get("timestamp"), record.get("location", ""))
        if weather is not None:
            enriched["weather_available"] = True
            enriched["temperature_c"] = weather["temperature_c"]
            enriched["humidity_pct"] = weather["humidity_pct"]
            enriched["precipitation_mm"] = weather["precipitation_mm"]
        else:
            enriched["enrichment_error"] = "Weather data unavailable or invalid"

    enriched["hazard_category"] = flags["hazard_category"]
    enriched["injury_severity"] = flags["injury_severity"]
    enriched["working_at_height"] = flags["working_at_height"]
    enriched["height_estimate_m"] = flags["height_estimate_m"]
    enriched["heavy_machinery_present"] = flags["heavy_machinery_present"]
    enriched["ppe_status"] = flags["ppe_status"]
    enriched["context_flags_error"] = flags["context_flags_error"]

    # Similar incidents — mutually exclusive with the weather call.
    if not weather_relevant:
        enriched["similar_incidents_checked"] = True
        enriched.update(ai_manager.find_similar_incidents(enriched, history_records or []))
    else:
        enriched["similar_incidents_checked"] = False
        enriched["similar_incidents"] = None
        enriched["similar_incidents_error"] = None

    # Web search — every incident: is this a known industry problem, and
    # similar real incidents with what was done about them.
    enriched.update(ai_manager.search_web_for_similar_incidents(enriched))

    return enriched


# Lennart
# Returns None, and saves nothing, when the AI says the text is not a real safety incident.
# interactive=False (batch, scripts, Docker) never waits on input() after a failed save.
def process_incident(incident: dict, records: list, interactive: bool = True) -> dict | None:
    with_context = derive_context(incident)
    with io_manager.show_loading("AI is analysing the incident"):
        enriched = enrich_record(with_context, records)
        is_valid = enriched.get("is_valid_incident", True)
        if is_valid:
            enriched = apply_lighting(apply_weather(enriched))
            enriched.update(generate_incident_review(enriched))
    if not is_valid:
        io_manager.display_message(
            "Incident rejected: " + str(enriched.get("invalid_reason") or "not a workplace safety incident")
        )
        return None

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

    saved = save_record(final_record)
    while saved is False and interactive and io_manager.ask_retry_save():
        saved = save_record(final_record)
    if saved is False:
        io_manager.display_message("Warning: could not save this incident to disk.")
    records.append(final_record)
    if not data_manager.save_ai_cache(ai_manager.export_response_cache()):
        io_manager.display_message("Warning: could not save the AI reply cache.")
    return final_record


# Lennart
# If the AI rejects the incident, asks whether to enter it again instead of showing a report.
def log_incident_flow(records: list) -> dict | None:
    while True:
        incident = io_manager.get_incident_input()
        final_record = process_incident(incident, records)
        if final_record is not None:
            break
        if not io_manager.ask_try_again():
            return None
    io_manager.display_outcome(final_record, SEVERITY_LEVELS, OUTCOME_ACTIONS)
    return final_record


# Lennart
def run_batch(path: str) -> int:
    incidents, problems = io_manager.read_incident_file(path)
    for problem in problems:
        io_manager.display_message(f"Skipped: {problem}")
    if not incidents:
        io_manager.display_message("No valid incidents to process.")
        return 1

    records = start_up()
    for incident in incidents:
        final_record = process_incident(incident, records, interactive=False)
        if final_record is None:
            continue
        io_manager.display_outcome(final_record, SEVERITY_LEVELS, OUTCOME_ACTIONS)
    io_manager.display_summary(records, SEVERITY_LEVELS, OUTCOME_ACTIONS, interactive=False)
    return 0


# Lennart
def main() -> None:
    records = start_up()
    while True:
        choice = io_manager.get_menu_choice()
        if choice == "1":
            log_incident_flow(records)
        elif choice == "2":
            records = data_manager.load_records()
            io_manager.display_summary(records, SEVERITY_LEVELS, OUTCOME_ACTIONS)
        elif choice == "3":
            query = io_manager.get_location_query(data_manager.list_locations(records))
            if query is None:
                continue
            location, days = query
            io_manager.display_query_results(data_manager.query_by_location(location, days))
        elif choice == "4":
            io_manager.display_message("Goodbye.")
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Workplace Safety Incident Triage System")
    parser.add_argument("--batch", metavar="FILE", help="process the incidents in FILE (JSON) and exit")
    arguments = parser.parse_args()
    if arguments.batch:
        raise SystemExit(run_batch(arguments.batch))
    main()
