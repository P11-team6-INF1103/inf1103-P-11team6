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
