# Daniel
from workflow import WorkflowStore


def test_suggested_priority():
    assert WorkflowStore.suggested_priority({"severity_estimate": 5}) == 1
    assert WorkflowStore.suggested_priority({"severity_estimate": 4}) == 2
    assert WorkflowStore.suggested_priority({"severity_estimate": 3}) == 3
    assert WorkflowStore.suggested_priority({"severity_estimate": 1, "outcome": "systemic_escalation"}) == 2
    assert WorkflowStore.suggested_priority({"severity_estimate": 1, "outcome": "log_only"}) == 4
    assert WorkflowStore.suggested_priority({"assessment_error": "down"}) == 3
