# Lennart
from database import Database


class UnreachableDatabase(Database):
    def __init__(self):  # no real connection is attempted
        self.is_postgres = True

    def connect(self):
        raise ConnectionError("could not connect to server")
