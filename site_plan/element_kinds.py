# Sufi

from site_plan.element_kind import ElementKind

# Every kind the system knows. SiteElement reads these and never branches on the kind.
ELEMENT_KINDS: dict[str, ElementKind] = {
    kind.key: kind for kind in (
        ElementKind("building", "Building / tower",
                    "a main building, tower, block or podium under construction (usually a large labelled rectangle)",
                    min_size_m=4.0),
        ElementKind("tower_crane", "Tower crane",
                    "a tower crane, often drawn as a small square or cross with a large circle showing its swing radius",
                    min_size_m=2.0),
        ElementKind("excavation", "Excavation / basement pit",
                    "an excavation, basement pit or deep trench (often hatched or labelled basement, B1, B2, pit, shoring)",
                    min_size_m=4.0),
        ElementKind("scaffold", "Scaffold", "scaffolding or a hoarded facade along the side of a building"),
        ElementKind("cabin", "Site office / cabins",
                    "site offices, welfare cabins, canteen, first aid room or dormitory containers"),
        ElementKind("laydown", "Laydown / storage",
                    "a material laydown, storage or stockpile area (rebar, formwork, pipes, pallets)"),
        ElementKind("gate", "Gate / entrance", "a site gate, entrance or security post on the boundary"),
        ElementKind("road", "Road / access route", "a haul road, access road, ramp or vehicle route"),
        ElementKind("power", "Switchroom / generators",
                    "a switchroom, generator, transformer or temporary power area"),
        ElementKind("zone", "Other area",
                    "any other labelled area that is not one of the kinds above (loading bay, parking, assembly point)"),
    )
}
