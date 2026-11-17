# Lennart
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from data_stores.db_json import DbJson
from database import Database


class AccountStore:
    # The dashboard's login accounts. One row per account in the database's documents table (name "account:<name>"),
    # holding the password hash only: no password is kept in the source, in a file or in plain text.
    PREFIX = "account:"

    def __init__(self, database: Database) -> None:
        self._database = database
        # Compared against when the name is unknown, so a wrong name takes as long as a wrong password.
        self._dummy_hash = generate_password_hash(secrets.token_hex(8))

    # Account names ignore case and spaces around them.
    @staticmethod
    def _key(name: str) -> str:
        return name.strip().lower()

    def _document(self, name: str) -> DbJson:
        return DbJson(self._database, self.PREFIX + self._key(name), dict)

    # Creates the account, or replaces its password. False if the name or password is empty or the write failed.
    def add(self, name: str, password: str) -> bool:
        if not self._key(name) or not password:
            return False
        return self._document(name).write({"hash": generate_password_hash(password)})

    # Adds every name:password pair (replacing a password that changed). Returns how many were saved.
    def seed(self, accounts: dict[str, str]) -> int:
        return sum(self.add(name, password) for name, password in accounts.items())

    def remove(self, name: str) -> bool:
        return self._document(name).delete()

    def exists(self, name: str) -> bool:
        data, error = self._document(name).read()
        return error is None and bool(data.get("hash"))

    # How many accounts the database holds (0 if it cannot be read).
    def count(self) -> int:
        try:
            with self._database.connect() as connection:
                row = connection.execute("SELECT COUNT(*) AS n FROM documents WHERE name LIKE ?",
                                         (self.PREFIX + "%",)).fetchone()
            return int(row["n"])
        except Exception:
            return 0

    # True only for an existing account with its password. A missing account, a damaged row or an unreachable
    # database all give False, never an error.
    def check(self, name: object, password: object) -> bool:
        if not isinstance(name, str) or not isinstance(password, str):
            return False
        data, error = self._document(name).read()
        stored = None if error else data.get("hash")
        matches = check_password_hash(stored if isinstance(stored, str) and stored else self._dummy_hash, password)
        return isinstance(stored, str) and bool(stored) and matches
