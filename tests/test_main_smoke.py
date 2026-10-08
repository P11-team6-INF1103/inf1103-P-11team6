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


def test_process_incident_saves_and_returns_a_record_with_an_outcome(monkeypatch):
    _use_fakes(monkeypatch)
    records = []
    final_record = main.process_incident(_incident(), records)
    assert final_record["outcome"] in ("log_only", "pending_review", "systemic_escalation", "stop_work_review")
    assert records == [final_record]
    assert main.data_manager.load_records() == [final_record]


def test_log_incident_flow_runs_one_incident(monkeypatch, capsys):
    _use_fakes(monkeypatch)
    monkeypatch.setattr(main.io_manager, "get_incident_input", lambda: _incident())
    final_record = main.log_incident_flow([])
    assert "outcome" in final_record
    assert capsys.readouterr().out != ""


def test_run_batch_processes_every_incident_in_the_file(monkeypatch, tmp_path):
    _use_fakes(monkeypatch)
    path = tmp_path / "batch.json"
    path.write_text(json.dumps([_incident(), _incident(location="Site B")]))
    assert main.run_batch(str(path)) == 0
    assert len(main.data_manager.load_records()) == 2


def test_run_batch_returns_1_for_an_unreadable_file(tmp_path):
    assert main.run_batch(str(tmp_path / "missing.json")) == 1
