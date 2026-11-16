"""Offline tests: no API key, no network. Run: python -m unittest discover -s tests -v"""
import hashlib
import hmac
import os
import tempfile
import unittest
from pathlib import Path

# Isolate every output path in a temp folder BEFORE the package reads its config.
_TMP = Path(tempfile.mkdtemp())
os.environ.update(DB_FILE=str(_TMP / "leads.db"), ALERTS_FILE=str(_TMP / "alerts.log"),
                  OUTBOX_DIR=str(_TMP / "outbox"), LLM_PROVIDER="mock")

from welcome_automation import config, instagram, messenger  # noqa: E402
from welcome_automation.analyzer import get_analyzer  # noqa: E402
from welcome_automation.run import process_contact  # noqa: E402
from welcome_automation.storage import LeadStore, contact_key, normalize_phone  # noqa: E402


class PhoneAndKeyTests(unittest.TestCase):
    def test_phone_formats_collapse_to_one_number(self):
        for raw in ("09123456789", "+98 912 345 6789", "00989123456789", "۰۹۱۲۳۴۵۶۷۸۹", "0912-345-6789"):
            self.assertEqual(normalize_phone(raw), "9123456789", raw)

    def test_contact_key_priority(self):
        self.assertEqual(contact_key({"ig_id": "123", "email": "a@b.c"}), "ig:123")
        self.assertEqual(contact_key({"email": "  Reza@Example.COM "}), "email:reza@example.com")
        self.assertEqual(contact_key({"phone": "0912 345 6789"}), "phone:9123456789")
        self.assertEqual(contact_key({"id": "c-9"}), "id:c-9")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.db = Path(tempfile.mkdtemp()) / "leads.db"
        self.store = LeadStore(self.db)
        self.sections, self.settings = messenger.load_template()
        self.stats = {"processed": 0, "duplicate": 0, "buying": 0, "error": 0}
        self.seen: set = set()

    def tearDown(self):
        self.store.close()

    def run_one(self, contact):
        process_contact(contact, store=self.store, analyzer=get_analyzer("mock"), sections=self.sections,
                        settings=self.settings, seen=self.seen, dry_run=False, stats=self.stats)

    def test_same_person_gets_only_one_welcome(self):
        self.run_one({"id": "1", "channel": "website_form", "name": "Reza", "email": "Reza@Example.com",
                      "phone": "", "message": "I want a quote for 20 licences, budget ready"})
        self.seen.clear()  # simulate a later run: only the database remembers
        self.run_one({"id": "2", "channel": "website_form", "name": "", "email": " reza@example.com",
                      "phone": "", "message": "Any update?"})
        self.assertEqual(self.stats["processed"], 1)
        self.assertEqual(self.stats["duplicate"], 1)
        n = self.store.conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        self.assertEqual(n, 1)

    def test_failed_analysis_saves_nothing(self):
        class Broken:
            def analyze(self, contact):
                return {"error": "model timeout"}
        process_contact({"id": "x", "email": "x@y.z", "message": "hi"}, store=self.store, analyzer=Broken(),
                        sections=self.sections, settings=self.settings, seen=self.seen,
                        dry_run=False, stats=self.stats)
        self.assertEqual(self.stats["error"], 1)
        self.assertFalse(self.store.is_processed("email:x@y.z"))

    def test_welcome_uses_first_name(self):
        analysis = {"intent": "question", "name": "Maryam Karimi", "interest": "course dates"}
        text = messenger.render_welcome(analysis, {"channel": "instagram_dm"}, self.sections, self.settings)
        self.assertIn("Maryam", text)
        self.assertNotIn("Karimi", text)
        self.assertNotIn("{name}", text)


class InstagramWebhookTests(unittest.TestCase):
    def test_signature_check(self):
        old = config.IG_APP_SECRET
        config.IG_APP_SECRET = "s3cret"
        try:
            body = b'{"object":"instagram"}'
            good = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
            self.assertTrue(instagram.verify_signature(body, good))
            self.assertFalse(instagram.verify_signature(body, "sha256=" + "0" * 64))
            self.assertFalse(instagram.verify_signature(body, None))
        finally:
            config.IG_APP_SECRET = old

    def test_echo_and_own_messages_are_ignored(self):
        payload = {"object": "instagram", "entry": [{"id": "PAGE", "messaging": [
            {"sender": {"id": "USER1"}, "message": {"mid": "m1", "text": "Hello!"}, "timestamp": 1},
            {"sender": {"id": "PAGE"}, "message": {"mid": "m2", "text": "our reply", "is_echo": True}},
            {"sender": {"id": "PAGE"}, "message": {"mid": "m3", "text": "from page"}},
        ]}]}
        contacts = instagram.extract_messages(payload)
        self.assertEqual([c["ig_id"] for c in contacts], ["USER1"])
        self.assertEqual(contacts[0]["channel"], "instagram_dm")


if __name__ == "__main__":
    unittest.main()
