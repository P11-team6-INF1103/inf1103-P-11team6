# Lennart
import pytest

from data_stores.db_json import DbJson
from database import Database
from tests.doubles.unreachable_database import UnreachableDatabase
from web_support.account_store import AccountStore


@pytest.fixture
def database(tmp_path):
    return Database(str(tmp_path / "accounts.db"))


def test_an_account_is_checked_by_name_and_password(database):
    store = AccountStore(database)
    assert store.add("  Boss ", "s3cret") and store.exists("boss")
    assert store.check("BOSS", "s3cret") and not store.check("boss", "S3CRET") and not store.check("boss", "")
    assert not store.check("nobody", "s3cret") and not store.exists("nobody")


def test_only_a_hash_is_stored(database):
    AccountStore(database).add("boss", "s3cret")
    data, error = DbJson(database, "account:boss", dict).read()
    assert error is None and set(data) == {"hash"} and "s3cret" not in data["hash"]


def test_seed_counts_adds_and_replaces_a_changed_password(database):
    store = AccountStore(database)
    assert store.seed({"a": "one", "b": "two"}) == 2 and store.count() == 2
    store.seed({"a": "uno"})
    assert store.check("a", "uno") and not store.check("a", "one") and store.count() == 2


def test_empty_names_and_passwords_are_refused(database):
    store = AccountStore(database)
    assert not store.add("", "pw") and not store.add("   ", "pw") and not store.add("boss", "")
    assert store.count() == 0


def test_removing_an_account_stops_it_logging_in(database):
    store = AccountStore(database)
    store.add("boss", "s3cret")
    assert store.remove("boss") and not store.exists("boss") and not store.check("boss", "s3cret")


@pytest.mark.parametrize("name,password", [(None, "x"), ("boss", None), (1, 2), (["boss"], "x")])
def test_wrong_types_are_a_plain_no(database, name, password):
    store = AccountStore(database)
    store.add("boss", "s3cret")
    assert store.check(name, password) is False


def test_a_damaged_row_is_a_plain_no_not_an_error(database):
    store = AccountStore(database)
    DbJson(database, "account:boss", dict).write({"hash": 12345})
    assert store.check("boss", "anything") is False
    DbJson(database, "account:other", dict).write({"unexpected": True})
    assert store.check("other", "anything") is False and not store.exists("other")


def test_an_unreachable_database_never_raises():
    store = AccountStore(UnreachableDatabase())
    assert store.check("boss", "s3cret") is False and store.exists("boss") is False
    assert store.count() == 0 and store.add("boss", "s3cret") is False
