# Sufi

import math

from site_plan.element_kind import ElementKind
from site_plan.element_kinds import ELEMENT_KINDS


class SiteElement:
    # One labelled thing on the plan, in metres from the top-left corner of the site.
    MAX_NAME = 60

    # A finite number as a float, or None for anything else (text, booleans, NaN, infinity).
    @staticmethod
    def parse_number(value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
        return float(value)

    def __init__(self, kind: ElementKind, name: str, x: float, y: float, w: float, d: float,
                 radius_m: float | None = None, aliases: list[str] | None = None) -> None:
        self._kind = kind
        self._name = name
        self._rect = (x, y, w, d)
        self._radius_m = radius_m
        self._aliases = list(aliases or [])

    @property
    def kind(self) -> ElementKind:
        return self._kind

    @property
    def name(self) -> str:
        return self._name

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return self._rect

    @property
    def aliases(self) -> list[str]:
        return list(self._aliases)

    # True if a location typed on an incident ("Block B scaffold") refers to this element.
    def matches(self, location: str) -> bool:
        text = location.strip().lower()
        if not text:
            return False
        names = [self._name.lower()] + [a.lower() for a in self._aliases]
        return any(n == text or (len(n) >= 3 and (n in text or text in n)) for n in names)

    # Builds an element from one dict (AI reply or user file), fixing small problems and noting them in warnings.
    # Returns None if the dict cannot be used at all.
    @classmethod
    def from_dict(cls, raw: object, site_w: float, site_d: float, warnings: list[str]) -> "SiteElement | None":
        if not isinstance(raw, dict):
            warnings.append("An element that was not an object was skipped.")
            return None
        name = str(raw.get("name") or "").strip()[:cls.MAX_NAME]
        kind = ELEMENT_KINDS.get(str(raw.get("type")))
        if kind is None:
            kind = ELEMENT_KINDS["zone"]
            warnings.append(f"'{name or '?'}' has an unknown type, so it is shown as an area.")
        x, y, w, d = (SiteElement.parse_number(raw.get(k)) for k in ("x", "y", "w", "d"))
        if None in (x, y, w, d):
            warnings.append(f"'{name or kind.label}' has no usable position or size and was skipped.")
            return None
        size = kind.min_size()
        w, d = max(w, size), max(d, size)
        if w > site_w or d > site_d:
            warnings.append(f"'{name or kind.label}' was bigger than the site and was shrunk to fit.")
            w, d = min(w, site_w), min(d, site_d)
        x = min(max(x, 0.0), site_w - w)
        y = min(max(y, 0.0), site_d - d)
        radius = SiteElement.parse_number(raw.get("radius_m"))
        if kind.key == "tower_crane" and (radius is None or not 5 <= radius <= 100):
            radius = 30.0
        aliases = raw.get("aliases") if isinstance(raw.get("aliases"), list) else []
        aliases = [str(a).strip()[:cls.MAX_NAME] for a in aliases if str(a).strip()][:8]
        return cls(kind, name or kind.label, round(x, 1), round(y, 1), round(w, 1), round(d, 1),
                   radius if kind.key == "tower_crane" else None, aliases)

    def to_dict(self, element_id: str) -> dict:
        x, y, w, d = self._rect
        data = {"id": element_id, "type": self._kind.key, "name": self._name, "x": x, "y": y, "w": w, "d": d,
                "aliases": list(self._aliases)}
        if self._radius_m is not None:
            data["radius_m"] = self._radius_m
        return data
