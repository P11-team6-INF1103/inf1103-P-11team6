#Ren Xiang

import json


class JsonReply:
    # Turns AI reply text into checked JSON. Every reply goes through here before any field is used.

    _TYPE_CHECKS = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: isinstance(v, bool),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "null": lambda v: v is None,
    }

    # Parses a JSON reply after stripping any ```json fence; raises ValueError if it is not JSON.
    @staticmethod
    def parse(text: str) -> object:
        cleaned = str(text).strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned)

    # Pulls the first {...} object out of a reply that has other text around it, or returns None.
    @staticmethod
    def extract_object(text: str) -> dict | None:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start:end + 1])
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None

    # Checks parsed JSON against a schema (types, enums, required keys); raises ValueError on a mismatch.
    @classmethod
    def validate(cls, data: object, schema: dict, path: str = "response") -> None:
        allowed = schema.get("type")
        if allowed is not None:
            allowed = allowed if isinstance(allowed, list) else [allowed]
            if not any(cls._TYPE_CHECKS[t](data) for t in allowed):
                raise ValueError(f"{path}: expected {' or '.join(allowed)}, got {type(data).__name__}")
        if "enum" in schema and data not in schema["enum"]:
            raise ValueError(f"{path}: {data!r} is not one of {schema['enum']}")
        if isinstance(data, dict):
            for key in schema.get("required", []):
                if key not in data:
                    raise ValueError(f"{path}: missing required field '{key}'")
            for key, sub_schema in schema.get("properties", {}).items():
                if key in data:
                    cls.validate(data[key], sub_schema, f"{path}.{key}")
        if isinstance(data, list) and "items" in schema:
            for index, item in enumerate(data):
                cls.validate(item, schema["items"], f"{path}[{index}]")