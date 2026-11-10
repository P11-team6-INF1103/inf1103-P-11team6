# Darrel
import re
import shutil
import textwrap
from datetime import datetime

from models.incident import Incident


class ReportPrinter:
    _SEASON_TEXT = {
        "northeast_monsoon": "Northeast monsoon season (Dec to early Mar): wet and windy, heavy rain spells",
        "southwest_monsoon": "Southwest monsoon season (Jun to Sep): hot, early-morning squalls, possible haze",
        "inter_monsoon": "Inter-monsoon season (Apr-May, Oct-Nov): hot, afternoon thunderstorms and lightning",
    }
    HAZARD_NAMES = {
        "fall": "Slip, trip or fall (ground level)", "fall_from_height": "Fall from height",
        "electrical": "Electrical", "chemical": "Chemical", "vehicular": "Vehicle or mobile machinery",
        "struck_by_machinery": "Struck by machinery", "low_visibility": "Poor visibility",
        "other": "Other", "unassessed": "Not assessed",
    }
    OUTCOME_NAMES = {
        "stop_work_review": "STOP WORK - safety review", "photo_review": "CHECK PHOTO",
        "systemic_escalation": "ESCALATE to management", "log_only": "LOG ONLY",
        "pending_review": "NEEDS MANUAL REVIEW",
    }
    _OUTCOME_SHORT = {
        "stop_work_review": "STOP WORK", "photo_review": "CHECK PHOTO", "systemic_escalation": "ESCALATE",
        "log_only": "Log only", "pending_review": "MANUAL REVIEW",
    }
    # Plain-English text for each *_error field. Raw error text goes to the log, not the user.
    _PROBLEM_MESSAGES = (
        ("context_flags_error", "Hazard details could not be read automatically, so the incident was not scored."),
        ("enrichment_error", "Current weather could not be retrieved, so weather was not factored in."),
        ("web_search_error", "We couldn't look up similar incidents or industry information online right now."),
        ("similar_incidents_error", "We couldn't compare this with earlier incidents on our own sites right now."),
        ("photo_error", "The photo could not be analysed, so it was not used in the assessment."),
        ("review_error", "Causes and prevention advice couldn't be generated."),
    )
    _KEY_HINT = "An API key looks missing: check GEMINI_API_KEY and GROQ_API_KEY in the .env file."
    _WIDTH = 64
    _LABEL_WIDTH = 14

    # Keeps the severity and outcome descriptions the reports print.
    def __init__(self, severity_levels: dict, outcome_actions: dict) -> None:
        self._severity_levels = severity_levels
        self._outcome_actions = outcome_actions

    # Formats an ISO timestamp as '05 Oct 2026, 09:00', or returns it unchanged if unreadable.
    @staticmethod
    def format_time(timestamp: object) -> str:
        try:
            return datetime.fromisoformat(timestamp).strftime("%d %b %Y, %H:%M")
        except (TypeError, ValueError):
            return str(timestamp)

    # Report width: the terminal width kept between 60 and 90 columns.
    @staticmethod
    def _report_width() -> int:
        return min(max(shutil.get_terminal_size((100, 24)).columns, 60), 90)

    # Removes citation markers and swaps fancy hyphens and quotes for plain ones.
    @staticmethod
    def _clean(text: object) -> str:
        text = re.sub(r"【[^】]*】", "", str(text))
        text = text.translate({0x2011: "-", 0x2010: "-", 0x2019: "'", 0x2018: "'"})
        return re.sub(r"\s+([.,;])(?=\s|$)", r"\1", " ".join(text.split()))

    # Prints a section heading line.
    @staticmethod
    def _section(title: str, width: int) -> None:
        print(f"\n── {title} " + "─" * max(width - len(title) - 4, 3))

    # Prints 'label  value' with wrapped lines hanging under the value; a list prints one bullet per item.
    def _field(self, label: str, value: object, width: int, indent: int = 2, label_width: int = _LABEL_WIDTH) -> None:
        items = value if isinstance(value, list) else [value]
        bullets = isinstance(value, list)
        hang = " " * (indent + label_width)
        for position, item in enumerate(items):
            lead = " " * indent + label.ljust(label_width) if position == 0 else hang
            print(textwrap.fill(("- " if bullets else "") + self._clean(item), width,
                                initial_indent=lead, subsequent_indent=hang + ("  " if bullets else ""),
                                break_long_words=False, break_on_hyphens=False))

    # Plain-English messages for each *_error field on the incident.
    def friendly_problems(self, incident: Incident) -> list[str]:
        problems = [text for field, text in self._PROBLEM_MESSAGES if incident.get(field)]
        raw = " ".join(str(incident.get(field) or "") for field, _ in self._PROBLEM_MESSAGES)
        if "API_KEY" in raw:
            problems.append(self._KEY_HINT)
        return problems

    def _print_header(self, incident: Incident, width: int, number: int | None) -> None:
        title = f"INCIDENT #{number}" if number else "INCIDENT REPORT"
        print("═" * width)
        print(f" {title}   {incident.location}   {self.format_time(incident.timestamp)}")
        print("═" * width)
        hazard = incident.get("hazard_type")
        self._field("What happened", incident.description, width, indent=1, label_width=15)
        self._field("Reported by", incident.get("reporter_role"), width, indent=1, label_width=15)
        self._field("Anyone injured", "Yes" if incident.injury else "No", width, indent=1, label_width=15)
        self._field("Type of hazard", self.HAZARD_NAMES.get(hazard, hazard), width, indent=1, label_width=15)
        if incident.get("photo_file"):
            self._field("Photo", incident.get("photo_file"), width, indent=1, label_width=15)
        if incident.version > 1:
            note = f"Version {incident.version}" + (f" (copied from version {incident.get('reverted_from')})"
                                                    if incident.get("reverted_from") else " (edited)")
            self._field("Version", note, width, indent=1, label_width=15)

    def _print_severity(self, incident: Incident, width: int) -> None:
        outcome = incident.get("outcome")
        severity = incident.get("severity_estimate") or 0
        self._section("SEVERITY AND ACTION", width)
        if incident.get("assessment_error"):
            self._field("Severity", "NOT ASSESSED - the AI could not analyse this incident.", width)
        else:
            level = self._severity_levels.get(severity)
            name = f"  {level[0].upper()}" if level else ""
            self._field("Severity", f"{'█' * severity}{'░' * (5 - severity)}  {severity}/5{name}", width)
            if level:
                self._field("", level[1], width)
            if incident.get("severity_reasons"):
                self._field("Why", incident.get("severity_reasons"), width)
            self._field("Could recur", incident.get("likelihood_recurrence"), width)
        self._field("Action", self.OUTCOME_NAMES.get(outcome, outcome), width)
        if outcome in self._outcome_actions:
            self._field("", self._outcome_actions[outcome], width)

    # New in Part 2: what the AI saw in the uploaded photo and how it changed the assessment.
    def _print_photo(self, incident: Incident, width: int) -> None:
        if not incident.get("photo_analysed"):
            return
        self._section("WHAT THE PHOTO SHOWS", width)
        self._field("Summary", incident.get("photo_summary"), width)
        if incident.get("photo_hazards_seen"):
            self._field("Hazards seen", incident.get("photo_hazards_seen"), width)
        if incident.get("photo_matches_description") is False:
            self._field("Warning", "The photo does not seem to match the description.", width)
        if incident.get("photo_evidence_used"):
            self._field("Used in score", incident.get("photo_evidence_used"), width)

    def _print_weather(self, incident: Incident, width: int) -> None:
        if not incident.get("weather_available"):
            return
        self._section("WEATHER AT THE TIME", width)
        self._field("Conditions", f"{str(incident.get('condition')).capitalize()}, "
                    f"{incident.get('temperature_c')}°C, {incident.get('humidity_pct')}% humidity", width)
        if incident.get("monsoon_season") in self._SEASON_TEXT:
            self._field("Season", self._SEASON_TEXT[incident.get("monsoon_season")], width)

    def _print_web(self, incident: Incident, width: int) -> None:
        if incident.get("web_industry_context"):
            self._section("IS THIS A KNOWN ISSUE IN THE INDUSTRY?", width)
            self._field("", incident.get("web_industry_context"), width, label_width=0)
        web = incident.get("web_incidents") or []
        if web:
            self._section("SIMILAR INCIDENTS REPORTED ELSEWHERE", width)
        for i, item in enumerate(web, start=1):
            print(textwrap.fill(self._clean(item.get("summary")), width, initial_indent=f"  {i}. ",
                                subsequent_indent="     ", break_long_words=False))
            self._field("Where / when", f"{item.get('location')}, {item.get('date')}", width, indent=5)
            self._field("What was done", item.get("action_taken"), width, indent=5)
            self._field("Source", item.get("source_url"), width, indent=5)

    def _print_similar(self, incident: Incident, width: int) -> None:
        similar = incident.get("similar_incidents") or []
        if similar:
            self._section("SIMILAR INCIDENTS ON OUR OWN SITES", width)
        for i, item in enumerate(similar, start=1):
            date = self.format_time(item.get("timestamp"))[:11]
            print(textwrap.fill(f"\"{item.get('description')}\" - {item.get('location')}, {date}", width,
                                initial_indent=f"  {i}. ", subsequent_indent="     ", break_long_words=False))
            self._field("Action taken", self.OUTCOME_NAMES.get(item.get("outcome"), item.get("outcome")),
                        width, indent=5)

    def _print_review(self, incident: Incident, width: int) -> None:
        if incident.get("review_likely_causes"):
            self._section("WHY IT LIKELY HAPPENED", width)
            self._field("", incident.get("review_likely_causes"), width, label_width=0)
        if incident.get("review_prevention_actions"):
            self._section("HOW TO PREVENT IT", width)
            self._field("", incident.get("review_prevention_actions"), width, label_width=0)

    def _print_problems(self, incident: Incident, width: int) -> None:
        problems = self.friendly_problems(incident)
        if problems:
            self._section("NOTE: SOME AI STEPS DID NOT WORK", width)
            self._field("", problems, width, label_width=0)

    # Prints the full report for one incident, one section after another, leaving out empty sections.
    def print_incident(self, incident: Incident, number: int | None = None) -> None:
        width = self._report_width()
        print()
        self._print_header(incident, width, number)
        self._print_severity(incident, width)
        self._print_photo(incident, width)
        self._print_weather(incident, width)
        self._print_web(incident, width)
        self._print_similar(incident, width)
        self._print_review(incident, width)
        self._print_problems(incident, width)
        print("═" * width)
        print()

    # 'level/5 Name' for an incident, or 'not assessed'.
    def _severity_text(self, incident: Incident) -> str:
        if incident.get("assessment_error"):
            return "not assessed"
        severity = incident.get("severity_estimate") or 0
        level = self._severity_levels.get(severity)
        return f"{severity}/5" + (f" {level[0]}" if level else "")

    # (label, value) pairs for what a version says: the four typed fields, the photo and the AI insight.
    def _version_values(self, data: Incident | dict) -> list[tuple[str, str]]:
        get = data.get
        hazard = get("hazard_type")
        return [
            ("What happened", str(get("description"))), ("Location", str(get("location"))),
            ("Reported by", str(get("reporter_role"))), ("Anyone injured", "Yes" if get("injury") else "No"),
            ("Photo", get("photo_file") or "none"),
            ("Hazard type", self.HAZARD_NAMES.get(hazard, hazard)),
            ("Severity", self._severity_text(data) if isinstance(data, Incident)
             else self._severity_text(Incident.from_dict(data))),
            ("Action", self.OUTCOME_NAMES.get(get("outcome"), get("outcome"))),
        ]

    # Prints the old and new value of everything that differs between two versions, then the unchanged AI insight.
    def print_comparison(self, old: Incident | dict, new: Incident) -> None:
        width = self._report_width()
        self._section("WHAT CHANGED (OLD -> NEW)", width)
        same = []
        for (label, before), (_, after) in zip(self._version_values(old), self._version_values(new)):
            if before == after:
                same.append(label)
            else:
                self._field(label, f"{before} -> {after}", width)
        if same:
            self._field("Unchanged", ", ".join(same), width)

    # Prints every version of an incident, newest last, in one line each.
    def print_history(self, incident: Incident) -> None:
        width = self._report_width()
        self._section(f"VERSIONS ({incident.version})", width)
        versions = incident.history + [incident.snapshot()]
        for data in versions:
            version = Incident.from_dict(data)
            tag = "  <- current" if data["version"] == incident.version else ""
            how = f" (copied from v{data['reverted_from']})" if data.get("reverted_from") else ""
            outcome = data.get("outcome")
            print(textwrap.fill(
                f"v{data['version']}{how}: severity {self._severity_text(version)}, "
                f"{self._OUTCOME_SHORT.get(outcome, outcome)}{tag}",
                width, initial_indent="  ", subsequent_indent="      "))
            print(textwrap.fill(f"\"{data.get('description')}\" - {data.get('location')}", width,
                                initial_indent="      ", subsequent_indent="      "))

    # Prints a boxed table; long cells wrap inside their column.
    @staticmethod
    def _print_table(headers: list, rows: list, widths: list) -> None:
        def border(left: str, mid: str, right: str) -> str:
            return left + mid.join("─" * (w + 2) for w in widths) + right
        print(border("┌", "┬", "┐"))
        all_rows = [headers] + rows
        for index, row in enumerate(all_rows):
            cells = [textwrap.wrap(str(cell), w) or [""] for cell, w in zip(row, widths)]
            for i in range(max(len(c) for c in cells)):
                print("│ " + " │ ".join((c[i] if i < len(c) else "").ljust(w) for c, w in zip(cells, widths)) + " │")
            if index < len(all_rows) - 1:
                print(border("├", "┼", "┤"))
        print(border("└", "┴", "┘"))

    # One table row per incident, with manual reviews first and then the most severe.
    def _summary_rows(self, records: list[Incident]) -> list[list]:
        ordered = sorted(enumerate(records, start=1),
                         key=lambda pair: (pair[1].get("outcome") in ("pending_review", "photo_review"),
                                           pair[1].get("severity_estimate") or 0),
                         reverse=True)
        rows = []
        for number, incident in ordered:
            hazard, outcome = incident.get("hazard_type"), incident.get("outcome")
            rows.append([
                number, self.format_time(incident.timestamp).replace(",", ""), incident.location,
                self.HAZARD_NAMES.get(hazard, hazard),
                "-" if incident.get("assessment_error") else incident.get("severity_estimate"),
                self._OUTCOME_SHORT.get(outcome, outcome),
                ("[photo] " if incident.get("photo_file") else "") + incident.description,
            ])
        return rows

    # Prints counts by outcome and hazard, then a table of every incident.
    def print_summary(self, records: list[Incident]) -> None:
        print("\n" + "#" * self._WIDTH)
        print("INCIDENT SUMMARY / AFTER-ACTION REVIEW")
        print("#" * self._WIDTH)
        if not records:
            print("No incidents logged yet.")
            return
        outcomes, hazards = {}, {}
        for incident in records:
            outcome = self.OUTCOME_NAMES.get(incident.get("outcome"), incident.get("outcome"))
            hazard = self.HAZARD_NAMES.get(incident.get("hazard_type"), incident.get("hazard_type"))
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            hazards[hazard] = hazards.get(hazard, 0) + 1
        print(f"Total incidents: {len(records)}")
        print(f"With a photo: {sum(1 for r in records if r.get('photo_file'))}")
        print("By action: " + ", ".join(f"{k} ({v})" for k, v in sorted(outcomes.items(), key=str)))
        print("By hazard: " + ", ".join(f"{k} ({v})" for k, v in sorted(hazards.items(), key=str)))
        spare = max(shutil.get_terminal_size((100, 24)).columns, 100) - (3 + 17 + 18 + 3 + 13) - 22
        location_width = max(spare * 2 // 5, 12)
        print("\nOVERVIEW (manual reviews first, then most severe)")
        self._print_table(["#", "When", "Location", "Hazard", "Sev", "Action", "What happened"],
                          self._summary_rows(records),
                          [3, 17, location_width, 18, 3, 13, max(spare - location_width, 20)])

    # Prints what each severity level means.
    def print_severity_guide(self) -> None:
        print("\nWHAT THE SEVERITY LEVELS MEAN")
        for level in sorted(self._severity_levels):
            name, meaning = self._severity_levels[level]
            print(f"  {level} {name:<9} {meaning}")
