import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
