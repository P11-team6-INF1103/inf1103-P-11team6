# Darrel
import logging
import os
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from web_support.account_store import AccountStore

logger = logging.getLogger(__name__)


class SupervisorLogin:
    # Whitelisted supervisor accounts for the dashboard: there is no sign-up, only the accounts in the AccountStore.
    # The store (the database) is given to it, so the accounts outlive this object (aggregation). A login hands back a
    # signed token that runs out after SESSION_SECONDS.
    SESSION_SECONDS = 8 * 60 * 60

    def __init__(self, accounts: AccountStore, secret: str) -> None:
        self._accounts = accounts
        self._tokens = URLSafeTimedSerializer(secret, salt="supervisor-login")

    # Saves the accounts from DASHBOARD_ACCOUNTS ("name:password,name2:password2") into the store, hashed (a password
    # that changed there replaces the old one). The signing key comes from AUTH_SECRET; without it a random key is made,
    # so every login ends when the server restarts.
    # If the store still has no account at all, one is made: 'supervisor' with a random password that is written to the
    # log once, so a fresh install is never open and never has a default password.
    @classmethod
    def from_environment(cls, accounts: AccountStore) -> "SupervisorLogin":
        accounts.seed(cls.parse_accounts(os.environ.get("DASHBOARD_ACCOUNTS") or ""))
        if accounts.count() == 0:
            password = secrets.token_urlsafe(9)
            if accounts.add("supervisor", password):
                logger.warning("No login accounts exist yet, so the account 'supervisor' was created with the password "
                               "%s (shown only now). Set DASHBOARD_ACCOUNTS to choose your own.", password)
        return cls(accounts, os.environ.get("AUTH_SECRET") or secrets.token_hex(32))

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
        return self._accounts.check(username, password)

    # A signed token that proves this account logged in.
    def issue(self, username: str) -> str:
        return self._tokens.dumps({"user": username.strip().lower()})

    # The account name inside a valid, unexpired token from a still-existing account, otherwise None.
    def verify(self, token: object) -> str | None:
        if not isinstance(token, str) or not token:
            return None
        try:
            data = self._tokens.loads(token, max_age=self.SESSION_SECONDS)
        except (SignatureExpired, BadSignature):
            return None
        user = data.get("user") if isinstance(data, dict) else None
        return user if isinstance(user, str) and self._accounts.exists(user) else None
