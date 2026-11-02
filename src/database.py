"""SQLite storage for contacts, authorized WhatsApp senders and the send log.

Both ``original_input`` (what the user typed) and ``normalized_e164`` are stored.
Legacy ``phone`` / ``business_number`` columns are kept in sync for compatibility
with databases created by earlier versions of the app.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import DB_PATH
from .validators import normalize_phone, validate_phone_number_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    original_input TEXT NOT NULL,
    normalized_e164 TEXT NOT NULL UNIQUE,
    phone TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS authorized_senders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,
    phone_number_id TEXT NOT NULL UNIQUE,
    original_input TEXT NOT NULL,
    normalized_e164 TEXT NOT NULL,
    business_number TEXT,
    waba_id TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS send_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_e164 TEXT NOT NULL,
    sender_phone_number_id TEXT,
    audio_path TEXT,
    status TEXT NOT NULL,
    message_id TEXT,
    error TEXT,
    created_at TEXT NOT NULL
);
"""

# table -> {column: declaration} added by migrations
MIGRATION_COLUMNS = {
    "contacts": {"original_input": "TEXT", "normalized_e164": "TEXT", "phone": "TEXT"},
    "authorized_senders": {
        "original_input": "TEXT",
        "normalized_e164": "TEXT",
        "business_number": "TEXT",
        "waba_id": "TEXT",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path | str = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- schema / migration ----------------------------------------------

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            for table, columns in MIGRATION_COLUMNS.items():
                existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
                for column, decl in columns.items():
                    if column not in existing:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            self._backfill(conn)

    @staticmethod
    def _backfill(conn: sqlite3.Connection) -> None:
        """Fill normalized/original columns for rows created by older versions."""
        for table, legacy in (("contacts", "phone"), ("authorized_senders", "business_number")):
            rows = conn.execute(
                f"SELECT id, {legacy} AS legacy, original_input, normalized_e164 FROM {table}"
            ).fetchall()
            for row in rows:
                source = row["normalized_e164"] or row["original_input"] or row["legacy"]
                if not source:
                    continue
                try:
                    norm = normalize_phone(source)
                except ValueError:
                    continue
                conn.execute(
                    f"UPDATE {table} SET original_input = COALESCE(NULLIF(original_input, ''), ?), "
                    f"normalized_e164 = ?, {legacy} = ? WHERE id = ?",
                    (source, norm.normalized_e164, norm.normalized_e164, row["id"]),
                )

    # --- contacts ----------------------------------------------------------

    def add_contact(self, name: str, phone_input: str) -> dict:
        name = (name or "").strip()
        if not name:
            raise ValueError("Contact name is required.")
        norm = normalize_phone(phone_input)
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO contacts (name, original_input, normalized_e164, phone, created_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(normalized_e164) DO UPDATE SET name = excluded.name, "
                "original_input = excluded.original_input",
                (name, norm.original_input, norm.normalized_e164, norm.normalized_e164, _now()),
            )
        return {"name": name, "original_input": norm.original_input, "normalized_e164": norm.normalized_e164}

    def list_contacts(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, name, original_input, normalized_e164, created_at "
                "FROM contacts ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_contact(self, contact_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))

    # --- authorized senders --------------------------------------------------

    def add_authorized_sender(
        self, display_name: str, phone_number_id: str, business_number_input: str, waba_id: str = ""
    ) -> dict:
        display_name = (display_name or "").strip()
        if not display_name:
            raise ValueError("Display name is required.")
        phone_number_id = validate_phone_number_id(phone_number_id)
        norm = normalize_phone(business_number_input)
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO authorized_senders "
                "(display_name, phone_number_id, original_input, normalized_e164, business_number, waba_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(phone_number_id) DO UPDATE SET display_name = excluded.display_name, "
                "original_input = excluded.original_input, normalized_e164 = excluded.normalized_e164, "
                "business_number = excluded.business_number, waba_id = excluded.waba_id",
                (
                    display_name,
                    phone_number_id,
                    norm.original_input,
                    norm.normalized_e164,
                    norm.normalized_e164,
                    (waba_id or "").strip(),
                    _now(),
                ),
            )
        return {
            "display_name": display_name,
            "phone_number_id": phone_number_id,
            "original_input": norm.original_input,
            "normalized_e164": norm.normalized_e164,
        }

    def list_authorized_senders(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, display_name, phone_number_id, original_input, normalized_e164, waba_id, created_at "
                "FROM authorized_senders ORDER BY display_name COLLATE NOCASE"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_authorized_sender(self, sender_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM authorized_senders WHERE id = ?", (sender_id,))

    # --- send log --------------------------------------------------------------

    def log_send(
        self,
        recipient_e164: str,
        sender_phone_number_id: str | None,
        audio_path: str | None,
        status: str,
        message_id: str | None = None,
        error: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO send_log (recipient_e164, sender_phone_number_id, audio_path, status, message_id, error, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (recipient_e164, sender_phone_number_id, audio_path, status, message_id, error, _now()),
            )

    def list_send_log(self, limit: int = 50) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, recipient_e164, sender_phone_number_id, audio_path, status, message_id, error, created_at "
                "FROM send_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
