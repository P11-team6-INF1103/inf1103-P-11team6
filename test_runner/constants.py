#Ren Xiang

import re

OWNERS = ("Lennart", "Daniel", "Darrel", "Sufi", "Ren Xiang")

PHASE_NAMES = {1: "Development 1 (2-8 Nov)", 2: "Development 2 (9-15 Nov)", 3: "Misc (16-18 Nov)"}

PHASE_KEYS = {"dev1": 1, "dev2": 2, "misc": 3}

# Phase 1 tests need only the managers; phase 2 tests need the wiring, the web API and the features.
FIRST_PHASE_TESTS = {"test_models.py", "test_database.py", "test_data_manager.py", "test_logic_manager.py",
                     "test_io_manager.py", "test_ai_manager.py"}

BATCH_OUTPUT = ("INCIDENT SUMMARY", "Total incidents: 3", "With a photo: 1")

_NAME_TAG = re.compile(r"^\s*#\s?(Lennart|Daniel|Darrel|Sufi|Ren Xiang)\s*$")

_COUNTS = re.compile(r"(\d+) (passed|failed|errors?|skipped|deselected)")