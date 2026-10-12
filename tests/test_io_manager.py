import json

import io_manager as io


def _type(monkeypatch, lines):
    answers = iter(lines)
    prompts = []

    def fake_input(prompt=""):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


def _record(**overrides):
    record = {"description": "Worker slipped near the scaffolding", "location": "Site A", "reporter_role": "site_supervisor",
              "injury": False, "timestamp": "2026-10-02T17:32:00", "hazard_type": "fall",
              "severity_estimate": 2, "outcome": "log_only"}
    record.update(overrides)
    return record


def test_incident_input_reprompts_until_valid(monkeypatch, capsys):
    prompts = _type(monkeypatch, ["", "(&(&(&)", "worker slipped on a wet floor", "*^&*", "Site A - Block 3",
                                  "*^&*^&*ciudsbc", "site_supervisor", "maybe", "Y"])
    incident = io.get_incident_input()
    assert incident["description"] == "worker slipped on a wet floor"
    assert incident["location"] == "Site A - Block 3"
    assert incident["reporter_role"] == "site_supervisor" and incident["injury"] is True
    out = capsys.readouterr().out
    assert out.count("Error:") == 3 and "press Enter again to go back" in out and any(p.startswith("Please answer yes or no") for p in prompts)


def test_checks_reject_junk_and_accept_real_input():
    for junk in ("", "(&(&(&)", "short", "aaaaaaaaaaaa", "12345 67890 1234", "x" * 501):
        assert io._check_description(junk), junk
    assert io._check_description("Worker slipped on a wet floor near the stairwell") is None
    for junk in ("", "(&(&(&)", "***", "12345", "x" * 101):
        assert io._check_location(junk), junk
    assert io._check_location("Site A - Block 3 (Level 2), #04") is None
    for junk in ("", "*^&*^&*ciudsbc", "r", "boss123", "x" * 41):
        assert io._check_role(junk), junk
    assert io._check_role("site_supervisor") is None
    assert io._sanitise("  a \t b\x00  c \n") == "a b c"


def test_location_query_reprompts_and_defaults_to_30_days(monkeypatch, capsys):
    prompts = _type(monkeypatch, ["***", "Site A", "abc", "0", "-3", "7"])
    assert io.get_location_query() == ("Site A", 7)
    assert "Error:" in capsys.readouterr().out
    assert sum(p.startswith("Please enter a whole number") for p in prompts) == 3
    _type(monkeypatch, ["Site B", ""])
    assert io.get_location_query() == ("Site B", 30)


def test_location_query_returns_none_on_empty_input_to_go_back(monkeypatch):
    prompts = _type(monkeypatch, [""])
    assert io.get_location_query() is None
    assert "press Enter to go back" in prompts[0]
    prompts = _type(monkeypatch, ["***", ""])
    assert io.get_location_query() is None
    assert "press Enter to go back" in prompts[1]


def test_ask_try_again(monkeypatch):
    prompts = _type(monkeypatch, ["maybe", "n"])
    assert io.ask_try_again() is False
    assert "Please answer yes or no" in prompts[1]
    _type(monkeypatch, ["Y"])
    assert io.ask_try_again() is True


def test_ask_retry_save_warns_and_asks_again_until_valid(monkeypatch, capsys):
    prompts = _type(monkeypatch, ["maybe", "n"])
    assert io.ask_retry_save() is False
    assert "INCIDENT NOT SAVED" in capsys.readouterr().out
    assert "Please answer yes or no" in prompts[1]
    _type(monkeypatch, ["Y"])
    assert io.ask_retry_save() is True


def test_menu_rejects_invalid_choice(monkeypatch, capsys):
    _type(monkeypatch, ["9", "x", "3"])
    assert io.get_menu_choice() == "3"


def test_menu_treats_ctrl_c_and_closed_input_as_exit(monkeypatch, capsys):
    for interrupt in (EOFError, KeyboardInterrupt):
        def stop(prompt="", interrupt=interrupt):
            raise interrupt
        monkeypatch.setattr("builtins.input", stop)
        assert io.get_menu_choice() == "5"


def test_clean_keeps_dot_env_and_closes_up_punctuation():
    assert io._clean("is not set in .env") == "is not set in .env"
    assert io._clean("ends here . Next ; ok") == "ends here. Next; ok"
    assert io._clean("a‑b ’x’ 【10†L1】") == "a-b 'x'"


def test_summary_prints_a_boxed_table_most_severe_first(capsys):
    records = [_record(), _record(location="Site B", severity_estimate=5, outcome="stop_work_review",
                                  hazard_type="fall_from_height")]
    io.display_summary(records, {1: ("Minimal", "x")}, interactive=False)
    out = capsys.readouterr().out
    assert "Total incidents: 2" in out and "┌" in out and "└" in out
    assert out.index("Site B") < out.index("Site A")


def test_summary_opens_a_full_report_by_number(monkeypatch, capsys):
    _type(monkeypatch, ["9", "1", ""])
    io.display_summary([_record()], interactive=True)
    out = capsys.readouterr().out
    assert "Please enter a number from 1 to 1." in out and "INCIDENT #1" in out


def test_summary_with_no_records(capsys):
    io.display_summary([])
    assert "No incidents logged yet." in capsys.readouterr().out


def test_report_shows_sections_only_when_they_have_content(capsys):
    io.display_outcome(_record(review_likely_causes=["Wet floor"]), {2: ("Minor", "Record it.")})
    out = capsys.readouterr().out
    assert "SEVERITY AND ACTION" in out and "WHY IT LIKELY HAPPENED" in out
    assert "WEATHER AT THE TIME" not in out and "HOW TO PREVENT IT" not in out


def test_report_shows_the_weather_section_when_weather_was_checked(capsys):
    io.display_outcome(_record(weather_available=True, condition="rain", temperature_c=28, humidity_pct=90), {2: ("Minor", "Record it.")})
    out = capsys.readouterr().out
    assert "WEATHER AT THE TIME" in out and "Rain, 28°C, 90% humidity" in out


def test_query_results_display(capsys):
    io.display_query_results([])
    io.display_query_results([_record()])
    out = capsys.readouterr().out
    assert "No matching incidents found." in out and "1 matching incident(s)" in out


def test_read_incident_file_validates_every_item(tmp_path):
    items = [
        {"description": "worker slipped on wet floor", "location": "Site A", "reporter_role": "supervisor",
         "injury": "yes", "timestamp": "2026-09-27T10:00:00"},
        {"description": "", "location": "Site A", "reporter_role": "supervisor", "injury": True},
        {"description": "worker slipped on wet floor", "location": "Site A", "reporter_role": "supervisor", "injury": "maybe"},
        "nope",
    ]
    path = tmp_path / "in.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    good, problems = io.read_incident_file(str(path))
    assert len(good) == 1 and good[0]["injury"] is True and len(problems) == 3
    assert io.read_incident_file(str(tmp_path / "missing.json"))[0] == []
    path.write_text("{bad", encoding="utf-8")
    assert io.read_incident_file(str(path))[0] == []


def test_get_delete_choice_reprompts_until_valid_number(monkeypatch, capsys):
    _type(monkeypatch, ["0", "9", "abc", "2"])
    assert io.get_delete_choice(3) == 2
    assert "Please enter a number from 1 to 3" in capsys.readouterr().out


def test_get_delete_choice_enter_or_closed_input_goes_back(monkeypatch):
    _type(monkeypatch, [""])
    assert io.get_delete_choice(3) is None
    for interrupt in (EOFError, KeyboardInterrupt):
        def stop(prompt="", interrupt=interrupt):
            raise interrupt
        monkeypatch.setattr("builtins.input", stop)
        assert io.get_delete_choice(3) is None


def test_confirm_delete_shows_the_incident_and_asks_yes_or_no(monkeypatch, capsys):
    _type(monkeypatch, ["maybe", "y"])
    assert io.confirm_delete({"location": "Site A", "description": "Slip"}, 2) is True
    assert "Incident #2: Site A - Slip" in capsys.readouterr().out
    _type(monkeypatch, ["no"])
    assert io.confirm_delete({"location": "Site A", "description": "Slip"}, 2) is False


def test_pressing_enter_twice_at_any_incident_question_returns_none(monkeypatch):
    first = "worker slipped on a wet floor"
    for answers in (["", ""], [first, "  ", ""], [first, "Site A", "", ""], [first, "Site A", "site_supervisor", "", ""]):
        _type(monkeypatch, answers)
        assert io.get_incident_input() is None


def test_one_blank_answer_only_shows_the_hint_and_asks_again(monkeypatch, capsys):
    _type(monkeypatch, ["", "worker slipped on a wet floor", "", "***", "Site A - Block 3", "site_supervisor", "n"])
    incident = io.get_incident_input()
    assert incident["description"] == "worker slipped on a wet floor"
    assert incident["location"] == "Site A - Block 3" and incident["injury"] is False
    assert capsys.readouterr().out.count("press Enter again to go back") == 2


def test_blank_enter_is_not_special_for_other_yes_no_questions(monkeypatch):
    prompts = _type(monkeypatch, ["", "", "n"])
    assert io._ask_yes_no("Enter the incident again? (yes/no): ") is False
    assert prompts[1].startswith("Please answer yes or no") and "go back" not in prompts[1]
