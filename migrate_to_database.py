# Lennart
# One-off: copies the local files (data/incidents.json and the priorities in data/app.db)
# into the database named by DATABASE_URL (Postgres, e.g. Neon). Safe to run twice: it only adds what is missing.
#   python migrate_to_database.py
import argparse
import os
import sqlite3

from dotenv import load_dotenv

from data_manager import DataManager
from database import Database
from db.database_unavailable import DatabaseUnavailable
from models.incident import Incident


class Migration:
    # Copies what is in the local data folder into one target database. Every step only adds what is missing,
    # so running it twice never duplicates anything.
    def __init__(self, folder: str, target: Database) -> None:
        self._target = target
        self._local = DataManager(folder)
        self._remote = DataManager(folder, target)

    # Incidents: only into an empty table, so running this twice never duplicates them.
    def copy_incidents(self) -> None:
        incidents = self._local.load_records()
        if self._remote.load_records():
            print("Incidents: the database already has some, so none were copied.")
            return
        copied = sum(self._remote.save_record(Incident.from_dict(i.to_dict())) for i in incidents)
        print(f"Incidents: copied {copied} of {len(incidents)}.")

    # Each incident's priority and resolved status, from the local SQLite file.
    def copy_workflow(self) -> None:
        db_file = self._local.database_path
        if not os.path.exists(db_file):
            return
        source = sqlite3.connect(db_file)
        source.row_factory = sqlite3.Row
        with self._target.connect() as connection:
            for row in source.execute("SELECT * FROM incident_workflow"):
                connection.execute(
                    "INSERT INTO incident_workflow (incident_key, priority, resolved, resolved_at, resolution_note, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                    tuple(row[k] for k in ("incident_key", "priority", "resolved", "resolved_at", "resolution_note", "updated_at")))

    # Command line entry point: returns the exit code.
    @classmethod
    def main(cls) -> int:
        parser = argparse.ArgumentParser(description="Copy local data into the DATABASE_URL database.")
        parser.parse_args()
        load_dotenv()
        url = os.environ.get("DATABASE_URL")
        if not url:
            print("DATABASE_URL is not set in .env.")
            return 1
        try:
            target = Database(url)
        except DatabaseUnavailable as error:
            print(f"Cannot migrate: {error}.")
            return 1
        migration = cls(DataManager.default_folder(), target)
        migration.copy_incidents()
        migration.copy_workflow()
        target.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(Migration.main())
