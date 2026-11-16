# Darrel
import os
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

# Used when DASHBOARD_ACCOUNTS is not set: the demo supervisor and one account per developer on the team.
_DEFAULT_ACCOUNTS = "supervisor:123,darrel:123,lennart:123,daniel:123,ren xiang:123,sufi:123"


class SupervisorLogin:
    # Whitelisted supervisor accounts for the dashboard: there is no sign-up, only the accounts given here.
    # Passwords are kept as hashes, and a login hands back a signed token that runs out after SESSION_SECONDS.
    SESSION_SECONDS = 8 * 60 * 60

    def __init__(self, accounts: dict[str, str], secret: str) -> None:
        self._hashes = {name.strip().lower(): generate_password_hash(password)
                        for name, password in accounts.items() if name.strip() and password}
        self._tokens = URLSafeTimedSerializer(secret, salt="supervisor-login")
        # Compared against when the name is unknown, so a wrong name takes as long as a wrong password.
        self._dummy_hash = generate_password_hash(secrets.token_hex(8))

    # The accounts from DASHBOARD_ACCOUNTS ("name:password,name2:password2") and the signing key from AUTH_SECRET.
    # Without AUTH_SECRET a random key is made, so every login ends when the server restarts.
    @classmethod
    def from_environment(cls) -> "SupervisorLogin":
        return cls(cls.parse_accounts(os.environ.get("DASHBOARD_ACCOUNTS") or _DEFAULT_ACCOUNTS),
                   os.environ.get("AUTH_SECRET") or secrets.token_hex(32))

    # "name:password,name2:password2" as a dict, spaces around each part ignored; entries without a colon, name or
    # password are skipped.
    @staticmethod
    def parse_accounts(text: str) -> dict[str, str]:
        accounts = {}
        for entry in text.split(","):
            name, colon, password = entry.partition(":")
            if colon and name.strip() and password.strip():
                accounts[name.strip()] = password.strip()
        return accounts

    # True only for a whitelisted name with its password (the name ignores case and spaces).
    def check(self, username: object, password: object) -> bool:
        if not isinstance(username, str) or not isinstance(password, str):
            return False
        stored = self._hashes.get(username.strip().lower())
        matches = check_password_hash(stored or self._dummy_hash, password)
        return stored is not None and matches

    # A signed token that proves this account logged in.
    def issue(self, username: str) -> str:
        return self._tokens.dumps({"user": username.strip().lower()})

    # The account name inside a valid, unexpired token from a still-whitelisted account, otherwise None.
    def verify(self, token: object) -> str | None:
        if not isinstance(token, str) or not token:
            return None
        try:
            data = self._tokens.loads(token, max_age=self.SESSION_SECONDS)
        except (SignatureExpired, BadSignature):
            return None
        user = data.get("user") if isinstance(data, dict) else None
        return user if isinstance(user, str) and user in self._hashes else None
