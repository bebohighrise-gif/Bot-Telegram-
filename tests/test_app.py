import os
import tempfile
import unittest
from unittest.mock import patch

import main


class Rust133BotTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_db = main.DB_FILE
        self.old_admins = main.ADMIN_IDS.copy()
        self.old_group = main.GROUP_ID
        main.DB_FILE = os.path.join(self.tempdir.name, "bot.db")
        main.ADMIN_IDS = {12345}
        main.GROUP_ID = -100123
        main.init_db()

    def tearDown(self):
        main.DB_FILE = self.old_db
        main.ADMIN_IDS = self.old_admins
        main.GROUP_ID = self.old_group
        self.tempdir.cleanup()

    def test_allowed_and_suspicious_domains(self):
        self.assertTrue(main.link_is_allowed("https://rust.facepunch.com/news"))
        self.assertTrue(main.link_is_allowed("https://store.steampowered.com/app/252490"))
        self.assertTrue(main.suspicious_url("https://example.invalid/offer"))
        self.assertTrue(main.suspicious_url("https://bit.ly/regalo"))

    def test_extracts_urls_from_text_and_caption(self):
        message = type("Message", (), {"text": "Mira https://example.com y www.site.test", "caption": None})()
        self.assertEqual(main.urls_in(message), ["https://example.com", "www.site.test"])
        message.text = None
        message.caption = "archivo en https://bit.ly/x"
        self.assertEqual(main.urls_in(message), ["https://bit.ly/x"])

    def test_spanish_heuristic(self):
        self.assertTrue(main.probably_spanish("Hola, este es un mensaje para la comunidad"))
        self.assertFalse(main.probably_spanish("This is a message for the community"))

    def test_link_policy_is_persisted(self):
        self.assertEqual(main.link_mode(), "review")
        main.set_setting("link_mode", "auto")
        self.assertEqual(main.link_mode(), "auto")
        main.set_setting("link_mode", "invalid")
        self.assertEqual(main.link_mode(), "review")

    def test_runtime_validation_requires_token_and_admin(self):
        with patch.object(main, "TELEGRAM_TOKEN", ""), patch.object(main, "ADMIN_IDS", {12345}):
            with self.assertRaisesRegex(RuntimeError, "TELEGRAM_TOKEN"):
                main.validate_runtime_config()
        with patch.object(main, "TELEGRAM_TOKEN", "123456:abcdefghijklmnopqrstuvwxyz"), patch.object(main, "ADMIN_IDS", set()):
            with self.assertRaisesRegex(RuntimeError, "ADMIN"):
                main.validate_runtime_config()


if __name__ == "__main__":
    unittest.main()
