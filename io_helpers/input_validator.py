# Sufi
import os
import re
from datetime import datetime


class InputValidator:
    # Checks for typed text. Each check_* returns an error message, or None when the text is fine.
    MIN_DESCRIPTION = 10
    MAX_DESCRIPTION = 500
    MAX_LOCATION = 100
    MAX_ROLE = 40
    _LOCATION_CHARS = re.compile(r"^[A-Za-z0-9 \-,./()#]+$")
    _ROLE_CHARS = re.compile(r"^[A-Za-z _/\-]+$")

    # Collapses whitespace and drops unprintable characters.
    @staticmethod
    def sanitise(text: object) -> str:
        text = " ".join(str(text).split())
        return "".join(ch for ch in text if ch.isprintable())

    # Turns a typed or dragged-in file path into a plain path (removes quotes and '\ ' escapes).
    @staticmethod
    def clean_path(text: str) -> str:
        path = text.strip()
        if len(path) >= 2 and path[0] == path[-1] and path[0] in "'\"":
            path = path[1:-1]
        return os.path.expanduser(path.replace("\\ ", " "))

    @classmethod
    def check_description(cls, text: str) -> str | None:
        if text == "":
            return "Description cannot be empty."
        if len(text) < cls.MIN_DESCRIPTION:
            return f"Description is too short. Say what happened in at least {cls.MIN_DESCRIPTION} characters."
        if len(text) > cls.MAX_DESCRIPTION:
            return f"Description is too long (maximum {cls.MAX_DESCRIPTION} characters)."
        no_spaces = text.replace(" ", "")
        if sum(ch.isalpha() for ch in no_spaces) < len(no_spaces) / 2:
            return "Description must be mostly words, not symbols or numbers."
        if len(re.findall(r"[A-Za-z]{2,}", text)) < 2:
            return "Description must contain at least 2 real words."
        if len({ch for ch in text.lower() if ch.isalpha()}) < 4:
            return "Description looks like repeated characters. Describe the incident in words."
        return None

    @classmethod
    def check_location(cls, text: str) -> str | None:
        if text == "":
            return "Location cannot be empty."
        if len(text) > cls.MAX_LOCATION:
            return f"Location is too long (maximum {cls.MAX_LOCATION} characters)."
        if not cls._LOCATION_CHARS.match(text):
            return "Location may only contain letters, digits, spaces and - , . / ( ) #"
        if not re.search(r"[A-Za-z]", text):
            return "Location must contain at least one letter, e.g. 'Site A - Block 3'."
        return None

    @classmethod
    def check_role(cls, text: str) -> str | None:
        if text == "":
            return "Role cannot be empty."
        if len(text) < 2:
            return "Role is too short, e.g. 'site_supervisor'."
        if len(text) > cls.MAX_ROLE:
            return f"Role is too long (maximum {cls.MAX_ROLE} characters)."
        if not cls._ROLE_CHARS.match(text):
            return "Role may only contain letters, spaces, _ - and /"
        return None

    # Checks the incident fields sent by a batch file or the web form, with the same rules as typed input.
    # Returns (clean fields for Incident(...), problems); the fields are only usable when problems is empty.
    @classmethod
    def validate_fields(cls, item: dict) -> tuple[dict, list[str]]:
        fields, bad = {}, []
        for key, check in (("description", cls.check_description), ("location", cls.check_location),
                           ("reporter_role", cls.check_role)):
            value = cls.sanitise(item[key]) if isinstance(item.get(key), str) else None
            error = "missing" if value is None else check(value)
            if error:
                bad.append(f"{key} ({error})")
            fields[key] = value
        injury = item.get("injury")
        if isinstance(injury, str) and injury.strip().lower() in ("yes", "y", "no", "n", "true", "false"):
            injury = injury.strip().lower() in ("yes", "y", "true")
        if not isinstance(injury, bool):
            bad.append("injury (true/false)")
        fields["injury"] = injury
        timestamp = item.get("timestamp") or datetime.now().isoformat()
        try:
            datetime.fromisoformat(timestamp)
        except (TypeError, ValueError):
            bad.append("timestamp (ISO format)")
        fields["timestamp"] = timestamp
        return fields, bad
