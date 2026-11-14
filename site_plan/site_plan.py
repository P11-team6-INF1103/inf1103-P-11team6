# Sufi

from site_plan.site_element import SiteElement
from site_plan.site_plan_error import SitePlanError


class SitePlan:
    # A whole site: its boundary and the elements on it. It owns its elements (composition): they have no
    # meaning outside one plan.
    MIN_SIDE_M = 20.0
    MAX_SIDE_M = 2000.0
    MAX_ELEMENTS = 80

    def __init__(self, name: str, width_m: float, depth_m: float, elements: list[SiteElement] | None = None,
                 warnings: list[str] | None = None) -> None:
        self._name = name
        self._width_m = width_m
        self._depth_m = depth_m
        self._elements = list(elements or [])
        self._warnings = list(warnings or [])

    @property
    def name(self) -> str:
        return self._name

    @property
    def width_m(self) -> float:
        return self._width_m

    @property
    def depth_m(self) -> float:
        return self._depth_m

    @property
    def elements(self) -> list[SiteElement]:
        return list(self._elements)

    # Problems that were fixed or skipped while the plan was built; shown to the user, never saved.
    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    # Builds a plan from a dict (a saved plan, a filled-in template, or converted AI output).
    # Raises SitePlanError if the site itself is unusable; bad elements are fixed or skipped with a warning.
    @classmethod
    def from_dict(cls, data: object) -> "SitePlan":
        if not isinstance(data, dict):
            raise SitePlanError("The site plan must be a JSON object.")
        width, depth = SiteElement.parse_number(data.get("width_m")), SiteElement.parse_number(data.get("depth_m"))
        for label, value in (("width_m", width), ("depth_m", depth)):
            if value is None or not cls.MIN_SIDE_M <= value <= cls.MAX_SIDE_M:
                raise SitePlanError(f"{label} must be a number from {cls.MIN_SIDE_M:g} to {cls.MAX_SIDE_M:g} metres.")
        raw_elements = data.get("elements")
        if not isinstance(raw_elements, list):
            raise SitePlanError("elements must be a list.")
        warnings: list[str] = []
        if len(raw_elements) > cls.MAX_ELEMENTS:
            warnings.append(f"Only the first {cls.MAX_ELEMENTS} elements were kept.")
        elements = [e for e in (SiteElement.from_dict(r, width, depth, warnings) for r in raw_elements[:cls.MAX_ELEMENTS])
                    if e is not None]
        name = str(data.get("name") or "").strip()[:SiteElement.MAX_NAME] or "Construction site"
        return cls(name, round(width, 1), round(depth, 1), elements, warnings)

    def to_dict(self) -> dict:
        return {"name": self._name, "width_m": self._width_m, "depth_m": self._depth_m,
                "elements": [e.to_dict(f"e{n}") for n, e in enumerate(self._elements, start=1)]}

    # The element a location text refers to, or None. An exact name beats a partial match.
    def find_element(self, location: str) -> SiteElement | None:
        text = location.strip().lower()
        matches = [e for e in self._elements if e.matches(text)]
        exact = [e for e in matches if e.name.lower() == text or text in [a.lower() for a in e.aliases]]
        return (exact or matches or [None])[0]
