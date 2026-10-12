import argparse
import logging

import ai_manager
import data_manager
import io_manager
import logic_manager

logger = logging.getLogger(__name__)

SEVERITY_LEVELS = logic_manager.SEVERITY_LEVELS
OUTCOME_ACTIONS = logic_manager.OUTCOME_ACTIONS


# Sets up logging, warns about a corrupt incidents file, loads the saved incidents and the AI cache.
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


# Fields copied from the hazard extraction onto the record (the validity fields are copied first).
_HAZARD_FLAG_KEYS = (
    "hazard_category", "injury_treatment", "equipment_mentioned", "elevated_places",
    "height_estimate_m", "ppe_status", "context_flags_error",
)


# The weather step: returns the weather fields to add, with enrichment_error set if the lookup failed.
def _weather_fields(record: dict) -> dict:
    fields = {
        "weather_available": False, "condition": None, "temperature_c": None,
        "humidity_pct": None, "precipitation_mm": None, "enrichment_error": None,
    }
    if not record.get("run_weather"):
        return fields
    try:
        weather = ai_manager.get_weather(record.get("timestamp"), record.get("location", ""))
    except Exception as error:
        logger.warning("Weather step failed: %s", error)
        weather = None
    if weather is None:
        fields["enrichment_error"] = "Weather data unavailable or invalid"
        return fields
    fields["weather_available"] = True
    for key in ("temperature_c", "humidity_pct", "precipitation_mm"):
        fields[key] = weather[key]
    return fields


# The similar-incidents step: returns its fields; a lookup that raises becomes similar_incidents_error.
def _similar_incident_fields(enriched: dict, history_records: list | None) -> dict:
    if not enriched.get("run_similar"):
        return {"similar_incidents_checked": False, "similar_incidents": None, "similar_incidents_error": None}
    try:
        found = ai_manager.find_similar_incidents(enriched, history_records or [], OUTCOME_ACTIONS)
    except Exception as error:
        logger.warning("Similar-incidents step failed: %s", error)
        return {
            "similar_incidents_checked": True, "similar_incidents": None,
            "similar_incidents_error": f"Similar-incidents lookup failed: {error}",
        }
    return {"similar_incidents_checked": True, **found}


# The web-search step: returns its fields; a search that raises becomes web_search_error.
def _web_search_fields(enriched: dict) -> dict:
    try:
        return ai_manager.search_web_for_similar_incidents(enriched)
    except Exception as error:
        logger.warning("Web search step failed: %s", error)
        return {"web_industry_context": None, "web_incidents": None, "web_search_error": str(error)}


# Lennart
# Runs the AI steps for one incident (hazard flags first, then weather, similar incidents and web search); never raises.
def enrich_record(record: dict, history_records: list | None = None) -> dict:
    enriched = dict(record)

    flags = ai_manager.extract_hazard_context_flags(str(record.get("description") or ""))
    enriched["is_valid_incident"] = flags.get("is_valid_incident")
    enriched["invalid_reason"] = flags.get("invalid_reason")
    if not logic_manager.screen_incident(enriched)["accepted"]:
        return enriched

    enriched.update(_weather_fields(record))
    for key in _HAZARD_FLAG_KEYS:
        enriched[key] = flags[key]
    enriched.update(_similar_incident_fields(enriched, history_records))
    enriched.update(_web_search_fields(enriched))
    return enriched


# The whole pipeline for one incident: enrich, score, decide the outcome, save; returns the record, or None if rejected.
def process_incident(incident: dict, records: list, interactive: bool = True) -> dict | None:
    with_context = logic_manager.derive_context(incident)
    with io_manager.show_loading("AI is analysing the incident"):
        enriched = enrich_record(with_context, records)
        screening = logic_manager.screen_incident(enriched)
        if screening["accepted"]:
            enriched = logic_manager.apply_weather(enriched)
            enriched = logic_manager.apply_lighting(enriched)
            enriched = logic_manager.apply_hazard_rules(enriched)
            enriched.update(ai_manager.generate_incident_review(enriched))
    if not screening["accepted"]:
        io_manager.display_message("Incident rejected: " + screening["reject_reason"])
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
    final_record["outcome"] = logic_manager.decide_outcome(assessed, history)

    saved = data_manager.save_record(final_record)
    while saved is False and interactive and io_manager.ask_retry_save():
        saved = data_manager.save_record(final_record)
    if saved is False:
        io_manager.display_message("Warning: could not save this incident to disk.")
    records.append(final_record)
    if not data_manager.save_ai_cache(ai_manager.export_response_cache()):
        io_manager.display_message("Warning: could not save the AI reply cache.")
    return final_record


# Menu option 1: asks for an incident, processes it, shows the report, and offers to re-enter it if rejected.
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


# Processes every valid incident in a JSON file without prompting; returns 0, or 1 if there was nothing valid.
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


# Menu option 2: reloads the saved incidents and shows the summary.
def show_summary() -> list:
    records = data_manager.load_records()
    io_manager.display_summary(records, SEVERITY_LEVELS, OUTCOME_ACTIONS)
    return records


# Menu option 3: asks for a location and a number of days and shows the incidents found.
def run_location_query(records: list) -> None:
    query = io_manager.get_location_query(data_manager.list_locations(records))
    if query is None:
        return
    location, days = query
    io_manager.display_query_results(data_manager.query_by_location(location, days))


# The interactive menu loop: log an incident, view the summary, query by location, exit.
def main() -> None:
    records = start_up()
    while True:
        choice = io_manager.get_menu_choice()
        if choice == "1":
            log_incident_flow(records)
        elif choice == "2":
            records = show_summary()
        elif choice == "3":
            run_location_query(records)
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
