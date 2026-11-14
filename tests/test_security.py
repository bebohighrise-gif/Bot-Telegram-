import asyncio
import logging
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import helpers  # noqa: F401
import bot
from telegram import Chat, Message, MessageEntity
from telegram.error import BadRequest


def run(coro):
    return asyncio.run(coro)


def make_message(text="hola", user_id=500, **extra):
    user = SimpleNamespace(id=user_id, is_bot=False, full_name="Test", first_name="Test", username="test")
    base = dict(text=text, caption=None, message_id=10, chat_id=bot.GROUP_ID, from_user=user, sender_chat=None,
                reply_text=AsyncMock(), delete=AsyncMock(), photo=(), video=None, document=None, audio=None,
                animation=None, sticker=None, voice=None, video_note=None)
    base.update(extra)
    return SimpleNamespace(**base)


def make_context(member_status="member"):
    bot_api = AsyncMock()
    bot_api.id = 999
    bot_api.get_chat_member.return_value = SimpleNamespace(status=member_status, until_date=None)
    bot_api.get_chat.return_value = SimpleNamespace(title="G", username=None, permissions=None)
    return SimpleNamespace(bot=bot_api, args=[], application=SimpleNamespace(create_task=lambda coro: coro.close()))


def make_update(message, chat_type="private", user_id=1):
    user = message.from_user if hasattr(message, "from_user") and user_id is None else SimpleNamespace(id=user_id, full_name="U", first_name="U", username="u")
    return SimpleNamespace(effective_message=message, effective_user=user, effective_chat=SimpleNamespace(id=user_id if chat_type == "private" else bot.GROUP_ID, type=chat_type), callback_query=None)


class BotTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patches = [
            patch.object(bot, "store", bot.JsonStore(Path(self.tmp.name))),
            patch.object(bot, "admins", set()),
            patch.object(bot, "BOT_OWNER_ID", 1),
            patch.object(bot, "SEED_ADMINS", set()),
            patch.object(bot, "admin_states", bot.FlowStates()),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        bot._group_admin_cache.clear()
        bot._rate_marks.clear()
        bot._permissions_cache.update(at=0.0, value=None)
        bot._last_error_notice = float("-inf")


class LinkTests(BotTestCase):
    def test_hidden_text_link_is_extracted(self):
        message = Message(message_id=1, date=datetime.now(timezone.utc), chat=Chat(id=1, type="supergroup"),
                          text="mira aquí", entities=[MessageEntity(type="text_link", offset=5, length=4, url="https://evil.example/phish")])
        self.assertIn("https://evil.example/phish", bot.extract_links(message))

    def test_bare_domain_detected_by_telegram_is_extracted(self):
        message = Message(message_id=1, date=datetime.now(timezone.utc), chat=Chat(id=1, type="supergroup"),
                          text="entra a t.me/evil ya", entities=[MessageEntity(type="url", offset=8, length=9)])
        self.assertIn("t.me/evil", bot.extract_links(message))
        self.assertFalse(bot.link_allowed("t.me/evil"))

    def test_process_link_deletes_and_notifies_moderators(self):
        message = make_message("https://evil.example", entities=[])
        message.parse_entities = lambda types: {}
        context = make_context()
        run(bot.set_role(2, "moderator", 1))
        assert run(bot.process_link(make_update(message, "supergroup"), context)) is True
        message.delete.assert_awaited()
        recipients = {call.args[0] for call in context.bot.send_message.await_args_list}
        self.assertIn(1, recipients)  # solo el propietario recibe el aviso privado
        self.assertNotIn(bot.GROUP_ID, recipients)
        self.assertEqual(len(run(bot.store.load("pending_links.json"))), 1)


class StoreTests(BotTestCase):
    def test_corrupt_file_is_backed_up_and_defaults_are_not_shared(self):
        path = Path(self.tmp.name) / "settings.json"
        path.write_text("{no es json", encoding="utf-8")
        value = run(bot.store.load("settings.json"))
        value["bad_words"].append("mutado")
        self.assertTrue(list(Path(self.tmp.name).glob("settings.json.corrupt-*")), "debe conservar copia del archivo dañado")
        self.assertEqual(bot.store.defaults["settings.json"]["bad_words"], [])

    def test_save_is_atomic_and_private(self):
        run(bot.store.save("x.json", {"a": 1}))
        path = Path(self.tmp.name) / "x.json"
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertFalse((Path(self.tmp.name) / "x.json.tmp").exists())

    def test_guarded_handlers_do_not_overlap(self):
        active, peak = 0, 0

        async def handler(update, context):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1

        async def scenario():
            wrapped = bot.guarded(handler)
            await asyncio.gather(*(wrapped(None, None) for _ in range(5)))

        with patch.object(bot, "STATE_LOCK", asyncio.Lock()):
            run(scenario())
        self.assertEqual(peak, 1)


class RoleTests(BotTestCase):
    def test_permission_matrix(self):
        for user_id, role in [(10, "admin"), (11, "moderator"), (12, "support"), (13, "announcer")]:
            self.assertTrue(run(bot.set_role(user_id, role, 1)))
        expected = {
            1: {"moderate", "support", "announce", "configure", "owner"},
            10: {"moderate", "support", "announce", "configure"},
            11: {"moderate"}, 12: {"support"}, 13: {"announce"}, 99: set(),
        }
        for user_id, allowed in expected.items():
            for permission in ("moderate", "support", "announce", "configure", "owner"):
                self.assertEqual(run(bot.has_permission(user_id, permission)), permission in allowed, (user_id, permission))

    def test_only_owner_can_manage_roles(self):
        run(bot.set_role(10, "admin", 1))
        message = make_message("/addadmin 77")
        context = make_context()
        context.args = ["77"]
        run(bot.admins_cmd(make_update(message, user_id=10), context))
        self.assertNotIn(77, bot.admins)
        run(bot.admins_cmd(make_update(message, user_id=1), context))
        self.assertIn(77, bot.admins)

    def test_owner_and_seed_admins_cannot_be_demoted(self):
        with patch.object(bot, "SEED_ADMINS", {42}):
            self.assertFalse(run(bot.set_role(1, "user", 1)))
            self.assertFalse(run(bot.set_role(42, "user", 1)))

    def test_demoted_admin_loses_access(self):
        run(bot.set_role(10, "admin", 1))
        self.assertTrue(run(bot.is_admin(10)))
        run(bot.set_role(10, "user", 1))
        self.assertFalse(run(bot.is_admin(10)))
        self.assertFalse(run(bot.has_permission(10, "moderate")))


class FlowTests(BotTestCase):
    def test_flow_state_expires(self):
        bot.admin_states[5] = {"flow": "ticket"}
        self.assertIsNotNone(bot.admin_states.get(5))
        with patch.object(bot.time, "monotonic", return_value=time.monotonic() + bot.STATE_TTL + 1):
            self.assertIsNone(bot.admin_states.get(5))

    def test_flows_are_ignored_in_groups(self):
        bot.admin_states[1] = {"flow": "announcement"}
        message = make_message("texto cualquiera", user_id=1)
        context = make_context()
        with patch.object(bot, "publish_announcement", AsyncMock()) as publish:
            run(bot.interactive_text(make_update(message, chat_type="supergroup", user_id=1), context))
        publish.assert_not_awaited()

    def test_appeal_flow_completes(self):
        bot.admin_states[500] = {"flow": "appeal"}
        message = make_message("me banearon por error", user_id=500)
        update = make_update(message, user_id=500)
        run(bot.interactive_text(update, make_context()))
        self.assertEqual(len(run(bot.store.load("appeals.json"))), 1)
        self.assertIsNone(bot.admin_states.get(500))

    def test_ticket_reply_is_one_shot(self):
        run(bot.set_role(2, "support", 1))
        run(bot.store.save("tickets.json", {"T1": {"ticket_id": "T1", "user_id": 700, "status": "en_proceso", "admin_id": 2}}))
        bot.admin_states[2] = {"flow": "ticket_reply", "ticket_id": "T1"}
        context = make_context()
        run(bot.interactive_text(make_update(make_message("hola, ya lo miramos", user_id=2), user_id=2), context))
        self.assertIsNone(bot.admin_states.get(2), "el estado no debe quedarse pegado")
        self.assertEqual(context.bot.send_message.await_args.args[0], 700)
        # un mensaje privado posterior del admin ya NO se reenvía al usuario
        context.bot.send_message.reset_mock()
        run(bot.interactive_text(make_update(make_message("nota personal", user_id=2), user_id=2), context))
        context.bot.send_message.assert_not_awaited()


class JoinAndVerifyTests(BotTestCase):
    def _change(self, old, new, is_member=True):
        user = SimpleNamespace(id=500, is_bot=False, first_name="Nuevo", full_name="Nuevo")
        member = lambda status: SimpleNamespace(status=status, user=user, is_member=is_member)  # noqa: E731
        return SimpleNamespace(chat_member=SimpleNamespace(chat=SimpleNamespace(id=bot.GROUP_ID), old_chat_member=member(old), new_chat_member=member(new)))

    def test_mute_does_not_trigger_welcome_again(self):
        context = make_context()
        run(bot.new_member(self._change("member", "restricted"), context))
        context.bot.send_message.assert_not_awaited()
        context.bot.restrict_chat_member.assert_not_awaited()

    def test_real_join_restricts_and_sends_verification(self):
        context = make_context()
        run(bot.new_member(self._change("left", "member"), context))
        context.bot.restrict_chat_member.assert_awaited_once()
        context.bot.send_message.assert_awaited_once()

    def _call(self, user_id=500, target=500):
        call = SimpleNamespace(data=f"verify:{target}", from_user=SimpleNamespace(id=user_id), answer=AsyncMock(), edit_message_text=AsyncMock())
        return call, SimpleNamespace(callback_query=call)

    def test_muted_user_cannot_unmute_with_verify_button(self):
        call, update = self._call()
        context = make_context()
        context.bot.get_chat_member.return_value = SimpleNamespace(status="restricted", until_date=datetime.now(timezone.utc) + timedelta(minutes=5))
        run(bot.verify_callback(update, context))
        context.bot.restrict_chat_member.assert_not_awaited()
        self.assertEqual(call.answer.await_count, 1)
        self.assertNotIn("500", run(bot.store.load("verified.json")))

    def test_gate_restriction_is_released_with_group_default_permissions(self):
        call, update = self._call()
        call.message = SimpleNamespace(message_id=321)
        context = make_context()
        defaults = SimpleNamespace(can_send_messages=True)
        context.bot.get_chat.return_value = SimpleNamespace(permissions=defaults)
        context.bot.get_chat_member.return_value = SimpleNamespace(status="restricted", until_date=None)
        run(bot.verify_callback(update, context))
        self.assertIs(context.bot.restrict_chat_member.await_args.args[2], defaults)
        context.bot.delete_message.assert_awaited_once_with(bot.GROUP_ID, 321)
        self.assertEqual(call.answer.await_count, 1)
        self.assertIn("500", run(bot.store.load("verified.json")))

    def test_button_of_another_user_is_rejected(self):
        call, update = self._call(user_id=501)
        run(bot.verify_callback(update, make_context()))
        self.assertEqual(call.answer.await_count, 1)


class ModerationTests(BotTestCase):
    def test_media_is_deleted_for_regular_users_only(self):
        context = make_context()
        photo = make_message(None, photo=("p",))
        run(bot.media_moderation(make_update(photo, "supergroup", user_id=500), context))
        photo.delete.assert_awaited()
        anonymous = make_message(None, user_id=bot.ANON_ADMIN_ID, photo=("p",))
        run(bot.media_moderation(make_update(anonymous, "supergroup", user_id=bot.ANON_ADMIN_ID), context))
        anonymous.delete.assert_not_awaited()

    def test_group_admins_are_exempt(self):
        context = make_context(member_status="administrator")
        message = make_message("https://evil.example")
        self.assertTrue(run(bot.is_exempt(context, message)))

    def test_mute_requires_valid_minutes(self):
        run(bot.set_role(2, "moderator", 1))
        context = make_context()
        for args in (["123"], ["123", "abc"], ["123", "0"], ["123", "999999"]):
            context.args = args
            run(bot.moderate_user(make_update(make_message("/mute " + " ".join(args), user_id=2), user_id=2), context))
        context.bot.restrict_chat_member.assert_not_awaited()
        context.args = ["123", "30"]
        run(bot.moderate_user(make_update(make_message("/mute 123 30", user_id=2), user_id=2), context))
        context.bot.restrict_chat_member.assert_awaited_once()

    def test_staff_cannot_be_sanctioned(self):
        run(bot.set_role(3, "admin", 1))
        context = make_context()
        context.args = ["3", "10"]
        run(bot.moderate_user(make_update(make_message("/mute 3 10", user_id=1), user_id=1), context))
        context.bot.restrict_chat_member.assert_not_awaited()

    def test_ban_confirmation_expires(self):
        old = (datetime.now(timezone.utc) - timedelta(seconds=bot.CONFIRM_TTL + 5)).isoformat(timespec="seconds")
        run(bot.store.save("moderation_confirmations.json", {"abc": {"action": "ban", "target": 123, "reason": "x", "admin_id": 1, "created_at": old}}))
        call = SimpleNamespace(data="confirmmod:abc", from_user=SimpleNamespace(id=1, full_name="O", first_name="O"), answer=AsyncMock(), edit_message_text=AsyncMock())
        context = make_context()
        run(bot.moderation_confirmation_callback(SimpleNamespace(callback_query=call), context))
        context.bot.ban_chat_member.assert_not_awaited()

    def test_word_filter_escalation_and_separate_counter(self):
        run(bot.store.save("settings.json", {"moderation": True, "word_filter": True, "bad_words": ["estafa"], "word_actions": {}}))
        run(bot.store.save("warns.json", {f"{bot.GROUP_ID}:500": 2}))  # 2 /warn manuales no deben adelantar el ban
        context = make_context()
        message = make_message("esto es una estafa")
        run(bot.moderate_words(make_update(message, "supergroup", user_id=500), context))
        context.bot.ban_chat_member.assert_not_awaited()
        context.bot.restrict_chat_member.assert_awaited_once()
        self.assertEqual(run(bot.store.load("warns.json"))[f"words:{bot.GROUP_ID}:500"], 1)


class CallbackTests(BotTestCase):
    def _poll_call(self, user_id):
        call = SimpleNamespace(data="voto:P1:0", from_user=SimpleNamespace(id=user_id), answer=AsyncMock(), edit_message_text=AsyncMock(),
                               message=SimpleNamespace(reply_markup=None))
        return call

    def test_poll_vote_answers_once_and_blocks_double_vote(self):
        run(bot.store.save("encuestas.json", {"P1": {"id": "P1", "title": "T", "options": ["a", "b"], "votes": {}, "closed": False}}))
        first = self._poll_call(500)
        run(bot.poll_callback(SimpleNamespace(callback_query=first), make_context()))
        self.assertEqual(first.answer.await_count, 1)
        second = self._poll_call(500)
        run(bot.poll_callback(SimpleNamespace(callback_query=second), make_context()))
        self.assertEqual(second.answer.await_count, 1)
        self.assertTrue(second.answer.await_args.kwargs.get("show_alert"))

    def test_poll_rejects_out_of_range_option(self):
        run(bot.store.save("encuestas.json", {"P1": {"id": "P1", "title": "T", "options": ["a"], "votes": {}, "closed": False}}))
        call = self._poll_call(500)
        call.data = "voto:P1:9"
        run(bot.poll_callback(SimpleNamespace(callback_query=call), make_context()))
        self.assertEqual(run(bot.store.load("encuestas.json"))["P1"]["votes"], {})

    def test_callbacks_require_permission(self):
        call = SimpleNamespace(data="validar:x", from_user=SimpleNamespace(id=500), answer=AsyncMock(), edit_message_text=AsyncMock())
        run(bot.link_callback(SimpleNamespace(callback_query=call), make_context()))
        self.assertTrue(call.answer.await_args.kwargs.get("show_alert"))
        call.edit_message_text.assert_not_awaited()

    def test_support_role_cannot_resolve_links(self):
        run(bot.set_role(2, "support", 1))
        call = SimpleNamespace(data="validar:x", from_user=SimpleNamespace(id=2, full_name="S", first_name="S"), answer=AsyncMock(), edit_message_text=AsyncMock())
        run(bot.link_callback(SimpleNamespace(callback_query=call), make_context()))
        call.edit_message_text.assert_not_awaited()


class MiscTests(BotTestCase):
    def test_parse_translation(self):
        data = [[["Hola mundo", "Hello world", None, None, 1]], None, "en"]
        self.assertEqual(bot.parse_translation(data), ("Hola mundo", "en"))

    def test_translation_skips_spanish_and_short_text(self):
        message = make_message("ok")
        with patch.object(bot, "translate_text", AsyncMock(return_value=("Vale", "en"))) as translate:
            run(bot.translate_and_reply(message))
            translate.assert_not_awaited()
        message = make_message("buenos días a todos")
        with patch.object(bot, "translate_text", AsyncMock(return_value=("buenas días a todos", "es"))):
            run(bot.translate_and_reply(message))
        message.reply_text.assert_not_awaited()
        message = make_message("good morning everyone")
        with patch.object(bot, "translate_text", AsyncMock(return_value=("buenos días a todos", "en"))):
            run(bot.translate_and_reply(message))
        message.reply_text.assert_awaited_once()

    def test_error_handler_ignores_not_modified_and_rate_limits_notices(self):
        context = make_context()
        context.error = BadRequest("Message is not modified")
        run(bot.error_handler(None, context))
        context.bot.send_message.assert_not_awaited()
        context.error = RuntimeError("boom")
        run(bot.error_handler(None, context))
        run(bot.error_handler(None, context))
        self.assertEqual(context.bot.send_message.await_count, 1)
        self.assertNotIn("boom", context.bot.send_message.await_args.args[1])  # no filtra detalles

    def test_token_is_never_logged_by_http_clients(self):
        for name in ("httpx", "httpcore"):
            self.assertGreaterEqual(logging.getLogger(name).level, logging.WARNING)

    def test_invalid_numeric_env_fails_with_clear_message(self):
        with patch.dict("os.environ", {"GROUP_ID": "abc"}):
            with self.assertRaises(RuntimeError):
                bot._int_env("GROUP_ID")

    def test_build_app_registers_handlers_and_expected_updates(self):
        app = bot.build_app()
        self.assertGreater(sum(len(handlers) for handlers in app.handlers.values()), 40)
        self.assertIn("chat_member", [str(item.value) for item in bot.ALLOWED_UPDATES])

    def test_post_init_survives_admin_without_private_chat(self):
        async def set_my_commands(commands, scope=None):
            if getattr(scope, "chat_id", None) == 77:
                raise BadRequest("Chat not found")

        application = SimpleNamespace(bot=AsyncMock(), job_queue=SimpleNamespace(run_repeating=lambda *a, **k: None))
        application.bot.set_my_commands = AsyncMock(side_effect=set_my_commands)
        with patch.object(bot, "SEED_ADMINS", {77}):
            run(bot.post_init(application))  # antes: el arranque fallaba si un admin nunca había iniciado el bot
        application.bot.set_chat_menu_button.assert_awaited()

    def test_wipe_reminder_sent_once(self):
        target = datetime.now(timezone.utc) + timedelta(minutes=30)
        run(bot.store.save("wipe_config.json", {"manual": target.isoformat(), "reminders": [700]}))
        context = make_context()
        run(bot.send_wipe_reminders(context))
        run(bot.send_wipe_reminders(context))
        self.assertEqual(context.bot.send_message.await_count, 1)

    def test_giveaway_winner_is_a_participant(self):
        run(bot.store.save("giveaways.json", {"G1": {"id": "G1", "prize": "Skin", "participants": [11, 12], "status": "active"}}))
        run(bot.set_role(2, "announcer", 1))
        context = make_context()
        context.args = ["cerrar", "G1"]
        context.bot.get_chat_member.return_value = SimpleNamespace(user=SimpleNamespace(full_name="Ganador"), status="member")
        run(bot.giveaway_cmd(make_update(make_message("/sorteo cerrar G1", user_id=2), user_id=2), context))
        self.assertIn(run(bot.store.load("giveaways.json"))["G1"]["winner"], {11, 12})


if __name__ == "__main__":
    unittest.main()
