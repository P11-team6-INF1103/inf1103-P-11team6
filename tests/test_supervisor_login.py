# Darrel
import pytest

from tests.api_helpers import FORM, make_client
from web_support.supervisor_login import SupervisorLogin


@pytest.fixture
def login():
    return SupervisorLogin({"Supervisor": "123", "manager": "s3cret"}, "test-secret")


# A client that has not logged in yet, with one incident already saved.
def anonymous_client(tmp_path):
    client = make_client(tmp_path)
    assert client.post("/api/incidents", data=FORM).status_code == 201
    client.environ_base.pop("HTTP_AUTHORIZATION")
    return client


def test_only_whitelisted_names_with_their_password_log_in(login):
    assert login.check("supervisor", "123") and login.check("  SUPERVISOR ", "123")
    assert login.check("manager", "s3cret")
    assert not login.check("supervisor", "1234") and not login.check("supervisor", "")
    assert not login.check("intruder", "123") and not login.check(None, "123") and not login.check("supervisor", 123)


def test_accounts_come_from_a_comma_separated_list():
    assert SupervisorLogin.parse_accounts("supervisor:123, boss:a:b ,broken,:nopass,empty:") == \
        {"supervisor": "123", "boss": "a:b"}


def test_default_account_is_used_when_none_are_configured(monkeypatch):
    monkeypatch.delenv("DASHBOARD_ACCOUNTS", raising=False)
    assert SupervisorLogin.from_environment().check("supervisor", "123")
    monkeypatch.setenv("DASHBOARD_ACCOUNTS", "lead:pass1")
    configured = SupervisorLogin.from_environment()
    assert configured.check("lead", "pass1") and not configured.check("supervisor", "123")


def test_tokens_are_signed_and_tied_to_a_whitelisted_account(login):
    token = login.issue("Supervisor")
    assert login.verify(token) == "supervisor"
    assert login.verify(token + "x") is None and login.verify("") is None and login.verify(None) is None
    assert SupervisorLogin({"supervisor": "123"}, "other-secret").verify(token) is None
    assert SupervisorLogin({"manager": "s3cret"}, "test-secret").verify(token) is None  # account removed
