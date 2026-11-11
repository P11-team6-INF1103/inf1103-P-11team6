# Daniel
from search_engine import IncidentSearch

INCIDENTS = [
    {"id": 1, "timestamp": "2026-10-30T09:00:00", "description": "Worker slipped on wet scaffold", "location": "Site A",
     "hazard_type": "fall", "severity_estimate": 4, "outcome": "stop_work_review", "priority": 2, "resolved": False},
    {"id": 2, "timestamp": "2026-10-31T09:00:00", "description": "Forklift hit a pallet", "location": "Site B",
     "hazard_type": "vehicle", "severity_estimate": 2, "outcome": "log_only", "priority": 4, "resolved": True,
     "photo_file": "a.png", "resolution_note": "Driver retrained"},
    {"id": 3, "timestamp": "2026-10-29T09:00:00", "description": "Scaffolding collapse near site office",
     "location": "Site A", "hazard_type": "fall", "severity_estimate": 5, "outcome": "stop_work_review",
     "priority": 1, "resolved": False},
]
SEARCH = IncidentSearch({"fall": "Fall from height", "vehicle": "Vehicle"})


def ids(results):
    return [r["id"] for r in results]


def test_search_ranks_and_matches_prefixes_and_plurals():
    assert ids(SEARCH.search(INCIDENTS, "scaffold")) == [1, 3]  # "scaffolding" starts with "scaffold"
    assert ids(SEARCH.search(INCIDENTS, "forklifts")) == [2]
    assert ids(SEARCH.search(INCIDENTS, "site a slipped")) == [1]  # every word must match
    assert ids(SEARCH.search(INCIDENTS, "height")) == [1, 3]  # found through the hazard label


def test_search_phrase_number_and_empty_query():
    assert ids(SEARCH.search(INCIDENTS, '"hit a pallet"')) == [2]
    assert ids(SEARCH.search(INCIDENTS, '"pallet hit"')) == []
    assert ids(SEARCH.search(INCIDENTS, "#3")) == [3]
    assert ids(SEARCH.search(INCIDENTS, "")) == [2, 1, 3]  # newest first
    assert SEARCH.search(INCIDENTS, "retrained")[0]["matched"] == ["resolution"]


def test_search_filters():
    assert ids(SEARCH.search(INCIDENTS, "", {"severity_min": 4})) == [1, 3]
    assert ids(SEARCH.search(INCIDENTS, "", {"status": "resolved"})) == [2]
    assert ids(SEARCH.search(INCIDENTS, "", {"status": "open", "location": "site a"})) == [1, 3]
    assert ids(SEARCH.search(INCIDENTS, "", {"priority": 1})) == [3]
    assert ids(SEARCH.search(INCIDENTS, "", {"date_from": "2026-10-30", "date_to": "2026-10-30"})) == [1]
    assert ids(SEARCH.search(INCIDENTS, "", {"has_photo": True})) == [2]
