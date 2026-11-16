# Sufi

class ElementKind:
    # One kind of thing on a site plan. The kinds differ only by data, so a new kind is one new line in
    # ELEMENT_KINDS (open/closed), not a new class.
    def __init__(self, key: str, label: str, hint: str, min_size_m: float = 1.0) -> None:
        self.key = key
        self.label = label
        self.hint = hint                  # what the AI should look for on the drawing
        self._min_size_m = min_size_m

    # The smallest footprint (metres) this kind is allowed to have, so a tiny box is still visible on the map.
    def min_size(self) -> float:
        return self._min_size_m
