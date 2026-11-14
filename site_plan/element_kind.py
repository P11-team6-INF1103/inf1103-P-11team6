# Sufi

class ElementKind:
    # One kind of thing that can appear on a site plan (building, crane, gate...). The kinds differ only by data, so
    # they are objects of this one class, not ten subclasses. The AI prompt, the validator and the site map all work
    # from the kind's key, so a new kind is one new line in ELEMENT_KINDS (open/closed) and no code changes.
    def __init__(self, key: str, label: str, hint: str, min_size_m: float = 1.0) -> None:
        self.key = key
        self.label = label
        self.hint = hint                  # what the AI should look for on the drawing
        self._min_size_m = min_size_m

    # The smallest footprint (metres) this kind is allowed to have, so a tiny box is still visible on the map.
    def min_size(self) -> float:
        return self._min_size_m
