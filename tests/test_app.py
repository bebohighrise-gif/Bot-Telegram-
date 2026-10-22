import json
import os
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import main


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.previous_db = main.DB_FILE
        self.previous_admin = main.ADMIN_ID
        main.DB_FILE = os.path.join(self.tempdir.name, "test.db")
        main.ADMIN_ID = 900000001

    def tearDown(self):
        main.DB_FILE = self.previous_db
        main.ADMIN_ID = self.previous_admin
        self.tempdir.cleanup()

    def test_price_validation_rejects_invalid_and_unbounded_values(self):
        self.assertEqual(main.validate_plan_price("9.999"), 10.0)
        for value in ("nan", "inf", "-1", "0", "10001", "not a number"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                main.validate_plan_price(value)

    def test_full_platform_fee_preserves_zero_creator_net(self):
        main.init_db()
        main.set_setting("platform_fee", "100")
        fee, net = main.calc_fee(25)
        self.assertEqual(fee, 25.0)
        self.assertEqual(net, 0.0)

    def test_config_requires_a_real_looking_token(self):
        previous_token = main.TELEGRAM_TOKEN
        try:
            main.TELEGRAM_TOKEN = ""
            with self.assertRaisesRegex(RuntimeError, "TELEGRAM_TOKEN"):
                main.validate_runtime_config()
        finally:
            main.TELEGRAM_TOKEN = previous_token

    def test_v4_media_migration_is_preserving_and_idempotent(self):
        conn = sqlite3.connect(main.DB_FILE)
        conn.execute("""CREATE TABLE content (
            id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id INTEGER, title TEXT,
            description TEXT, file_ids TEXT, media_types TEXT,
            is_premium INTEGER DEFAULT 1, views INTEGER DEFAULT 0, created_at TEXT
        )""")
        conn.execute(
            "INSERT INTO content (creator_id,title,file_ids,media_types,created_at) VALUES (?,?,?,?,?)",
            (123, "legacy", json.dumps(["photo-file", "video-file"]),
             json.dumps(["photo", "video"]), "2026-01-01T00:00:00"),
        )
        conn.commit()
        conn.close()

        main.init_db()
        main.init_db()
        conn = sqlite3.connect(main.DB_FILE)
        rows = conn.execute("SELECT title,file_id,media_type FROM content ORDER BY id").fetchall()
        conn.close()
        self.assertEqual(rows, [("legacy", "photo-file", "photo"),
                                ("legacy", "video-file", "video")])

    def test_v4_subscription_constraint_is_removed_without_losing_rows(self):
        conn = sqlite3.connect(main.DB_FILE)
        conn.execute("""CREATE TABLE subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, creator_id INTEGER,
            plan TEXT, amount REAL, status TEXT DEFAULT 'active', start_date TEXT,
            end_date TEXT, payment_method TEXT, created_at TEXT,
            UNIQUE(user_id, creator_id)
        )""")
        conn.execute("""INSERT INTO subscriptions
            (user_id,creator_id,plan,amount,status,start_date,end_date,payment_method,created_at)
            VALUES (456,123,'quarterly',25,'active','2026-01-01','2026-04-01','manual','2026-01-01')""")
        conn.commit()
        conn.close()

        main.init_db()
        conn = sqlite3.connect(main.DB_FILE)
        original = conn.execute("SELECT user_id,creator_id,plan_type,amount FROM subscriptions").fetchone()
        conn.execute("""INSERT INTO subscriptions
            (user_id,creator_id,plan_type,amount,status,start_date,end_date,credits_left,payment_method,created_at)
            VALUES (456,123,'pack3',4.99,'active','2026-01-01','2026-01-01',3,'manual','2026-01-01')""")
        count = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id=456 AND creator_id=123").fetchone()[0]
        conn.close()
        self.assertEqual(original, (456, 123, "quarterly", 25.0))
        self.assertEqual(count, 2)

    def test_legacy_creator_gets_plans_without_losing_prices(self):
        main.init_db()
        conn = sqlite3.connect(main.DB_FILE)
        conn.execute("ALTER TABLE creators ADD COLUMN monthly_price REAL DEFAULT 9.99")
        conn.execute("ALTER TABLE creators ADD COLUMN quarterly_price REAL DEFAULT 24.99")
        conn.execute("""INSERT INTO users
            (user_id,first_name,role,creator_verified) VALUES (123,'Old creator','creator',2)""")
        conn.execute("""INSERT INTO creators
            (user_id,display_name,monthly_price,quarterly_price) VALUES (123,'Old creator',12.50,31.00)""")
        conn.commit()
        conn.close()

        main.init_db()
        conn = sqlite3.connect(main.DB_FILE)
        prices = dict(conn.execute("SELECT plan_type,price FROM creator_plans WHERE creator_id=123"))
        conn.close()
        self.assertEqual(prices["monthly"], 12.5)
        self.assertEqual(prices["quarterly"], 31.0)
        self.assertIn("videocall", prices)

    def test_html_escaping(self):
        self.assertEqual(main.escape_html("<b>&"), "&lt;b&gt;&amp;")

    def test_approved_transaction_cannot_be_applied_twice(self):
        main.init_db()
        conn = sqlite3.connect(main.DB_FILE)
        conn.execute("INSERT INTO users (user_id, first_name, role, creator_verified) VALUES (123,'Creator','creator',2)")
        conn.execute("INSERT INTO creators (user_id, display_name) VALUES (123,'Creator')")
        conn.execute("""INSERT INTO creator_plans
            (creator_id,plan_type,name,price,days,credits,description)
            VALUES (123,'pack3','Pack 3',25,0,3,'Pack')""")
        plan_id = conn.execute("SELECT id FROM creator_plans WHERE creator_id=123").fetchone()[0]
        conn.execute("""INSERT INTO transactions
            (user_id,creator_id,type,amount,platform_fee,creator_net,status,plan_id)
            VALUES (456,123,'plan_pack3',25,25,0,'pending',?)""", (plan_id,))
        tx_id = conn.execute("SELECT id FROM transactions").fetchone()[0]
        conn.commit()
        conn.close()
        call = SimpleNamespace(
            data=f"approve_tx_{tx_id}", id="callback-1",
            from_user=SimpleNamespace(id=main.ADMIN_ID),
        )
        with patch.object(main.bot, "send_message"), \
             patch.object(main.bot, "answer_callback_query"):
            main.cb_approve_tx(call)
            main.cb_approve_tx(call)
        conn = sqlite3.connect(main.DB_FILE)
        earnings = conn.execute("SELECT total_earnings FROM creators WHERE user_id=123").fetchone()[0]
        subscribers = conn.execute("SELECT total_subscribers FROM creators WHERE user_id=123").fetchone()[0]
        subs = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id=456 AND creator_id=123").fetchone()[0]
        status = conn.execute("SELECT status FROM transactions WHERE id=?", (tx_id,)).fetchone()[0]
        conn.close()
        self.assertEqual((earnings, subscribers, subs, status), (0.0, 1, 1, "approved"))

    def test_videocall_approval_updates_only_linked_request(self):
        main.init_db()
        conn = sqlite3.connect(main.DB_FILE)
        conn.execute("INSERT INTO users (user_id, first_name, role, creator_verified) VALUES (123,'Creator','creator',2)")
        conn.execute("INSERT INTO creators (user_id, display_name) VALUES (123,'Creator')")
        conn.execute("""INSERT INTO creator_plans
            (creator_id,plan_type,name,price,days,credits,description)
            VALUES (123,'videocall','Video call',40,0,0,'Call')""")
        plan_id = conn.execute("SELECT id FROM creator_plans WHERE creator_id=123").fetchone()[0]
        conn.execute("""INSERT INTO transactions
            (user_id,creator_id,type,amount,platform_fee,creator_net,status,plan_id)
            VALUES (456,123,'videocall',40,8,32,'pending',?)""", (plan_id,))
        tx_id = conn.execute("SELECT id FROM transactions").fetchone()[0]
        conn.execute("INSERT INTO videocalls (user_id,creator_id,amount,status,transaction_id) VALUES (456,123,40,'pending_payment',?)", (tx_id,))
        conn.execute("INSERT INTO videocalls (user_id,creator_id,amount,status,transaction_id) VALUES (456,123,40,'pending_payment',99999)")
        conn.commit()
        conn.close()
        call = SimpleNamespace(
            data=f"approve_tx_{tx_id}", id="callback-2",
            from_user=SimpleNamespace(id=main.ADMIN_ID),
        )
        with patch.object(main.bot, "send_message"), \
             patch.object(main.bot, "answer_callback_query"):
            main.cb_approve_tx(call)
        conn = sqlite3.connect(main.DB_FILE)
        statuses = conn.execute("SELECT status FROM videocalls ORDER BY id").fetchall()
        earnings, subscribers = conn.execute("SELECT total_earnings,total_subscribers FROM creators WHERE user_id=123").fetchone()
        conn.close()
        self.assertEqual(statuses, [("requested",), ("pending_payment",)])
        self.assertEqual((earnings, subscribers), (32.0, 0))

    def test_verification_webapp_uses_reply_keyboard_launch(self):
        main.init_db()
        conn = sqlite3.connect(main.DB_FILE)
        conn.execute("""INSERT INTO users
            (user_id,first_name,age_declared,terms_accepted,age_verified_real)
            VALUES (456,'User',1,1,0)""")
        conn.commit()
        conn.close()
        previous_url = main.WEBAPP_VERIFICATION_URL
        main.WEBAPP_VERIFICATION_URL = "https://verify.example/verification.html"
        call = SimpleNamespace(
            data="request_real_verification", id="callback-webapp",
            from_user=SimpleNamespace(id=456),
            message=SimpleNamespace(chat=SimpleNamespace(id=456, type="private")),
        )
        try:
            with patch.object(main.bot, "send_message") as send_message, \
                 patch.object(main.bot, "answer_callback_query"):
                main.cb_request_verification(call)
            markup = send_message.call_args.kwargs["reply_markup"]
            self.assertIsInstance(markup, main.types.ReplyKeyboardMarkup)
            button = markup.keyboard[0][0]
            self.assertEqual(button["web_app"]["url"], main.WEBAPP_VERIFICATION_URL)
        finally:
            main.WEBAPP_VERIFICATION_URL = previous_url


if __name__ == "__main__":
    unittest.main()
