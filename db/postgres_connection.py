# Lennart

class PostgresConnection:
    # Lets the Postgres driver take the same ? placeholders SQLite uses.
    def __init__(self, connection) -> None:
        self._connection = connection

    def execute(self, sql: str, params: tuple = ()):
        return self._connection.execute(sql.replace("?", "%s"), params)
