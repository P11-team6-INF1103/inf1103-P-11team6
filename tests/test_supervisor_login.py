# Darrel
import pytest

from tests.api_helpers import FORM, SUPERVISOR, log_in, make_client
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


def test_each_developer_has_a_default_account(monkeypatch):
    monkeypatch.delenv("DASHBOARD_ACCOUNTS", raising=False)
    login = SupervisorLogin.from_environment()
    for name in ("darrel", "lennart", "daniel", "ren xiang", "Ren Xiang", "sufi", "Darrel"):
        assert login.check(name, "123"), name
    assert not login.check("darrel", "wrong") and not login.check("guest", "123")


def test_tokens_are_signed_and_tied_to_a_whitelisted_account(login):
    token = login.issue("Supervisor")
    assert login.verify(token) == "supervisor"
    assert login.verify(token + "x") is None and login.verify("") is None and login.verify(None) is None
    assert SupervisorLogin({"supervisor": "123"}, "other-secret").verify(token) is None
    assert SupervisorLogin({"manager": "s3cret"}, "test-secret").verify(token) is None  # account removed


def test_tokens_run_out(login, monkeypatch):
    token = login.issue("supervisor")
    monkeypatch.setattr(SupervisorLogin, "SESSION_SECONDS", -1)
    assert login.verify(token) is None


def test_every_route_needs_a_login_except_health_and_login(tmp_path):
    client = anonymous_client(tmp_path)
    blocked = [client.get("/api/incidents"), client.get("/api/incidents/1"), client.get("/api/meta"),
               client.get("/api/incidents/1/photo"), client.get("/api/incidents/export"),
               client.get("/api/reports/summary"), client.get("/api/incidents/search?q=plank"),
               client.get("/api/locations"), client.get("/api/site-plan"), client.get("/api/session"),
               client.post("/api/incidents", data=FORM), client.delete("/api/incidents/1"),
               client.post("/api/incidents/1/resolve", json={}), client.post("/api/incidents/1/reopen"),
               client.put("/api/incidents/1/priority", json={"priority": 1}),
               client.patch("/api/incidents/1", data={"location": "Site C"}),
               client.post("/api/incidents/1/revert", json={"version": 1}),
               client.post("/api/incidents/1/reanalyse"), client.put("/api/site-plan", json={}),
               client.delete("/api/site-plan"), client.post("/api/site-plan/read")]
    assert [r.status_code for r in blocked] == [401] * len(blocked)
    assert blocked[0].get_json()["errors"] == ["Log in to use the dashboard."]
    assert client.get("/api/health").status_code == 200 and client.get("/api/no-such-page").status_code == 404
    preflight = client.options("/api/incidents", headers={"Origin": "http://localhost:5173",
                                                          "Access-Control-Request-Method": "GET",
                                                          "Access-Control-Request-Headers": "authorization"})
    assert preflight.status_code == 200 and "authorization" in preflight.headers["Access-Control-Allow-Headers"]


def test_links_and_photos_may_carry_the_token_in_the_address(tmp_path):
    client = anonymous_client(tmp_path)
    token = client.post("/api/login", json=SUPERVISOR).get_json()["token"]
    assert client.get(f"/api/incidents/export?token={token}").status_code == 200
    assert client.get(f"/api/reports/summary?format=csv&token={token}").status_code == 200
    assert client.get(f"/api/incidents/1/photo?token={token}").status_code == 404  # let in: this incident has no photo
    assert client.get(f"/api/incidents?token={token}").status_code == 401  # other routes need the header
    assert client.get("/api/incidents/export?token=forged").status_code == 401


def test_logged_in_supervisor_can_resolve_and_delete(tmp_path):
    client = log_in(anonymous_client(tmp_path))
    assert client.get("/api/session").get_json() == {"username": "supervisor"}
    assert client.post("/api/incidents/1/resolve", json={"note": "Fixed"}).get_json()["resolved"] is True
    assert client.delete("/api/incidents/1").status_code == 200 and client.get("/api/incidents").get_json() == []


def test_wrong_logins_are_refused_then_blocked(tmp_path):
    client = anonymous_client(tmp_path)
    assert client.get("/api/session").status_code == 401
    assert client.post("/api/login", json={"username": "supervisor", "password": "nope"}).status_code == 401
    assert client.post("/api/login", data="not json").status_code == 401
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer forged.token.value"
    assert client.delete("/api/incidents/1").status_code == 401
    for _ in range(8):
        client.post("/api/login", json={"username": "supervisor", "password": "guess"})
    response = client.post("/api/login", json=SUPERVISOR)
    assert response.status_code == 429 and "Too many wrong logins" in response.get_json()["errors"][0]
