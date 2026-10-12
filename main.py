import argparse
import logging

import ai_manager
import data_manager
import io_manager
import logic_manager

logger = logging.getLogger(__name__)

decide_outcome = logic_manager.decide_outcome
save_record = data_manager.save_record
generate_incident_review = ai_manager.generate_incident_review
SEVERITY_LEVELS = logic_manager.SEVERITY_LEVELS
OUTCOME_ACTIONS = logic_manager.OUTCOME_ACTIONS

derive_context = logic_manager.derive_context
apply_weather = logic_manager.apply_weather
apply_lighting = logic_manager.apply_lighting


# Lennart
def start_up() -> list:
    """Sets up logging, warns about a corrupt incidents file, loads saved incidents and the AI cache. Returns the saved incidents."""
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


def _weather_fields(record: dict) -> dict:
    """The weather step. Returns the weather fields to add to the record.
    Without run_weather, or when the lookup fails or raises, weather_available
    is False and enrichment_error says why. Never raises."""
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


def _similar_incident_fields(enriched: dict, history_records: list | None) -> dict:
    """The similar-incidents step. Returns its fields; a lookup that raises
    becomes similar_incidents_error instead of an exception."""
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


def _web_search_fields(enriched: dict) -> dict:
    """The web-search step, run for every incident: is this a known industry
    problem, and which similar real incidents were there. A search that
    raises becomes web_search_error instead of an exception."""
    try:
        return ai_manager.search_web_for_similar_incidents(enriched)
    except Exception as error:
        logger.warning("Web search step failed: %s", error)
        return {"web_industry_context": None, "web_incidents": None, "web_search_error": str(error)}


# Lennart
# The mandatory AI call runs first. If logic_manager rejects the incident we stop here, before
# the weather and web-search calls are spent on it; process_incident shows the reason.
def enrich_record(record: dict, history_records: list | None = None) -> dict:
    """Runs the AI steps for one incident and returns the enriched record. The mandatory hazard extraction goes first; a rejected incident is returned at once. Then the optional weather, similar-incident and web-search steps, each of which fails safe: an error is recorded on the record, never raised."""
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


# Lennart
# Returns None, and saves nothing, when logic_manager rejects the text as not a real safety incident.
# interactive=False (batch, scripts, Docker) never waits on input() after a failed save.
def process_incident(incident: dict, records: list, interactive: bool = True) -> dict | None:
    """The whole pipeline for one incident: derive context, AI enrichment, severity, outcome, save. Returns the saved record, or None if the incident was rejected. interactive=False never asks questions."""
    with_context = derive_context(incident)
    with io_manager.show_loading("AI is analysing the incident"):
        enriched = enrich_record(with_context, records)
        screening = logic_manager.screen_incident(enriched)
        if screening["accepted"]:
            enriched = logic_manager.apply_hazard_rules(apply_lighting(apply_weather(enriched)))
            enriched.update(generate_incident_review(enriched))
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
    """Menu option 1: asks for an incident, processes it and shows the result. Offers to re-enter it if it was rejected. Returns the record, or None if the user gave up."""
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
    """Processes every valid incident in a JSON file without prompting and prints a summary. Returns 0, or 1 if the file had no valid incidents."""
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
    """The interactive menu loop: log an incident, view the summary, query by location, exit."""
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
