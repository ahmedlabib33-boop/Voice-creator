import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "t.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_contact_stores_both_forms(self):
        db = Database(self.path)
        db.add_contact("Ahmed", "01123040202")
        rows = db.list_contacts()
        self.assertEqual(rows[0]["original_input"], "01123040202")
        self.assertEqual(rows[0]["normalized_e164"], "+201123040202")

    def test_duplicate_contact_updates_name(self):
        db = Database(self.path)
        db.add_contact("A", "01123040202")
        db.add_contact("B", "+201123040202")
        rows = db.list_contacts()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "B")

    def test_sender_requires_numeric_phone_number_id(self):
        db = Database(self.path)
        with self.assertRaises(ValueError):
            db.add_authorized_sender("Biz", "+201123040202", "01123040202")
        saved = db.add_authorized_sender("Biz", "123456789012345", "01123040202")
        self.assertEqual(saved["normalized_e164"], "+201123040202")

    def test_legacy_schema_migrates(self):
        conn = sqlite3.connect(self.path)
        conn.executescript(
            """
            CREATE TABLE contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT, created_at TEXT NOT NULL);
            CREATE TABLE authorized_senders (id INTEGER PRIMARY KEY AUTOINCREMENT, display_name TEXT NOT NULL,
                phone_number_id TEXT NOT NULL UNIQUE, business_number TEXT, created_at TEXT NOT NULL);
            INSERT INTO contacts (name, phone, created_at) VALUES ('Old', '01123040202', 'x');
            INSERT INTO authorized_senders (display_name, phone_number_id, business_number, created_at)
                VALUES ('Biz', '123456789012345', '01000000000', 'x');
            """
        )
        conn.commit()
        conn.close()
        db = Database(self.path)
        c = db.list_contacts()[0]
        self.assertEqual((c["original_input"], c["normalized_e164"]), ("01123040202", "+201123040202"))
        s = db.list_authorized_senders()[0]
        self.assertEqual((s["original_input"], s["normalized_e164"]), ("01000000000", "+201000000000"))

    def test_send_log(self):
        db = Database(self.path)
        db.log_send("+201123040202", "123", "/x.mp3", "sent", "wamid.1")
        self.assertEqual(db.list_send_log()[0]["message_id"], "wamid.1")


if __name__ == "__main__":
    unittest.main()
