# Daniel
from datetime import date

import pytest

from reports.hazard_ranking_section import HazardRankingSection
from reports.location_ranking_section import LocationRankingSection
from reports.overview_section import OverviewSection
from reports.report_section import ReportSection
from reports.severity_trend_section import SeverityTrendSection
from trend_report import TrendReport

TODAY = date(2026, 11, 10)


def incident(day, location="Site A", severity=2, hazard="fall", **fields):
    return {"timestamp": f"{day}T10:00:00", "location": location, "severity_estimate": severity,
            "hazard_type": hazard, "resolved": False, "injury": False, **fields}


# The week ending 10 Nov is 4-10 Nov; the week before it is 28 Oct-3 Nov.
INCIDENTS = [
    incident("2026-11-09", "Block B", 5, "fall_from_height", injury=True),
    incident("2026-11-08", "Block B", 4, "fall_from_height", resolved=True),
    incident("2026-11-05", "Site A", 2, "fall"),
    incident("2026-10-30", "Site A", 1, "fall"),
    incident("2026-10-29", "Block B", 2, "other"),
    incident("2026-10-01", "Site A", 3, "fall"),  # older than both periods
]


def week():
    return TrendReport.standard({"fall": "Slip or fall", "fall_from_height": "Fall from height"}).build(INCIDENTS, 7, TODAY)


def test_overview_compares_this_period_with_the_one_before():
    overview = week()["sections"]["overview"]
    assert overview["total"] == 3 and overview["previous_total"] == 2 and overview["change"] == 1
    assert overview["severe"] == 2 and overview["previous_severe"] == 0
    assert overview["average_severity"] == 3.7 and overview["previous_average_severity"] == 1.5
    assert overview["injuries"] == 1 and overview["open"] == 2 and overview["resolved"] == 1


def test_rankings_put_the_busiest_first_and_use_readable_hazard_names():
    sections = week()["sections"]
    assert sections["locations"][0] == {"name": "Block B", "count": 2, "previous_count": 1, "share": 67,
                                       "worst_severity": 5, "average_severity": 4.5}
    assert [h["name"] for h in sections["hazards"]] == ["Fall from height", "Slip or fall"]


def test_trend_is_daily_for_a_week_and_weekly_for_a_long_period():
    daily = week()["sections"]["trend"]
    assert len(daily) == 7 and daily[0]["from"] == "2026-11-04" and daily[-1]["to"] == "2026-11-10"
    assert [d["incidents"] for d in daily] == [0, 1, 0, 0, 1, 1, 0]
    monthly = TrendReport.standard().build(INCIDENTS, 28, TODAY)["sections"]["trend"]
    assert len(monthly) == 4 and sum(b["incidents"] for b in monthly) == 5
    assert monthly[-1]["severe"] == 2 and monthly[-1]["to"] == "2026-11-10"


def test_notes_say_what_changed_in_plain_words():
    notes = week()["notes"]
    assert "Incidents are up by 1 (2 before, 3 now)." in notes
    assert "Severe incidents (severity 4+) rose from 0 to 2." in notes
    assert any("Block B had the most incidents" in n for n in notes)
    assert any("Fall from height" in n.title() or "fall from height" in n for n in notes)


def test_an_empty_period_and_unreadable_timestamps_do_not_break_the_report():
    empty = TrendReport.standard().build([], 7, TODAY)
    assert empty["notes"] == ["No incidents were logged in this period."]
    assert empty["sections"]["locations"] == [] and empty["sections"]["overview"]["average_severity"] is None
    messy = TrendReport.standard().build([{"timestamp": "garbage"}, {"location": "x"}, incident("2026-11-09")], 7, TODAY)
    assert messy["skipped"] == 2 and messy["sections"]["overview"]["total"] == 1


def test_an_incident_the_ai_could_not_assess_counts_but_is_left_out_of_the_averages():
    unassessed = incident("2026-11-09", severity=0, assessment_error="AI down")
    overview = TrendReport.standard().build([unassessed, incident("2026-11-09", severity=4)], 7, TODAY)["sections"]["overview"]
    assert overview["total"] == 2 and overview["average_severity"] == 4.0 and overview["severe"] == 1


def test_csv_export_lists_every_section():
    report = TrendReport.standard()
    text = report.to_csv(report.build(INCIDENTS, 7, TODAY))
    lines = text.splitlines()
    assert lines[0] == "section,item,value" and "period,from,2026-11-04" in lines
    assert "overview,total,3" in lines and any(line.startswith("locations,Block B,") for line in lines)
    assert any(line.startswith("trend,2026-11-04 to 2026-11-04") for line in lines)


# OCP and LSP: a brand-new section plugs in without touching TrendReport, and every section is used the same way.
class CriticalCountSection(ReportSection):
    @property
    def key(self):
        return "critical"

    def build(self, current, previous, days, today):
        return {"count": sum(1 for i in current if i["severity_estimate"] == 5)}

    def rows(self, data):
        return [("count", data["count"])]


def test_a_new_section_plugs_in_without_changing_the_report_class():
    report = TrendReport([OverviewSection(), CriticalCountSection()])
    built = report.build(INCIDENTS, 7, TODAY)
    assert built["sections"]["critical"] == {"count": 1} and set(built["sections"]) == {"overview", "critical"}
    assert "critical,count,1" in report.to_csv(built).splitlines()


@pytest.mark.parametrize("section", [OverviewSection(), HazardRankingSection(), LocationRankingSection(), SeverityTrendSection()])
def test_every_section_can_stand_in_for_the_base_type(section):
    data = section.build([], [], 7, TODAY)
    assert isinstance(section, ReportSection) and isinstance(section.notes(data), list) and isinstance(section.rows(data), list)


def test_the_section_interface_cannot_be_created_directly():
    with pytest.raises(TypeError):
        ReportSection()
