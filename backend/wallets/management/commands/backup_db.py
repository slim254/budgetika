"""Back up the SQLite database using the sqlite3 online backup API.

Usage:
    python manage.py backup_db

Writes a timestamped copy to ~/.budgeting-app/backups/db-YYYYMMDD-HHMMSS.sqlite3
via sqlite3.Connection.backup() (safe to run against a live, in-use database —
unlike a plain file copy, it will not produce a torn/corrupt snapshot). Then
prunes backups older than 30 days, always keeping at least the 5 most recent
regardless of age.
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

BACKUP_DIR = Path.home() / ".budgeting-app" / "backups"
KEEP_DAYS = 30
KEEP_MIN = 5


class Command(BaseCommand):
    help = "Back up the SQLite database (sqlite3 .backup) and prune old backups."

    def handle(self, *args, **options):
        db_settings = settings.DATABASES["default"]
        engine = db_settings.get("ENGINE", "")
        if not engine.endswith("sqlite3"):
            raise CommandError(
                f"backup_db only supports SQLite databases (DATABASES['default']['ENGINE'] "
                f"is {engine!r}). Use your database engine's native backup tool instead."
            )

        db_path = Path(db_settings["NAME"])
        if not db_path.exists():
            raise CommandError(f"Database file not found: {db_path}")

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest_path = BACKUP_DIR / f"db-{timestamp}.sqlite3"

        source_conn = sqlite3.connect(str(db_path))
        dest_conn = sqlite3.connect(str(dest_path))
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
            source_conn.close()

        self.stdout.write(self.style.SUCCESS(f"Backed up {db_path} -> {dest_path}"))

        removed = self._prune()
        if removed:
            self.stdout.write(f"Pruned {removed} backup(s) older than {KEEP_DAYS} days.")

    def _prune(self):
        """Delete backups older than KEEP_DAYS, but always keep the KEEP_MIN newest."""
        backups = sorted(
            BACKUP_DIR.glob("db-*.sqlite3"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if len(backups) <= KEEP_MIN:
            return 0

        cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
        removed = 0
        for backup in backups[KEEP_MIN:]:
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            if mtime < cutoff:
                backup.unlink()
                removed += 1
        return removed
