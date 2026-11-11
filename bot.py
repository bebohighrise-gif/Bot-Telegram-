#!/usr/bin/env python3
"""Rust 133 Dev Blog community bot.

Async python-telegram-bot v20+, JSON persistence protected by asyncio.Lock.
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser
from deep_translator import GoogleTranslator
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, ChatMemberHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
LOG = logging.getLogger("rust133")
TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
GROUP_ID = int(os.getenv("GROUP_ID", "0") or 0)
GROUP_NAME = os.getenv("GROUP_NAME", "GAMAER CITY").strip() or "GAMAER CITY"
SEED_ADMINS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().lstrip("-").isdigit()}
DATA_DIR = Path(os.getenv("DATA_DIR", "."))
DATA_DIR.mkdir(parents=True, exist_ok=True)
URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>]+")
NO_LINKS = {"rust.facepunch.com", "facepunch.com", "store.steampowered.com", "steamcommunity.com"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


def uid() -> str:
    return uuid.uuid4().hex[:10]


def mention(user: Any) -> str:
    name = esc(getattr(user, "first_name", None) or getattr(user, "username", None) or getattr(user, "id", "usuario"))
    return f"<a href=\"tg://user?id={getattr(user, 'id', 0)}\">{name}</a>"


class JsonStore:
    def __init__(self, root: Path):
        self.root = root
        self.lock = asyncio.Lock()
        self.defaults = {
            "admins.json": [], "pending_links.json": {}, "resolved_links.json": {},
            "warns.json": {}, "responder_sessions.json": {}, "tickets.json": {},
            "tickets_cerrados.json": {}, "welcome.json": {"enabled": False, "text": "👋 Bienvenido {nombre} a {grupo}!", "file_id": None},
            "wipe_config.json": {"manual": None, "reminders": []}, "encuestas.json": {},
            "server.json": {"name": "GAMAER CITY", "ip": ""},
            "roles.json": {}, "verified.json": {}, "moderation_logs.json": [],
            "appeals.json": {}, "reports.json": {}, "events.json": {}, "giveaways.json": {},
            "official_links.json": {"discord": "", "web": "", "channel": "", "donaciones": ""},
            "auto_replies.json": {"enabled": True, "rules": {
                "hola": "👋 ¡Hola! Bienvenido a GAMAER CITY. Usa /help para ver los comandos.",
                "reglas": "📜 Puedes consultar las reglas con /reglas.",
                "ip": "🎮 La IP del servidor está disponible con /servidor.",
                "wipe": "🧨 Consulta el próximo wipe con /wipe.",
                "ayuda": "ℹ️ Usa /help para ver la ayuda de GAMAER CITY."
            }},
            "rules.txt": "📜 <b>Reglas de Rust 133 Dev Blog</b>\n\n1. Respeta a la comunidad.\n2. No spam, estafas ni phishing.\n3. No enlaces a otros servidores sin autorización.\n4. No contenido ilegal o datos personales.\n5. La moderación puede borrar mensajes y sancionar cuentas.",
            "settings.json": {"moderation": True, "word_filter": True, "bad_words": [], "word_actions": {}},
        }

    def path(self, name: str) -> Path:
        return self.root / name

    async def load(self, name: str) -> Any:
        async with self.lock:
            path = self.path(name)
            if not path.exists():
                value = self.defaults.get(name, {})
                await self._write_unlocked(name, value)
                return value.copy() if isinstance(value, (dict, list)) else value
            try:
                if name.endswith(".txt"):
                    return path.read_text(encoding="utf-8")
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                LOG.error("No se pudo leer %s: %s", name, exc)
                return self.defaults.get(name, {})

    async def save(self, name: str, value: Any) -> None:
        async with self.lock:
            await self._write_unlocked(name, value)

    async def _write_unlocked(self, name: str, value: Any) -> None:
        path = self.path(name)
        temp = path.with_suffix(path.suffix + ".tmp")
        if name.endswith(".txt"):
            temp.write_text(str(value), encoding="utf-8")
        else:
            temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)


store = JsonStore(DATA_DIR)
admins: set[int] = set(SEED_ADMINS)
recent_messages: deque[Any] = deque(maxlen=15)
admin_states: dict[int, dict[str, Any]] = {}
translation_locks: set[int] = set()


def valid_token() -> bool:
    return bool(re.fullmatch(r"\d{6,12}:[A-Za-z0-9_-]{20,}", TOKEN))


async def is_admin(user_id: int | None) -> bool:
    return bool(user_id and user_id in admins)


async def refresh_admins() -> None:
    global admins
    stored = await store.load("admins.json")
    admins = set(SEED_ADMINS) | {int(x) for x in stored if str(x).lstrip("-").isdigit()}
    await store.save("admins.json", sorted(admins))


async def audit(action: str, actor_id: int | None = None, target_id: int | None = None, details: str = "") -> None:
    logs = await store.load("moderation_logs.json")
    logs.append({"action": action, "actor_id": actor_id, "target_id": target_id, "details": details[:1000], "timestamp": now()})
    await store.save("moderation_logs.json", logs[-5000:])


async def role_of(user_id: int | None) -> str:
    if user_id in SEED_ADMINS: return "owner"
    roles = await store.load("roles.json")
    return roles.get(str(user_id), "admin" if await is_admin(user_id) else "user")


async def has_permission(user_id: int | None, permission: str) -> bool:
    role = await role_of(user_id)
    permissions = {
        "owner": {"all"}, "admin": {"moderate", "support", "announce", "configure"},
        "moderator": {"moderate"}, "support": {"support"}, "announcer": {"announce"},
    }
    return "all" in permissions.get(role, set()) or permission in permissions.get(role, set())


async def private_admin(update: Update) -> bool:
    user = update.effective_user
    if not update.effective_chat or update.effective_chat.type != "private" or not await is_admin(user.id if user else None):
        if update.effective_chat and update.effective_chat.type == "private":
            await update.effective_message.reply_text("🔒 Solo los administradores autorizados pueden usar este comando.")
        return False
    return True


def group_message(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id == GROUP_ID)


def link_host(url: str) -> str:
    return re.sub(r"(?i)^https?://", "", url).split("/", 1)[0].split(":", 1)[0].lower().lstrip("www.")


def link_allowed(url: str) -> bool:
    host = link_host(url)
    return any(host == domain or host.endswith("." + domain) for domain in NO_LINKS)


async def automatic_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.effective_message
    if not group_message(update) or not message.text or message.text.startswith("/") or URL_RE.search(message.text) or await is_admin(message.from_user.id):
        return False
    config = await store.load("auto_replies.json")
    if not config.get("enabled", True): return False
    text = message.text.casefold()
    for trigger, reply in config.get("rules", {}).items():
        if re.search(r"(?<!\w)" + re.escape(trigger.casefold()) + r"(?!\w)", text):
            try:
                await message.reply_text(reply, parse_mode=ParseMode.HTML)
            except Exception:
                LOG.warning("No se pudo enviar respuesta automática", exc_info=True)
            return True
    return False


def word_matches(text: str, words: list[str]) -> str | None:
    normalized = text.casefold()
    for word in words:
        candidate = str(word).strip().casefold()
        if candidate and re.search(r"(?<!\w)" + re.escape(candidate) + r"(?!\w)", normalized):
            return candidate
    return None


async def moderate_words(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.effective_message
    if not group_message(update) or not message.from_user or await is_admin(message.from_user.id):
        return False
    settings = await store.load("settings.json")
    matched = word_matches(message.text or message.caption or "", settings.get("bad_words", []))
    if not settings.get("moderation", True) or not settings.get("word_filter", True) or not matched:
        return False
    try:
        await message.delete()
        await context.bot.send_message(GROUP_ID, "⚠️ El mensaje fue retirado por incumplir las reglas de la comunidad.")
    except Exception:
        LOG.warning("No se pudo retirar mensaje filtrado", exc_info=True)
    warns = await store.load("warns.json")
    key = f"{GROUP_ID}:{message.from_user.id}"
    warns[key] = int(warns.get(key, 0)) + 1
    await store.save("warns.json", warns)
    action = settings.get("word_actions", {}).get(matched, "escalate")
    if action == "escalate":
        if warns[key] == 1:
            escalation = "silenciado 5 minutos y advertido"
            minutes = 5
        elif warns[key] == 2:
            escalation = "silenciado 20 minutos y advertido"
            minutes = 20
        else:
            escalation = "expulsado permanentemente y baneado"
            minutes = 0
        try:
            if warns[key] >= 3:
                await context.bot.ban_chat_member(GROUP_ID, message.from_user.id)
            else:
                from telegram import ChatPermissions
                await context.bot.restrict_chat_member(
                    GROUP_ID, message.from_user.id,
                    ChatPermissions(can_send_messages=False),
                    until_date=datetime.now(timezone.utc) + timedelta(minutes=minutes),
                )
        except Exception:
            LOG.warning("No se pudo aplicar escalada por palabra", exc_info=True)
        try:
            await context.bot.send_message(GROUP_ID, f"⚠️ {mention(message.from_user)}: {escalation} por una infracción de palabras filtradas.", parse_mode=ParseMode.HTML)
        except Exception:
            pass
        return True
    if action == "mute":
        try:
            from telegram import ChatPermissions
            await context.bot.restrict_chat_member(GROUP_ID, message.from_user.id, ChatPermissions(can_send_messages=False), until_date=datetime.now(timezone.utc) + timedelta(minutes=60))
        except Exception: LOG.warning("No se pudo silenciar por palabra configurada", exc_info=True)
    elif action in {"kick", "ban"}:
        try:
            await context.bot.ban_chat_member(GROUP_ID, message.from_user.id)
            if action == "kick": await context.bot.unban_chat_member(GROUP_ID, message.from_user.id)
        except Exception: LOG.warning("No se pudo aplicar %s por palabra configurada", action, exc_info=True)
    # 'warn' es el valor seguro. Kick/ban/mute solo ocurren si el admin
    # configuró explícitamente esa acción para esa palabra.
    try:
        label = {"warn": "advertencia", "mute": "silenciado 60 minutos", "kick": "expulsado", "ban": "baneado"}.get(action, "revisado")
        await context.bot.send_message(GROUP_ID, f"ℹ️ Moderación automática configurada: {label}. Si crees que fue un falso positivo, contacta con un administrador mediante /soporte.")
    except Exception:
        pass
    return True


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_text = ("\n\n<b>Admin</b>\n/addadmin /deladmin /listadmins\n/pendientes /responder /anuncio\n"
                  "/moderacion on|off /ban /kick /mute /unmute /warn\n/soporte /tickets /bienvenida /setbienvenida\n"
                  "/setwipe /encuesta /encuestas /cerrar_encuesta /setreglas\n/servidor /setservidor /filtro /auto") if await is_admin(update.effective_user.id) else ""
    await update.effective_message.reply_text(f"🤖 <b>{esc(GROUP_NAME)}</b>\n/reglas — reglas\n/devblog — último devblog\n/servidor — IP del servidor\n/wipe — próximo wipe\n/soporte — abrir ticket\n/cancelar — cancelar flujo" + admin_text, parse_mode=ParseMode.HTML)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("✅ Bot conectado. Usa /help para ver los comandos.", parse_mode=ParseMode.HTML)


async def admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    cmd = update.effective_message.text.split()[0].split("@")[0]
    data = await store.load("admins.json")
    if cmd == "/listadmins":
        await update.effective_message.reply_text("👮 Admins:\n" + "\n".join(f"• <code>{x}</code>" for x in sorted(admins)), parse_mode=ParseMode.HTML); return
    if len(context.args) != 1 or not context.args[0].lstrip("-").isdigit():
        await update.effective_message.reply_text("Usa un user_id numérico. Telegram no permite resolver @username de forma fiable sin interacción previa."); return
    target = int(context.args[0])
    if cmd == "/addadmin":
        admins.add(target); await store.save("admins.json", sorted(admins)); await update.effective_message.reply_text("✅ Admin añadido.")
    elif cmd == "/deladmin":
        if target in SEED_ADMINS: await update.effective_message.reply_text("❌ No se puede quitar un admin definido en ADMIN_IDS."); return
        admins.discard(target); await store.save("admins.json", sorted(admins)); await update.effective_message.reply_text("✅ Admin eliminado.")


async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(await store.load("rules.txt"), parse_mode=ParseMode.HTML)


async def setrules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    text = update.effective_message.text.partition(" ")[2].strip()
    if not text: await update.effective_message.reply_text("Usa /setreglas texto"); return
    await store.save("rules.txt", esc(text)); await update.effective_message.reply_text("✅ Reglas guardadas.")


async def announcement_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    text = update.effective_message.text.partition(" ")[2].strip()
    try:
        source = update.effective_message.reply_to_message
        footer = f"\n\n— Enviado por {mention(update.effective_user)}"
        if source:
            if text and source.caption:
                text = f"{source.caption}\n\n{text}"
            if source.text or text:
                await context.bot.send_message(GROUP_ID, f"📢 <b>ANUNCIO</b>\n\n{esc(text or source.text)}{footer}", parse_mode=ParseMode.HTML)
            else:
                await context.bot.copy_message(GROUP_ID, update.effective_chat.id, source.message_id)
                await context.bot.send_message(GROUP_ID, f"— Enviado por {mention(update.effective_user)}", parse_mode=ParseMode.HTML)
        elif text:
            await context.bot.send_message(GROUP_ID, f"📢 <b>ANUNCIO</b>\n\n{esc(text)}{footer}", parse_mode=ParseMode.HTML)
        else:
            await update.effective_message.reply_text("Escribe /anuncio texto o responde con /anuncio a un mensaje multimedia."); return
        await update.effective_message.reply_text("✅ Anuncio enviado.")
    except Exception as exc: LOG.exception("announcement"); await update.effective_message.reply_text(f"❌ No se pudo anunciar: {esc(exc)}")


async def moderation_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    if not context.args or context.args[0].lower() not in {"on", "off"}: await update.effective_message.reply_text("Usa /moderacion on|off"); return
    settings = await store.load("settings.json"); settings["moderation"] = context.args[0].lower() == "on"; await store.save("settings.json", settings)
    await update.effective_message.reply_text(f"✅ Moderación {'activada' if settings['moderation'] else 'desactivada'}.")


async def server_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    server = await store.load("server.json")
    if not server.get("ip"):
        await update.effective_message.reply_text("ℹ️ La IP del servidor todavía no ha sido configurada por el equipo.")
        return
    await update.effective_message.reply_text(
        f"🎮 <b>{esc(server.get('name', GROUP_NAME))}</b>\n"
        f"🌐 IP del servidor: <code>{esc(server['ip'])}</code>", parse_mode=ParseMode.HTML)


async def setserver_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    if not context.args:
        await update.effective_message.reply_text("Usa /setservidor IP [nombre del servidor]")
        return
    ip = context.args[0]
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", ip):
        await update.effective_message.reply_text("IP inválida."); return
    server = await store.load("server.json")
    server.update({"ip": ip, "name": " ".join(context.args[1:]) or server.get("name", GROUP_NAME)})
    await store.save("server.json", server)
    await update.effective_message.reply_text("✅ Datos del servidor guardados.")


async def filter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    settings = await store.load("settings.json")
    if not context.args:
        actions = settings.get("word_actions", {})
        words = settings.get("bad_words", [])
        display = ", ".join(f"{word} ({actions.get(word, 'escalate')})" for word in words) or "ninguna"
        await update.effective_message.reply_text(f"Filtro: {'activo' if settings.get('word_filter', True) else 'inactivo'}\nPalabras: {display}")
        return
    action, values = context.args[0].lower(), context.args[1:]
    if action in {"on", "off"}:
        settings["word_filter"] = action == "on"
    elif action == "add" and len(values) >= 1:
        chosen_action = values[-1].lower() if values[-1].lower() in {"warn", "mute", "kick", "ban", "escalate"} else "escalate"
        word_values = values[:-1] if values[-1].lower() in {"warn", "mute", "kick", "ban", "escalate"} else values
        if not word_values:
            await update.effective_message.reply_text("Indica una palabra antes de la acción."); return
        settings["bad_words"] = sorted(set(settings.get("bad_words", []) + [x.casefold() for x in word_values]))
        settings.setdefault("word_actions", {}).update({x.casefold(): chosen_action for x in word_values})
    elif action == "remove" and values:
        settings["bad_words"] = [x for x in settings.get("bad_words", []) if x.casefold() not in {v.casefold() for v in values}]
        for value in values: settings.setdefault("word_actions", {}).pop(value.casefold(), None)
    elif action == "list":
        await update.effective_message.reply_text("Palabras filtradas: " + (", ".join(settings.get("bad_words", [])) or "ninguna")); return
    else:
        await update.effective_message.reply_text("Usa /filtro on|off, /filtro add palabra [escalate|warn|mute|kick|ban], /filtro remove palabra o /filtro list"); return
    await store.save("settings.json", settings); await update.effective_message.reply_text("✅ Filtro actualizado.")


async def auto_reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    config = await store.load("auto_replies.json")
    if not context.args:
        status = "activo" if config.get("enabled", True) else "inactivo"
        await update.effective_message.reply_text(f"Respuestas automáticas: {status}\n" + "\n".join(f"• {k}: {v}" for k, v in config.get("rules", {}).items()))
        return
    action = context.args[0].lower()
    if action in {"on", "off"}:
        config["enabled"] = action == "on"
    elif action == "list":
        await update.effective_message.reply_text("\n".join(f"• {k}: {v}" for k, v in config.get("rules", {}).items()) or "No hay respuestas configuradas.")
        return
    elif action == "remove" and len(context.args) >= 2:
        config.get("rules", {}).pop(context.args[1].casefold(), None)
    elif action == "add" and len(context.args) >= 3:
        trigger = context.args[1].casefold(); reply = " ".join(context.args[2:])
        config.setdefault("rules", {})[trigger] = reply[:1000]
    else:
        await update.effective_message.reply_text("Usa /auto on|off, /auto list, /auto add palabra respuesta o /auto remove palabra"); return
    await store.save("auto_replies.json", config); await update.effective_message.reply_text("✅ Respuestas automáticas actualizadas.")


async def moderate_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    if not context.args or not context.args[0].lstrip("-").isdigit(): await update.effective_message.reply_text("Usa /ban ID [motivo]"); return
    target = int(context.args[0]); cmd = update.effective_message.text.split()[0].split("@")[0]; reason = " ".join(context.args[1:]) or "Sin motivo"
    try:
        if cmd == "/ban": await context.bot.ban_chat_member(GROUP_ID, target)
        elif cmd == "/kick": await context.bot.ban_chat_member(GROUP_ID, target); await context.bot.unban_chat_member(GROUP_ID, target)
        elif cmd == "/mute":
            minutes = max(1, int(context.args[1])); until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
            from telegram import ChatPermissions
            await context.bot.restrict_chat_member(GROUP_ID, target, ChatPermissions(can_send_messages=False), until_date=until)
        elif cmd == "/unmute":
            from telegram import ChatPermissions
            await context.bot.restrict_chat_member(GROUP_ID, target, ChatPermissions(can_send_messages=True, can_send_other_messages=True))
        elif cmd == "/warn":
            warns = await store.load("warns.json"); key = f"{GROUP_ID}:{target}"; warns[key] = int(warns.get(key, 0)) + 1; await store.save("warns.json", warns)
            if warns[key] >= 3: await context.bot.ban_chat_member(GROUP_ID, target)
            await update.effective_message.reply_text(f"⚠️ Advertencia {warns[key]}/3 registrada."); return
        await update.effective_message.reply_text(f"✅ {cmd[1:]} aplicado a <code>{target}</code>. Motivo: {esc(reason)}", parse_mode=ParseMode.HTML)
    except Exception as exc: await update.effective_message.reply_text(f"❌ Error de Telegram: {esc(exc)}")


async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.effective_message
    text = message.text or message.caption or ""
    links = URL_RE.findall(text)
    if not links or await is_admin(message.from_user.id): return False
    settings = await store.load("settings.json")
    if not settings.get("moderation", True): return False
    bad = [x for x in links if not link_allowed(x)]
    if not bad: return False
    try: await message.delete()
    except Exception: LOG.warning("No se pudo borrar enlace", exc_info=True)
    link_id = uid(); pending = await store.load("pending_links.json")
    pending[link_id] = {"link_id": link_id, "url": bad[0], "user_id": message.from_user.id, "username": message.from_user.username, "name": message.from_user.full_name, "chat_id": message.chat_id, "message_id": message.message_id, "timestamp": now()}
    await store.save("pending_links.json", pending)
    await context.bot.send_message(GROUP_ID, "⚠️ Tu enlace fue retirado y está en revisión por un administrador.")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Validar", callback_data=f"validar:{link_id}"), InlineKeyboardButton("🚫 Expulsar", callback_data=f"expulsar:{link_id}")]])
    info = f"🔎 <b>Enlace pendiente</b> #{link_id}\nURL: <code>{esc(bad[0])}</code>\nAutor: {esc(message.from_user.full_name)} @{esc(message.from_user.username)} (<code>{message.from_user.id}</code>)\nFecha: {now()}"
    for admin in admins:
        try: await context.bot.send_message(admin, info, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception: LOG.info("Admin %s aún no inició el bot", admin)
    return True


async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    pending = await store.load("pending_links.json")
    if not pending: await update.effective_message.reply_text("✅ No hay enlaces pendientes."); return
    for item in list(pending.values())[:20]:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Validar", callback_data=f"validar:{item['link_id']}"), InlineKeyboardButton("🚫 Expulsar", callback_data=f"expulsar:{item['link_id']}")]])
        await update.effective_message.reply_text(f"#{item['link_id']} <code>{esc(item['url'])}</code>\n{esc(item['name'])}", parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query; await call.answer()
    if not await is_admin(call.from_user.id): return
    action, link_id = call.data.split(":", 1); pending = await store.load("pending_links.json"); resolved = await store.load("resolved_links.json")
    if link_id in resolved or link_id not in pending: await call.edit_message_text("ℹ️ Este enlace ya fue resuelto."); return
    item = pending.pop(link_id); resolved[link_id] = {**item, "action": action, "admin_id": call.from_user.id, "resolved_at": now()}; await store.save("pending_links.json", pending); await store.save("resolved_links.json", resolved)
    try:
        if action == "validar": await context.bot.send_message(GROUP_ID, f"🔗 Enlace validado, enviado originalmente por <a href=\"tg://user?id={item['user_id']}\">{esc(item['name'])}</a>:\n{esc(item['url'])}", parse_mode=ParseMode.HTML); result = "✅ Validado"
        else: await context.bot.ban_chat_member(GROUP_ID, item["user_id"]); await context.bot.unban_chat_member(GROUP_ID, item["user_id"]); result = "🚫 Expulsado"
    except Exception as exc: result = f"❌ Error: {esc(exc)}"
    await call.edit_message_text(f"{result} por {mention(call.from_user)}", parse_mode=ParseMode.HTML)


async def translate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not group_message(update) or not message.text or message.text.startswith("/") or await is_admin(message.from_user.id) or await process_link(update, context): return
    if message.message_id in translation_locks: return
    translation_locks.add(message.message_id)
    try:
        translated = await asyncio.to_thread(GoogleTranslator(source="auto", target="es").translate, message.text)
        if translated and translated.casefold() != message.text.casefold(): await message.reply_text(f"🌐 <b>Traducción al español</b>\n{esc(translated)}", parse_mode=ParseMode.HTML)
    except Exception as exc: LOG.warning("Traducción no disponible: %s", exc)
    finally: translation_locks.discard(message.message_id)


async def media_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not group_message(update) or await is_admin(message.from_user.id): return
    settings = await store.load("settings.json")
    if settings.get("moderation", True) and message.content_type in {"photo", "video", "document", "audio", "animation", "sticker", "voice"}:
        try: await message.delete(); await context.bot.send_message(GROUP_ID, "⚠️ Las fotos, vídeos y archivos requieren autorización de un administrador.")
        except Exception: LOG.warning("No se pudo moderar multimedia", exc_info=True)


async def devblog_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        feed = await asyncio.to_thread(feedparser.parse, "https://rust.facepunch.com/rss/news")
        entry = feed.entries[0]; await update.effective_message.reply_text(f"📰 <b>{esc(entry.title)}</b>\n{esc(entry.link)}", parse_mode=ParseMode.HTML, disable_web_page_preview=False)
    except Exception as exc: await update.effective_message.reply_text(f"❌ No se pudo consultar el RSS: {esc(exc)}")


def next_wipe() -> datetime:
    current = datetime.now(timezone.utc)
    manual = None
    # Manual date is read by wipe_cmd; default is next first Thursday at 19:00 UTC.
    candidate = current.replace(hour=19, minute=0, second=0, microsecond=0)
    while candidate <= current or candidate.weekday() != 3 or candidate.day > 7: candidate += timedelta(days=1)
    return candidate


async def wipe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = await store.load("wipe_config.json"); target = None
    if config.get("manual"):
        try: target = datetime.fromisoformat(config["manual"])
        except ValueError: pass
    target = target or next_wipe(); remaining = target - datetime.now(timezone.utc)
    if context.args and context.args[0].lower() == "recordatorio":
        if update.effective_user.id not in config.setdefault("reminders", []): config["reminders"].append(update.effective_user.id); await store.save("wipe_config.json", config)
        await update.effective_message.reply_text("✅ Te avisaré una hora antes del wipe en este chat privado."); return
    total = max(0, int(remaining.total_seconds())); days, rem = divmod(total, 86400); hours, rem = divmod(rem, 3600); minutes = rem // 60
    await update.effective_message.reply_text(f"🧨 <b>Próximo wipe de Rust</b>\n📅 {target.strftime('%d/%m/%Y')}\n⏰ 19:00 UTC\n⏳ Faltan: {days} días, {hours} horas, {minutes} minutos", parse_mode=ParseMode.HTML)


async def setwipe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    try: target = datetime.strptime(" ".join(context.args), "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc); config = await store.load("wipe_config.json"); config["manual"] = target.isoformat(); await store.save("wipe_config.json", config); await update.effective_message.reply_text("✅ Wipe manual guardado en UTC.")
    except ValueError: await update.effective_message.reply_text("Usa /setwipe DD/MM/YYYY HH:MM")


async def automation_tick(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tareas idempotentes: se ejecuta cada minuto y tolera reinicios."""
    try:
        polls = await store.load("encuestas.json")
        changed = False
        for poll in polls.values():
            if poll.get("closed") or not poll.get("expires_at"):
                continue
            if datetime.fromisoformat(poll["expires_at"]) <= datetime.now(timezone.utc):
                poll["closed"] = True; changed = True
                counts = [sum(1 for vote in poll.get("votes", {}).values() if vote == i) for i in range(len(poll["options"]))]
                text = "📊 <b>Encuesta cerrada: " + esc(poll["title"]) + "</b>\n\n" + "\n".join(f"{i + 1}. {esc(x)} — {counts[i]} votos" for i, x in enumerate(poll["options"]))
                try: await context.bot.edit_message_text(GROUP_ID, poll["message_id"], text, parse_mode=ParseMode.HTML)
                except Exception: LOG.warning("No se pudo cerrar encuesta %s", poll.get("id"))
        if changed: await store.save("encuestas.json", polls)

        config = await store.load("wipe_config.json"); target = None
        if config.get("manual"):
            try: target = datetime.fromisoformat(config["manual"])
            except ValueError: target = None
        target = target or next_wipe(); reminder_key = target.isoformat()
        if target - timedelta(hours=1) <= datetime.now(timezone.utc) < target and config.get("last_reminder") != reminder_key:
            for user_id in config.get("reminders", []):
                try: await context.bot.send_message(user_id, f"⏰ Recordatorio: el wipe de Rust es en menos de una hora ({target.strftime('%d/%m/%Y %H:%M')} UTC).")
                except Exception: pass
            config["last_reminder"] = reminder_key; await store.save("wipe_config.json", config)

        tickets = await store.load("tickets.json"); cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        for ticket in tickets.values():
            if ticket.get("status") == "abierto" and datetime.fromisoformat(ticket["timestamp"]) < cutoff and ticket.get("timeout_notified") is not True:
                ticket["timeout_notified"] = True
                for admin in admins:
                    try: await context.bot.send_message(admin, f"⏰ El ticket #{ticket['ticket_id']} lleva más de 24 horas abierto.")
                    except Exception: pass
        await store.save("tickets.json", tickets)
    except Exception:
        LOG.exception("automation_tick")


async def soporte_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if group_message(update):
        try: await update.effective_message.delete()
        except Exception: pass
        await context.bot.send_message(GROUP_ID, "Usa /soporte en mi chat privado para abrir un ticket."); return
    if not context.args: admin_states[update.effective_user.id] = {"flow": "ticket"}; await update.effective_message.reply_text("Escribe el problema que quieres enviar al equipo."); return
    await create_ticket(update, " ".join(context.args), context)


async def create_ticket(update: Update, text: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    tickets = await store.load("tickets.json"); ticket_id = uid().upper(); user = update.effective_user
    tickets[ticket_id] = {"ticket_id": ticket_id, "user_id": user.id, "username": user.username, "name": user.full_name, "message": text, "timestamp": now(), "status": "abierto", "admin_id": None}; await store.save("tickets.json", tickets)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Atender", callback_data=f"atender:{ticket_id}"), InlineKeyboardButton("❌ Cerrar", callback_data=f"cerrar:{ticket_id}")]])
    msg = f"🎫 <b>Ticket #{ticket_id}</b>\nUsuario: {esc(user.full_name)} @{esc(user.username)} (<code>{user.id}</code>)\n\n{esc(text)}"
    for admin in admins:
        try: await context.bot.send_message(admin, msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception: pass
    await update.effective_message.reply_text(f"✅ Ticket #{ticket_id} creado. El equipo te responderá por este chat.")


async def tickets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    tickets = await store.load("tickets.json"); active = [x for x in tickets.values() if x["status"] != "cerrado"]
    await update.effective_message.reply_text("\n".join(f"#{x['ticket_id']} — {esc(x['name'])} — {x['status']}" for x in active) or "No hay tickets activos.", parse_mode=ParseMode.HTML)


async def ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query; await call.answer()
    if not await is_admin(call.from_user.id): return
    action, ticket_id = call.data.split(":", 1); tickets = await store.load("tickets.json"); ticket = tickets.get(ticket_id)
    if not ticket: await call.edit_message_text("Ticket no encontrado."); return
    if action == "atender":
        if ticket["status"] != "abierto": await call.edit_message_text(f"Ticket ya atendido por {ticket.get('admin_id')}"); return
        ticket["status"] = "en_proceso"; ticket["admin_id"] = call.from_user.id; await store.save("tickets.json", tickets); admin_states[call.from_user.id] = {"flow": "ticket_reply", "ticket_id": ticket_id}; await call.edit_message_text(f"✅ Has tomado #{ticket_id}. Envía ahora tu respuesta. /cerrar_ticket para finalizar.")
    else:
        ticket["status"] = "cerrado"; tickets[ticket_id] = ticket; await store.save("tickets.json", tickets); await call.edit_message_text("❌ Ticket cerrado sin respuesta."); await context.bot.send_message(ticket["user_id"], "Tu ticket ha sido cerrado. Si necesitas más ayuda, usa /soporte de nuevo.")


async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query; await call.answer()
    if not call.data.startswith("verify:"): return
    target_id = int(call.data.split(":", 1)[1])
    if call.from_user.id != target_id: await call.answer("Este botón no es para tu cuenta.", show_alert=True); return
    verified = await store.load("verified.json"); verified[str(target_id)] = {"chat_id": GROUP_ID, "timestamp": now()}; await store.save("verified.json", verified)
    try:
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(GROUP_ID, target_id, ChatPermissions(can_send_messages=True, can_send_other_messages=True, can_send_polls=True, can_add_web_page_previews=True))
    except Exception: LOG.warning("No se pudo liberar al usuario verificado", exc_info=True)
    await call.edit_message_text("✅ Verificación completada. Ya puedes participar en GAMAER CITY.")


async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query; await call.answer()
    if not await is_admin(call.from_user.id): return
    section = call.data.split(":", 1)[1]
    if section == "rules": text = await store.load("rules.txt")
    elif section == "server":
        server = await store.load("server.json"); text = f"🎮 {esc(server.get('name', GROUP_NAME))}\nIP: <code>{esc(server.get('ip', 'no configurada'))}</code>"
    elif section == "links": text = "Usa /pendientes para revisar enlaces."
    elif section == "tickets": text = "Usa /tickets para ver tickets activos."
    else: text = f"Mantenimiento: {'activo' if (await store.load('settings.json')).get('maintenance') else 'inactivo'}"
    await call.edit_message_text(text, parse_mode=ParseMode.HTML)


async def welcome_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    config = await store.load("welcome.json"); sub = update.effective_message.text.split()[0].split("@")[0]
    if sub == "/bienvenida":
        config["enabled"] = bool(context.args and context.args[0].lower() == "on"); await store.save("welcome.json", config); await update.effective_message.reply_text(f"✅ Bienvenida {'activada' if config['enabled'] else 'desactivada'}.")
    else:
        text = update.effective_message.text.partition(" ")[2].strip(); config["text"] = esc(text); await store.save("welcome.json", config); await update.effective_message.reply_text("✅ Mensaje de bienvenida guardado.")


async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = await store.load("welcome.json")
    if not config.get("enabled") or not update.chat_member: return
    member = update.chat_member.new_chat_member.user
    if update.chat_member.new_chat_member.status not in {ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED}: return
    verified = await store.load("verified.json")
    if str(member.id) not in verified:
        try:
            from telegram import ChatPermissions
            await context.bot.restrict_chat_member(GROUP_ID, member.id, ChatPermissions(can_send_messages=False, can_send_other_messages=False))
        except Exception: LOG.warning("No se pudo restringir a nuevo miembro", exc_info=True)
    text = ("📜 <b>Reglas de GAMAER CITY</b>\n\n" + await store.load("rules.txt") + "\n\nPulsa el botón para confirmar que las has leído y verificarte.")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ He leído las reglas y me verifico", callback_data=f"verify:{member.id}")]])
    await context.bot.send_message(update.effective_chat.id, text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_states.pop(update.effective_user.id, None); await update.effective_message.reply_text("✅ Flujo cancelado.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOG.error("Error procesando actualización", exc_info=context.error)
    for admin in admins:
        try: await context.bot.send_message(admin, "⚠️ El bot registró un error y seguirá funcionando.")
        except Exception: pass


async def official_links_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    links = await store.load("official_links.json")
    text = "🔗 <b>Enlaces oficiales de GAMAER CITY</b>\n" + "\n".join(f"• {esc(key.title())}: {esc(value)}" for key, value in links.items() if value)
    await update.effective_message.reply_text(text if any(links.values()) else "ℹ️ Todavía no hay enlaces oficiales configurados.", parse_mode=ParseMode.HTML)


async def set_links_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Usa /setenlaces discord|web|channel|donaciones URL")
        return
    key, value = context.args[0].lower(), " ".join(context.args[1:])
    if key not in {"discord", "web", "channel", "donaciones"}:
        await update.effective_message.reply_text("Categoría inválida."); return
    links = await store.load("official_links.json"); links[key] = value; await store.save("official_links.json", links); await update.effective_message.reply_text("✅ Enlace oficial actualizado.")


async def pin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not group_message(update) or not await is_admin(update.effective_user.id): return
    if not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("Responde a un mensaje con /fijar para fijarlo como mensaje oficial."); return
    try:
        target = update.effective_message.reply_to_message.message_id
        await context.bot.pin_chat_message(GROUP_ID, target, disable_notification=True)
        settings = await store.load("settings.json"); settings["pinned_message_id"] = target; await store.save("settings.json", settings)
        await audit("pin", update.effective_user.id, details=str(target)); await update.effective_message.reply_text("✅ Mensaje oficial fijado.")
    except Exception as exc: await update.effective_message.reply_text(f"❌ No se pudo fijar: {esc(exc)}")


async def maintenance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    settings = await store.load("settings.json")
    if not context.args or context.args[0].lower() not in {"on", "off"}:
        await update.effective_message.reply_text(f"Mantenimiento: {'activo' if settings.get('maintenance') else 'inactivo'}"); return
    settings["maintenance"] = context.args[0].lower() == "on"; await store.save("settings.json", settings); await audit("maintenance", update.effective_user.id, details=str(settings["maintenance"]))
    await update.effective_message.reply_text("✅ Modo mantenimiento actualizado.")


async def panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔎 Enlaces", callback_data="panel:links"), InlineKeyboardButton("🎫 Tickets", callback_data="panel:tickets")], [InlineKeyboardButton("📜 Reglas", callback_data="panel:rules"), InlineKeyboardButton("🌐 Servidor", callback_data="panel:server")], [InlineKeyboardButton("🛠️ Mantenimiento", callback_data="panel:maintenance")]])
    await update.effective_message.reply_text("🛠️ <b>Panel de GAMAER CITY</b>\nSelecciona una sección:", parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def appeal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text("Usa /apelar en el chat privado del bot."); return
    text = " ".join(context.args).strip()
    if not text:
        admin_states[update.effective_user.id] = {"flow": "appeal"}; await update.effective_message.reply_text("Explica por qué consideras injusta la sanción."); return
    appeals = await store.load("appeals.json"); appeal_id = uid().upper(); appeals[appeal_id] = {"id": appeal_id, "user_id": update.effective_user.id, "text": text, "status": "open", "timestamp": now()}; await store.save("appeals.json", appeals)
    for admin in admins:
        try: await context.bot.send_message(admin, f"⚖️ <b>Apelación #{appeal_id}</b>\nUsuario: {mention(update.effective_user)}\n\n{esc(text)}", parse_mode=ParseMode.HTML)
        except Exception: pass
    await update.effective_message.reply_text("✅ Apelación enviada al equipo.")


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text("Usa /reportar en privado y proporciona el ID del usuario y el motivo."); return
    if len(context.args) < 2 or not context.args[0].lstrip("-").isdigit():
        await update.effective_message.reply_text("Usa /reportar USER_ID motivo"); return
    reports = await store.load("reports.json"); report_id = uid().upper(); reports[report_id] = {"id": report_id, "reporter_id": update.effective_user.id, "target_id": int(context.args[0]), "text": " ".join(context.args[1:]), "status": "open", "timestamp": now()}; await store.save("reports.json", reports)
    await audit("report", update.effective_user.id, int(context.args[0]), reports[report_id]["text"])
    for admin in admins:
        try: await context.bot.send_message(admin, f"🚨 <b>Reporte #{report_id}</b>\nReportado: <code>{context.args[0]}</code>\nMotivo: {esc(reports[report_id]['text'])}", parse_mode=ParseMode.HTML)
        except Exception: pass
    await update.effective_message.reply_text("✅ Reporte enviado a los administradores.")


async def roles_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    if len(context.args) < 2 or not context.args[0].lstrip("-").isdigit() or context.args[1] not in {"admin", "moderator", "support", "announcer", "user"}:
        await update.effective_message.reply_text("Usa /rol USER_ID admin|moderator|support|announcer|user"); return
    roles = await store.load("roles.json"); roles[context.args[0]] = context.args[1]; await store.save("roles.json", roles); await update.effective_message.reply_text("✅ Rol actualizado.")


async def events_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    events = await store.load("events.json")
    if context.args and await private_admin(update):
        if context.args[0].lower() == "crear":
            text = " ".join(context.args[1:]).strip()
            if not text: await update.effective_message.reply_text("Usa /evento crear Título | fecha | detalles"); return
            event_id = uid().upper(); events[event_id] = {"id": event_id, "text": text, "created_at": now(), "status": "active"}; await store.save("events.json", events); await context.bot.send_message(GROUP_ID, f"📅 <b>Evento #{event_id}</b>\n\n{esc(text)}", parse_mode=ParseMode.HTML); await update.effective_message.reply_text("✅ Evento publicado."); return
        if context.args[0].lower() == "cancelar" and len(context.args) > 1:
            if context.args[1] in events: events[context.args[1]]["status"] = "cancelled"; await store.save("events.json", events)
            await update.effective_message.reply_text("✅ Evento cancelado."); return
    active = [event for event in events.values() if event.get("status") == "active"]
    await update.effective_message.reply_text("📅 Eventos activos:\n" + "\n".join(f"#{e['id']} — {esc(e['text'])}" for e in active) if active else "No hay eventos activos.", parse_mode=ParseMode.HTML)


async def giveaway_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    giveaways = await store.load("giveaways.json")
    if await private_admin(update) and context.args and context.args[0].lower() == "crear":
        prize = " ".join(context.args[1:]).strip()
        if not prize: await update.effective_message.reply_text("Usa /sorteo crear Premio"); return
        giveaway_id = uid().upper(); giveaways[giveaway_id] = {"id": giveaway_id, "prize": prize, "participants": [], "status": "active", "created_at": now()}; await store.save("giveaways.json", giveaways)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🎟️ Participar", callback_data=f"giveaway:{giveaway_id}")]])
        await context.bot.send_message(GROUP_ID, f"🎁 <b>Sorteo #{giveaway_id}</b>\nPremio: {esc(prize)}\nPulsa el botón para participar.", parse_mode=ParseMode.HTML, reply_markup=keyboard); await update.effective_message.reply_text("✅ Sorteo publicado."); return
    active = [g for g in giveaways.values() if g.get("status") == "active"]
    await update.effective_message.reply_text("🎁 Sorteos activos:\n" + "\n".join(f"#{g['id']} — {esc(g['prize'])} ({len(g['participants'])} participantes)" for g in active) if active else "No hay sorteos activos.", parse_mode=ParseMode.HTML)


async def giveaway_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query; await call.answer(); giveaway_id = call.data.split(":", 1)[1]; giveaways = await store.load("giveaways.json"); giveaway = giveaways.get(giveaway_id)
    if not giveaway or giveaway.get("status") != "active": await call.answer("Sorteo cerrado", show_alert=True); return
    user_id = call.from_user.id
    if user_id in giveaway["participants"]: await call.answer("Ya estás participando", show_alert=True); return
    giveaway["participants"].append(user_id); giveaways[giveaway_id] = giveaway; await store.save("giveaways.json", giveaways); await call.answer("Participación registrada")


async def responder_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    if not recent_messages:
        await update.effective_message.reply_text("No hay mensajes recientes en caché."); return
    lines = []
    for index, message in enumerate(recent_messages, 1):
        kind = message.content_type or "mensaje"
        summary = (message.text or message.caption or "").replace("\n", " ")[:60]
        lines.append(f"{index}. {esc(message.from_user.full_name)} · {kind} · {esc(summary)}")
    admin_states[update.effective_user.id] = {"flow": "respond_number"}
    await update.effective_message.reply_text("Selecciona el número del mensaje:\n" + "\n".join(lines))


async def encuesta_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    raw = update.effective_message.text.partition(" ")[2].strip()
    parts = [part.strip() for part in raw.split("|") if part.strip()]
    if len(parts) < 3 or len(parts) > 11:
        await update.effective_message.reply_text("Usa /encuesta Título | Opción 1 | Opción 2 (máximo 10 opciones)."); return
    duration = None
    if parts[-1].lower().startswith("duracion="):
        raw_duration = parts.pop().split("=", 1)[1].lower(); match = re.fullmatch(r"(\d+)(m|h|d)", raw_duration)
        if match: duration = timedelta(**{"minutes": int(match[1])} if match[2] == "m" else {"hours": int(match[1])} if match[2] == "h" else {"days": int(match[1])})
    if len(parts) < 3: await update.effective_message.reply_text("Debes indicar al menos dos opciones."); return
    polls = await store.load("encuestas.json"); poll_id = uid(); poll = {"id": poll_id, "title": parts[0], "options": parts[1:], "votes": {}, "closed": False, "created_at": now(), "expires_at": (datetime.now(timezone.utc) + duration).isoformat() if duration else None}
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(option, callback_data=f"voto:{poll_id}:{index}")] for index, option in enumerate(poll["options"])])
    message = await context.bot.send_message(GROUP_ID, "📊 <b>Encuesta: " + esc(poll["title"]) + "</b>\n\n" + "\n".join(f"{i + 1}. {esc(x)} — 0 votos" for i, x in enumerate(poll["options"])), parse_mode=ParseMode.HTML, reply_markup=keyboard)
    poll["message_id"] = message.message_id; polls[poll_id] = poll; await store.save("encuestas.json", polls); await update.effective_message.reply_text(f"✅ Encuesta publicada: #{poll_id}")


async def poll_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query; await call.answer(); _, poll_id, option = call.data.split(":", 2); polls = await store.load("encuestas.json"); poll = polls.get(poll_id)
    if not poll or poll.get("closed"): await call.answer("Encuesta cerrada", show_alert=True); return
    voter = str(call.from_user.id)
    if voter in poll["votes"]: await call.answer("Ya has votado", show_alert=True); return
    poll["votes"][voter] = int(option); polls[poll_id] = poll; await store.save("encuestas.json", polls)
    counts = [sum(1 for vote in poll["votes"].values() if vote == i) for i in range(len(poll["options"]))]
    text = "📊 <b>Encuesta: " + esc(poll["title"]) + "</b>\n\n" + "\n".join(f"{i + 1}. {esc(x)} — {counts[i]} votos" for i, x in enumerate(poll["options"]))
    await call.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=call.message.reply_markup)


async def encuestas_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    polls = await store.load("encuestas.json"); active = [p for p in polls.values() if not p.get("closed")]
    await update.effective_message.reply_text("\n".join(f"#{p['id']} — {p['title']} ({len(p['votes'])} votos)" for p in active) or "No hay encuestas activas.")


async def cerrar_encuesta_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    if not context.args: await update.effective_message.reply_text("Usa /cerrar_encuesta ID"); return
    polls = await store.load("encuestas.json"); poll = polls.get(context.args[0])
    if not poll: await update.effective_message.reply_text("Encuesta no encontrada."); return
    poll["closed"] = True; polls[context.args[0]] = poll; await store.save("encuestas.json", polls); await update.effective_message.reply_text("✅ Encuesta cerrada.")


async def interactive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = admin_states.get(update.effective_user.id)
    if state and state.get("flow") == "respond_number":
        try: index = int(update.effective_message.text) - 1; target = list(recent_messages)[index]
        except (ValueError, IndexError): await update.effective_message.reply_text("Escribe un número válido o /cancelar."); return
        admin_states[update.effective_user.id] = {"flow": "respond_text", "target": target}
        await update.effective_message.reply_text("Escribe el texto de respuesta. /cancelar para salir."); return
    if state and state.get("flow") == "respond_text":
        target = state["target"]; admin_states.pop(update.effective_user.id, None)
        await context.bot.send_message(GROUP_ID, f"🛠️ <b>Respuesta de administración</b> para {mention(target.from_user)}\n\n{esc(update.effective_message.text)}", parse_mode=ParseMode.HTML, reply_to_message_id=target.message_id); await update.effective_message.reply_text("✅ Respuesta enviada."); return
    if state and state.get("flow") == "ticket": admin_states.pop(update.effective_user.id, None); await create_ticket(update, update.effective_message.text, context); return
    if state and state.get("flow") == "ticket_reply":
        ticket_id = state["ticket_id"]; tickets = await store.load("tickets.json"); ticket = tickets.get(ticket_id)
        if ticket and ticket.get("admin_id") == update.effective_user.id: await context.bot.send_message(ticket["user_id"], f"🛠️ <b>Respuesta del equipo</b>\n\n{esc(update.effective_message.text)}", parse_mode=ParseMode.HTML); await update.effective_message.reply_text("✅ Respuesta enviada.")
        return
    if not group_message(update): return
    if (await store.load("settings.json")).get("maintenance") and not await is_admin(update.effective_user.id):
        try: await update.effective_message.delete()
        except Exception: pass
        return
    recent_messages.append(update.effective_message)
    if await moderate_words(update, context): return
    if await automatic_reply(update, context): return
    await translate_message(update, context)


async def media_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not group_message(update): return
    if (await store.load("settings.json")).get("maintenance") and not await is_admin(update.effective_user.id):
        try: await update.effective_message.delete()
        except Exception: pass
        return
    recent_messages.append(update.effective_message)
    if await moderate_words(update, context): return
    await media_moderation(update, context)


async def post_init(application: Application) -> None:
    await refresh_admins(); application.job_queue.run_repeating(automation_tick, interval=60, first=10, name="rust133-automation"); LOG.info("Bot iniciado con admins %s y grupo %s", sorted(admins), GROUP_ID)


def build_app() -> Application:
    if not valid_token() or not GROUP_ID or not admins: raise RuntimeError("Configura TELEGRAM_TOKEN, GROUP_ID y ADMIN_IDS")
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler(["start"], start_cmd)); app.add_handler(CommandHandler(["help", "ayuda"], help_cmd)); app.add_handler(CommandHandler("reglas", rules_cmd)); app.add_handler(CommandHandler("devblog", devblog_cmd)); app.add_handler(CommandHandler("servidor", server_cmd)); app.add_handler(CommandHandler("enlaces", official_links_cmd)); app.add_handler(CommandHandler(["wipe", "wipes"], wipe_cmd)); app.add_handler(CommandHandler("soporte", soporte_cmd)); app.add_handler(CommandHandler("apelar", appeal_cmd)); app.add_handler(CommandHandler("reportar", report_cmd)); app.add_handler(CommandHandler("cancelar", cancel_cmd))
    app.add_handler(CommandHandler(["addadmin", "deladmin", "listadmins"], admins_cmd)); app.add_handler(CommandHandler("anuncio", announcement_cmd)); app.add_handler(CommandHandler("moderacion", moderation_cmd)); app.add_handler(CommandHandler("mantenimiento", maintenance_cmd)); app.add_handler(CommandHandler("panel", panel_cmd)); app.add_handler(CommandHandler("fijar", pin_cmd)); app.add_handler(CommandHandler("rol", roles_cmd)); app.add_handler(CommandHandler(["evento", "eventos"], events_cmd)); app.add_handler(CommandHandler(["sorteo", "sorteos"], giveaway_cmd)); app.add_handler(CommandHandler("setenlaces", set_links_cmd)); app.add_handler(CommandHandler("setservidor", setserver_cmd)); app.add_handler(CommandHandler("filtro", filter_cmd)); app.add_handler(CommandHandler("auto", auto_reply_cmd)); app.add_handler(CommandHandler(["ban", "kick", "mute", "unmute", "warn"], moderate_user)); app.add_handler(CommandHandler("pendientes", pending_cmd)); app.add_handler(CommandHandler("setreglas", setrules_cmd)); app.add_handler(CommandHandler("setwipe", setwipe_cmd)); app.add_handler(CommandHandler("tickets", tickets_cmd)); app.add_handler(CommandHandler("responder", responder_cmd)); app.add_handler(CommandHandler("encuesta", encuesta_cmd)); app.add_handler(CommandHandler("encuestas", encuestas_cmd)); app.add_handler(CommandHandler("cerrar_encuesta", cerrar_encuesta_cmd)); app.add_handler(CommandHandler(["bienvenida", "setbienvenida"], welcome_cmd))
    app.add_handler(CallbackQueryHandler(link_callback, pattern=r"^(validar|expulsar):")); app.add_handler(CallbackQueryHandler(ticket_callback, pattern=r"^(atender|cerrar):")); app.add_handler(CallbackQueryHandler(poll_callback, pattern=r"^voto:")); app.add_handler(CallbackQueryHandler(verify_callback, pattern=r"^verify:")); app.add_handler(CallbackQueryHandler(panel_callback, pattern=r"^panel:")); app.add_handler(CallbackQueryHandler(giveaway_callback, pattern=r"^giveaway:")); app.add_handler(ChatMemberHandler(new_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.Chat(GROUP_ID) & filters.TEXT & ~filters.COMMAND, interactive_text)); app.add_handler(MessageHandler(filters.Chat(GROUP_ID) & ~filters.TEXT & ~filters.COMMAND, media_router)); app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, interactive_text))
    app.add_error_handler(error_handler)
    return app


if __name__ == "__main__":
    if not valid_token(): raise SystemExit("TELEGRAM_TOKEN no configurado o inválido")
    build_app().run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
