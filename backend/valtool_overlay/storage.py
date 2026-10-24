import json
import secrets
import shutil
import sqlite3
import threading
from contextlib import closing, contextmanager
from pathlib import Path

from pydantic import Field, ValidationError

from .models import Match, Model, Settings


class Configuration(Model):
    schema_version: int = 1
    port: int = Field(default=32145, ge=1024, le=65535)
    overlay_key: str = Field(default_factory=lambda: secrets.token_hex(24), pattern=r"^[a-fA-F0-9]{48}$")
    overlay: Settings = Field(default_factory=Settings)


class Storage:
    """Same schema as the prototype. One connection per operation; no ORM or pooled threads."""

    def __init__(self, directory: Path, port: int | None = None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "settings.json"
        self.db_path = self.directory / "matches.db"
        self._lock = threading.RLock()
        if self.path.exists():
            try:
                self.configuration = Configuration.model_validate_json(self.path.read_text())
            except (ValidationError, ValueError) as error:
                raise ValueError("Could not read settings.json. The file has not been changed.") from error
            if self.configuration.schema_version != 1:
                raise ValueError("Unknown settings version. The file has not been changed.")
        else:
            self.configuration = Configuration()
        if port is not None:
            self.configuration = Configuration.model_validate({**self.configuration.json_data(), "port": port})
        self._save_configuration(self.configuration)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS matches (account TEXT NOT NULL, id TEXT NOT NULL, started INTEGER NOT NULL, data TEXT NOT NULL, PRIMARY KEY(account,id));
                CREATE TABLE IF NOT EXISTS contexts (puuid TEXT PRIMARY KEY, data TEXT NOT NULL);
            """)

    @contextmanager
    def _connect(self):
        with closing(sqlite3.connect(self.db_path, timeout=5)) as db, db:
            yield db

    def _save_configuration(self, config: Configuration):
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(config.model_dump_json(by_alias=True, indent=2), encoding="utf-8")
        temporary.chmod(0o600)
        if self.path.exists():
            backup = self.path.with_suffix(".json.bak")
            shutil.copyfile(self.path, backup)
            backup.chmod(0o600)
        temporary.replace(self.path)

    def save_settings(self, settings: Settings):
        with self._lock:
            config = self.configuration.model_copy(update={"overlay": settings})
            self._save_configuration(config)
            self.configuration = config

    def read_matches(self, account: str) -> list[Match]:
        with self._lock, self._connect() as db:
            return [Match.model_validate_json(row[0]) for row in db.execute(
                "SELECT data FROM matches WHERE account=? ORDER BY started DESC", (account,)
            )]

    def save_match(self, account: str, match: Match):
        if not match.is_final:
            raise ValueError("Only final match snapshots may be cached")
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO matches(account,id,started,data) VALUES(?,?,?,?) ON CONFLICT(account,id) DO UPDATE SET started=excluded.started,data=excluded.data",
                       (account, match.id, match.started_at, match.model_dump_json(by_alias=True)))

    def save_context(self, puuid: str, context: dict):
        # A narrow allowlist makes accidental persistence of credentials impossible here.
        safe = {key: context[key] for key in ("puuid", "shard", "region", "version") if key in context}
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO contexts(puuid,data) VALUES(?,?) ON CONFLICT(puuid) DO UPDATE SET data=excluded.data", (puuid, json.dumps(safe)))

    def read_context(self, puuid: str) -> dict | None:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT data FROM contexts WHERE puuid=?", (puuid,)).fetchone()
            return json.loads(row[0]) if row else None
