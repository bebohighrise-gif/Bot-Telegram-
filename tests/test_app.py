import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import helpers  # noqa: F401  (configura el entorno antes de importar bot)
import bot


class Rust133AsyncBotTests(unittest.TestCase):
    def test_token_validation(self):
        with patch.object(bot, "TOKEN", ""):
            self.assertFalse(bot.valid_token())
        with patch.object(bot, "TOKEN", "123456:abcdefghijklmnopqrstuvwxyz"):
            self.assertTrue(bot.valid_token())

    def test_link_helpers(self):
        self.assertEqual(bot.link_host("https://www.facepunch.com/news"), "facepunch.com")
        self.assertTrue(bot.link_allowed("https://rust.facepunch.com/news"))
        self.assertFalse(bot.link_allowed("https://unknown.example/offer"))

    def test_link_allowlist_cannot_be_spoofed(self):
        spoofed = [
            "https://wfacepunch.com/x",                 # antes: lstrip("www.") recortaba la "w"
            "https://wwwsteamcommunity.com/x",
            "https://facepunch.com@evil.example/",     # userinfo: el host real es evil.example
            "https://evil.example\\@facepunch.com/",   # barra invertida: los navegadores van a evil.example
            "https://facepunch.com.evil.example/",
            "https://notfacepunch.com/",
            "ftp://facepunch.com/",
        ]
        for url in spoofed:
            self.assertFalse(bot.link_allowed(url), url)
        for url in ["https://facepunch.com", "http://www.steamcommunity.com/x", "https://rust.facepunch.com./news"]:
            self.assertTrue(bot.link_allowed(url), url)

    def test_word_filter_uses_word_boundaries(self):
        self.assertEqual(bot.word_matches("Esto contiene estafa", ["estafa"]), "estafa")
        self.assertIsNone(bot.word_matches("estafador", ["estafa"]))

    def test_json_store_round_trip(self):
        async def run():
            with tempfile.TemporaryDirectory() as directory:
                store = bot.JsonStore(Path(directory))
                await store.save("custom.json", {"ok": True})
                self.assertEqual(await store.load("custom.json"), {"ok": True})
        asyncio.run(run())

    def test_callback_ids_are_short(self):
        self.assertLessEqual(len("validar:" + "a" * 10), 64)
        self.assertLessEqual(len("expulsar:" + "a" * 10), 64)


if __name__ == "__main__":
    unittest.main()
