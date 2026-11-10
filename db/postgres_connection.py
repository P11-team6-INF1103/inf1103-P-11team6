# Lennart
# Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".

class PostgresConnection:
    # Lets the Postgres driver take the same ? placeholders SQLite uses.
    def __init__(self, connection) -> None:
        self._connection = connection

    def execute(self, sql: str, params: tuple = ()):
        return self._connection.execute(sql.replace("?", "%s"), params)
