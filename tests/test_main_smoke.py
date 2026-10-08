import json

import main
import trial


def _incident(**overrides):
    incident = {
        "description": "Worker slipped on a wet floor near the loading bay.",
        "location": "Site A - Block 3",
        "reporter_role": "site_supervisor",
        "injury": False,
        "timestamp": "2026-10-05T09:00:00",
    }
    incident.update(overrides)
    return incident


def _use_fakes(monkeypatch):
    monkeypatch.setattr(main.ai_manager, "enrich_record", lambda record, history=None: trial.fake_enrich_record(record))
    monkeypatch.setattr(main.logic_manager, "assess_severity", lambda record, weather=None, history=None: trial.fake_assess_severity(record))
    monkeypatch.setattr(main, "decide_outcome", trial.fake_decide_outcome)


def test_start_up_returns_a_list_of_records():
    assert main.start_up() == []
