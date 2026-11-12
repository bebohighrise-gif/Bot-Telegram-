#!/usr/bin/env python3
"""Rust 133 Dev Blog community bot.

Async python-telegram-bot v20+, JSON persistence protected by asyncio.Lock.
"""
from __future__ import annotations

import asyncio
import copy
import functools
import html
import json
import logging
import os
import re
import secrets
import shutil
import time
import urllib.parse
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser
import aiohttp
from dotenv import load_dotenv
from telegram import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats, BotCommandScopeChat, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, MenuButtonCommands, ReplyKeyboardMarkup, Update
from telegram import ChatPermissions
from telegram.constants import ChatMemberStatus, MessageEntityType, ParseMode, UpdateType
from telegram.error import BadRequest, NetworkError, TelegramError, TimedOut
from telegram.helpers import mention_html
from telegram.ext import (
    Application, CallbackQueryHandler, ChatMemberHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_FILE)


def require_env() -> None:
    """Detiene el arranque si faltan variables. El archivo .env es opcional si las variables ya están en el entorno."""
    missing = [name for name in ("TELEGRAM_TOKEN", "GROUP_ID") if not os.getenv(name, "").strip()]
    if missing:
        hint = "" if ENV_FILE.is_file() else f" (no existe {ENV_FILE}; copia .env.example como .env o define las variables en el entorno)"
        raise RuntimeError("Faltan variables obligatorias: " + ", ".join(missing) + hint)


def _int_env(name: str, default: int = 0) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"{name} debe ser un número entero, no {raw!r}") from None


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    return default if not raw else raw in {"1", "true", "yes", "on", "si", "sí"}


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx registra la URL completa de cada petición, que contiene el token del bot: nunca por debajo de WARNING.
for _noisy in ("httpx", "httpcore", "telegram.request"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
LOG = logging.getLogger("rust133")
TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
GROUP_ID = _int_env("GROUP_ID")
GROUP_NAME = os.getenv("GROUP_NAME", "GAMAER CITY").strip() or "GAMAER CITY"
BOT_OWNER_ID = _int_env("BOT_OWNER_ID")
SEED_ADMINS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().lstrip("-").isdigit()}
TRANSLATE_ENABLED = _bool_env("TRANSLATE_ENABLED", True)
MEDIA_MODERATION = _bool_env("MEDIA_MODERATION", True)
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATE_TTL = 15 * 60          # segundos que vive un flujo interactivo
CONFIRM_TTL = 10 * 60        # segundos que vive una confirmación de ban/kick
ANON_ADMIN_ID = 1087968824   # GroupAnonymousBot: administradores que escriben de forma anónima
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
            "tickets_cerrados.json": {}, "welcome.json": {"enabled": True, "text": "👋 Bienvenido {nombre} a {grupo}!", "file_id": None},
            "wipe_config.json": {"manual": None, "reminders": []}, "encuestas.json": {},
            "server.json": {"name": "GAMAER CITY", "ip": ""},
            "roles.json": {}, "verified.json": {}, "moderation_logs.json": [],
            "appeals.json": {}, "reports.json": {}, "events.json": {}, "giveaways.json": {},
            "moderation_confirmations.json": {},
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
                value = copy.deepcopy(self.defaults.get(name, {}))
                await self._write_unlocked(name, value)
                return copy.deepcopy(value)
            try:
                if name.endswith(".txt"):
                    return path.read_text(encoding="utf-8")
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                # Nunca se descarta un archivo ilegible en silencio: se conserva una copia antes de que
                # el siguiente guardado lo sobrescriba con los valores por defecto.
                LOG.error("No se pudo leer %s: %s", name, exc)
                backup = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
                try:
                    shutil.copy2(path, backup)
                    LOG.error("Copia del archivo dañado guardada en %s", backup)
                except OSError:
                    LOG.error("No se pudo respaldar %s", name)
                return copy.deepcopy(self.defaults.get(name, {}))

    async def save(self, name: str, value: Any) -> None:
        async with self.lock:
            await self._write_unlocked(name, value)

    async def _write_unlocked(self, name: str, value: Any) -> None:
        path = self.path(name)
        temp = path.with_name(path.name + ".tmp")
        payload = str(value) if name.endswith(".txt") else json.dumps(value, ensure_ascii=False, indent=2)
        with open(temp, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temp, 0o600)  # contiene datos de usuarios
        except OSError:
            pass
        temp.replace(path)


store = JsonStore(DATA_DIR)
admins: set[int] = set(SEED_ADMINS)
recent_messages: deque[Any] = deque(maxlen=15)


class FlowStates(dict):
    """Flujos interactivos por usuario. Caducan solos tras STATE_TTL segundos."""

    def __setitem__(self, key: int, value: dict[str, Any]) -> None:
        super().__setitem__(key, {**value, "at": time.monotonic()})

    def get(self, key: int, default: Any = None) -> Any:
        value = super().get(key)
        if value is None:
            return default
        if time.monotonic() - value["at"] > STATE_TTL:
            self.pop(key, None)
            return default
        return value


admin_states: FlowStates = FlowStates()
STATE_LOCK = asyncio.Lock()
PERMISSIONS: dict[str, set[str]] = {
    "owner": {"all"},
    "admin": {"moderate", "support", "announce", "configure"},
    "moderator": {"moderate"},
    "support": {"support"},
    "announcer": {"announce"},
}
_group_admin_cache: dict[int, tuple[float, bool]] = {}
_permissions_cache: dict[str, Any] = {"at": 0.0, "value": None}
_rate_marks: dict[tuple[int, str], float] = {}
_last_error_notice = float("-inf")
translation_locks: set[int] = set()
last_flow_messages: dict[int, int] = {}


def valid_token() -> bool:
    return bool(re.fullmatch(r"\d{6,12}:[A-Za-z0-9_-]{20,}", TOKEN))


def owner_ids() -> set[int]:
    """Propietarios del bot: BOT_OWNER_ID, o ADMIN_IDS si no se definió propietario."""
    return {BOT_OWNER_ID} if BOT_OWNER_ID else set(SEED_ADMINS)


def is_owner(user_id: int | None) -> bool:
    return bool(user_id) and user_id in owner_ids()


async def is_admin(user_id: int | None) -> bool:
    """True para cualquier miembro del equipo (cualquier rol distinto de 'user')."""
    return bool(user_id and (is_owner(user_id) or user_id in admins))


async def refresh_admins() -> None:
    global admins
    stored = await store.load("admins.json")
    admins = set(SEED_ADMINS) | {int(x) for x in stored if str(x).lstrip("-").isdigit()}
    await store.save("admins.json", sorted(admins))


async def audit(action: str, actor_id: int | None = None, target_id: int | None = None, details: str = "") -> None:
    logs = await store.load("moderation_logs.json")
    logs.append({"action": action, "actor_id": actor_id, "target_id": target_id, "details": details[:1000], "timestamp": now()})
    await store.save("moderation_logs.json", logs[-5000:])


async def refresh_pinned_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = await store.load("settings.json")
    message_id = settings.get("pinned_message_id")
    if not message_id: return
    server = await store.load("server.json")
    text = f"📌 <b>{esc(GROUP_NAME)}</b>\n\n📜 Usa /reglas para las normas.\n🎮 IP: <code>{esc(server.get('ip', 'No configurada'))}</code>\n📰 /devblog · 🧨 /wipe · 🔗 /enlaces"
    try:
        await context.bot.edit_message_text(text, chat_id=GROUP_ID, message_id=message_id, parse_mode=ParseMode.HTML)
    except TelegramError:
        LOG.info("El mensaje fijado no se puede editar como texto")


async def role_of(user_id: int | None) -> str:
    if not user_id:
        return "user"
    if is_owner(user_id):
        return "owner"
    role = (await store.load("roles.json")).get(str(user_id))
    if role == "user" or role in PERMISSIONS:
        return role
    return "admin" if user_id in admins else "user"


async def has_permission(user_id: int | None, permission: str) -> bool:
    granted = PERMISSIONS.get(await role_of(user_id), set())
    return "all" in granted or permission in granted


async def staff_with(permission: str) -> list[int]:
    """IDs del equipo que tienen un permiso (para avisos privados)."""
    candidates = set(admins) | owner_ids()
    return [user_id for user_id in sorted(candidates) if await has_permission(user_id, permission)]


async def set_role(user_id: int, role: str, actor_id: int | None) -> bool:
    """Asigna un rol y mantiene sincronizado el conjunto de equipo. Devuelve False si no se permite."""
    if is_owner(user_id) or (role == "user" and user_id in SEED_ADMINS):
        return False
    roles = await store.load("roles.json")
    roles[str(user_id)] = role
    await store.save("roles.json", roles)
    if role == "user":
        admins.discard(user_id)
    else:
        admins.add(user_id)
    await store.save("admins.json", sorted(admins))
    await audit("role_assign", actor_id, user_id, role)
    return True


async def private_admin(update: Update, permission: str | None = None) -> bool:
    chat, user = update.effective_chat, update.effective_user
    if not chat or chat.type != "private":
        return False
    user_id = user.id if user else None
    if not await is_admin(user_id):
        await update.effective_message.reply_text("🔒 Esta función está reservada al equipo de GAMAER CITY. Puedes usar /help para ver las funciones públicas.")
        return False
    if permission and not await has_permission(user_id, permission):
        await update.effective_message.reply_text("🔒 Tu rol no tiene permiso para esta función.")
        return False
    return True


async def answer(call: Any, text: str | None = None, alert: bool = False) -> None:
    """Responde una sola vez al callback; Telegram rechaza la segunda respuesta."""
    try:
        await call.answer(text, show_alert=alert)
    except TelegramError:
        LOG.debug("No se pudo responder al callback", exc_info=True)


async def safe_edit(call: Any, text: str, **kwargs: Any) -> None:
    try:
        await call.edit_message_text(text, **kwargs)
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise


async def callback_guard(call: Any, permission: str | None = None) -> bool:
    user_id = call.from_user.id
    if not await is_admin(user_id) or (permission and not await has_permission(user_id, permission)):
        await answer(call, "🔒 No tienes permiso para esta acción.", True)
        return False
    await answer(call)
    return True


def rate_limited(user_id: int, key: str, seconds: float = 60.0) -> bool:
    current = time.monotonic()
    last = _rate_marks.get((user_id, key))
    if last is not None and current - last < seconds:
        return True
    _rate_marks[(user_id, key)] = current
    if len(_rate_marks) > 5000:
        for mark_key, mark in list(_rate_marks.items()):
            if current - mark > 3600:
                _rate_marks.pop(mark_key, None)
    return False


def guarded(handler: Any) -> Any:
    """Serializa handlers y tareas periódicas: evita lecturas-modificaciones-escrituras cruzadas sobre los JSON."""
    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        async with STATE_LOCK:
            await handler(update, context)
    return wrapper


def guarded_job(job: Any) -> Any:
    @functools.wraps(job)
    async def wrapper(context: ContextTypes.DEFAULT_TYPE) -> None:
        async with STATE_LOCK:
            await job(context)
    return wrapper


async def is_group_admin(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    cached = _group_admin_cache.get(user_id)
    if cached and time.monotonic() - cached[0] < 300:
        return cached[1]
    try:
        member = await context.bot.get_chat_member(GROUP_ID, user_id)
        result = member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}
    except TelegramError:
        result = False
    _group_admin_cache[user_id] = (time.monotonic(), result)
    return result


async def is_exempt(context: ContextTypes.DEFAULT_TYPE, message: Any) -> bool:
    """Equipo del bot, administradores del grupo (también anónimos) y otros bots no se moderan."""
    if message.sender_chat and message.sender_chat.id == GROUP_ID:
        return True
    user = message.from_user
    if not user or user.is_bot or user.id == ANON_ADMIN_ID:
        return True
    return await is_admin(user.id) or await is_group_admin(context, user.id)


async def default_permissions(context: ContextTypes.DEFAULT_TYPE) -> ChatPermissions:
    """Permisos por defecto del grupo, para devolver a un usuario a su estado normal."""
    if _permissions_cache["value"] and time.monotonic() - _permissions_cache["at"] < 300:
        return _permissions_cache["value"]
    try:
        chat = await context.bot.get_chat(GROUP_ID)
        if chat.permissions:
            _permissions_cache.update(at=time.monotonic(), value=chat.permissions)
            return chat.permissions
    except TelegramError:
        LOG.warning("No se pudieron leer los permisos del grupo", exc_info=True)
    return ChatPermissions(can_send_messages=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True)


def group_message(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id == GROUP_ID)


def public_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Reglas", callback_data="nav:rules"), InlineKeyboardButton("🎮 Servidor", callback_data="nav:server")],
        [InlineKeyboardButton("🧨 Wipe", callback_data="nav:wipe"), InlineKeyboardButton("🔗 Enlaces", callback_data="nav:links")],
        [InlineKeyboardButton("🎫 Soporte", callback_data="nav:support"), InlineKeyboardButton("📅 Eventos", callback_data="nav:events")],
        [InlineKeyboardButton("🎁 Sorteos", callback_data="nav:giveaways"), InlineKeyboardButton("❓ Ayuda", callback_data="nav:help")],
    ])


async def flow_prompt(update: Update, text: str, **kwargs: Any) -> None:
    message = await update.effective_message.reply_text(text, **kwargs)
    if update.effective_user and message:
        last_flow_messages[update.effective_user.id] = message.message_id


def link_host(url: str) -> str:
    """Host normalizado de una URL, o "" si es sospechosa (userinfo, barras invertidas, formato inválido)."""
    candidate = url if re.match(r"(?i)^[a-z][a-z0-9+.-]*://", url) else "http://" + url
    try:
        parts = urllib.parse.urlsplit(candidate)
        host = parts.hostname or ""
    except ValueError:
        return ""
    if "@" in parts.netloc or "\\" in candidate or parts.scheme.lower() not in {"http", "https"}:
        return ""
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def link_allowed(url: str) -> bool:
    host = link_host(url)
    return bool(host) and any(host == domain or host.endswith("." + domain) for domain in NO_LINKS)


def extract_links(message: Any) -> list[str]:
    """Enlaces visibles en el texto y también los ocultos tras texto (text_link) o detectados por Telegram."""
    text = message.text or message.caption or ""
    links = URL_RE.findall(text)
    parse = message.parse_entities if message.text else message.parse_caption_entities
    try:
        for entity, shown in parse([MessageEntityType.URL, MessageEntityType.TEXT_LINK]).items():
            links.append(entity.url if entity.type == MessageEntityType.TEXT_LINK and entity.url else shown)
    except (TypeError, ValueError):
        LOG.debug("No se pudieron leer las entidades del mensaje", exc_info=True)
    return list(dict.fromkeys(links))


def parse_user_id(raw: str) -> int | None:
    return int(raw) if raw.isdigit() and 0 < int(raw) < 2**53 else None


MEDIA_ATTRS = ("photo", "video", "document", "audio", "animation", "sticker", "voice", "video_note")


def message_kind(message: Any) -> str:
    for attr in MEDIA_ATTRS:
        if getattr(message, attr, None):
            return attr
    return "texto" if message.text else "mensaje"


async def notify_staff(context: ContextTypes.DEFAULT_TYPE, permission: str, text: str, **kwargs: Any) -> int:
    sent = 0
    for user_id in await staff_with(permission):
        try:
            await context.bot.send_message(user_id, text, **kwargs)
            sent += 1
        except TelegramError:
            LOG.info("El miembro del equipo %s aún no inició el bot", user_id)
    return sent


async def mute_user(context: ContextTypes.DEFAULT_TYPE, user_id: int, minutes: int | None) -> None:
    until = datetime.now(timezone.utc) + timedelta(minutes=minutes) if minutes else None
    await context.bot.restrict_chat_member(GROUP_ID, user_id, ChatPermissions.no_permissions(), until_date=until)


async def automatic_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.effective_message
    if not group_message(update) or not message.text or message.text.startswith("/") or URL_RE.search(message.text) or await is_exempt(context, message):
        return False
    config = await store.load("auto_replies.json")
    if not config.get("enabled", True): return False
    text = message.text.casefold()
    for trigger, reply in config.get("rules", {}).items():
        if re.search(r"(?<!\w)" + re.escape(trigger.casefold()) + r"(?!\w)", text):
            if trigger.casefold() == "ip" and not (await store.load("server.json")).get("ip"):
                reply = "ℹ️ La IP de GAMAER CITY todavía no está configurada por el equipo."
            if trigger.casefold() == "wipe" and not (await store.load("wipe_config.json")).get("manual"):
                reply = "ℹ️ El próximo wipe todavía no está configurado por el equipo."
            try:
                await message.reply_text(reply, parse_mode=ParseMode.HTML)
            except TelegramError:
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
    if not group_message(update) or await is_exempt(context, message):
        return False
    settings = await store.load("settings.json")
    if not settings.get("moderation", True) or not settings.get("word_filter", True):
        return False
    matched = word_matches(message.text or message.caption or "", settings.get("bad_words", []))
    if not matched:
        return False
    user = message.from_user
    try:
        await message.delete()
    except TelegramError:
        LOG.warning("No se pudo retirar mensaje filtrado", exc_info=True)
    warns = await store.load("warns.json")
    key = f"words:{GROUP_ID}:{user.id}"  # contador propio: no se mezcla con los /warn manuales
    warns[key] = count = int(warns.get(key, 0)) + 1
    await store.save("warns.json", warns)
    action = settings.get("word_actions", {}).get(matched, "escalate")
    severe = False
    try:
        if action == "escalate":
            if count >= 3:
                await context.bot.ban_chat_member(GROUP_ID, user.id)
                label, severe = "expulsado permanentemente y baneado", True
            else:
                minutes = 5 if count == 1 else 20
                await mute_user(context, user.id, minutes)
                label = f"silenciado {minutes} minutos y advertido"
        elif action == "mute":
            await mute_user(context, user.id, 60)
            label = "silenciado 60 minutos"
        elif action in {"kick", "ban"}:
            await context.bot.ban_chat_member(GROUP_ID, user.id)
            if action == "kick":
                await context.bot.unban_chat_member(GROUP_ID, user.id, only_if_banned=True)
            label, severe = ("expulsado" if action == "kick" else "baneado"), action == "ban"
        else:
            label = "advertido"
    except TelegramError:
        LOG.warning("No se pudo aplicar la sanción por palabra filtrada", exc_info=True)
        label = "revisado (el bot no pudo sancionar: revisa sus permisos de administrador)"
    await audit(f"word_{action}", None, user.id, f"palabra={matched} infracción={count} resultado={label}")
    try:
        await context.bot.send_message(GROUP_ID, f"⚠️ {mention(user)}: {label} por infringir el filtro de palabras. Si crees que es un error, usa /apelar en privado o /soporte.", parse_mode=ParseMode.HTML)
    except TelegramError:
        LOG.warning("No se pudo avisar de la sanción", exc_info=True)
    if severe:
        await notify_staff(context, "moderate", f"🔨 Sanción automática: <code>{user.id}</code> {esc(label)} (palabra «{esc(matched)}»). Si fue un error: /unmute o apelación.", parse_mode=ParseMode.HTML)
    return True


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_text = ("\n\n<b>🛠️ Administración</b>\n/addadmin /admin /mod /support /announcer /deladmin /listadmins\n"
                  "/panel /anuncio /pendientes /responder /tickets /moderacion /filtro /auto\n"
                  "/ban /kick /mute /unmute /warn /setreglas /setservidor /setenlaces /setwipe\n"
                  "/mantenimiento /fijar /rol /evento /sorteo /encuesta /cerrar_encuesta /testgrupo") if await is_admin(update.effective_user.id) else ""
    keyboard = [[KeyboardButton("/reglas 📜"), KeyboardButton("/servidor 🎮"), KeyboardButton("/wipe 🧨")], [KeyboardButton("/soporte 🎫"), KeyboardButton("/enlaces 🔗"), KeyboardButton("/eventos 📅")]]
    if await is_admin(update.effective_user.id):
        keyboard += [[KeyboardButton("/panel 🛠️"), KeyboardButton("/anuncio 📢"), KeyboardButton("/tickets 🎫")], [KeyboardButton("/filtro 🛡️"), KeyboardButton("/auto 🤖"), KeyboardButton("/mantenimiento 🔧")], [KeyboardButton("/sorteo 🎁")]]
    await update.effective_message.reply_text(f"🤖 <b>{esc(GROUP_NAME)}</b>\n/reglas — reglas\n/devblog — último devblog\n/servidor — IP del servidor\n/wipe — próximo wipe\n/soporte — abrir ticket\n/cancelar — cancelar flujo" + admin_text, parse_mode=ParseMode.HTML, reply_markup=public_buttons())
    if update.effective_chat.type == "private":
        await update.effective_message.reply_text("Usa también el teclado inferior para acceder rápidamente a las funciones principales.", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True))


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    extra = " Si eres el propietario del grupo y aún no hay admins, usa /claimadmin." if not admins else ""
    await update.effective_message.reply_text("✅ <b>GAMAER CITY</b>\nBot conectado. Usa los botones o /help para ver todas las funciones." + extra, parse_mode=ParseMode.HTML, reply_markup=public_buttons())


async def claim_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.effective_chat or update.effective_chat.type != "private":
        await update.effective_message.reply_text("Usa /claimadmin en el chat privado del bot."); return
    if BOT_OWNER_ID and user.id == BOT_OWNER_ID:
        admins.add(user.id); await store.save("admins.json", sorted(admins)); await audit("claim_bot_owner", user.id)
        await update.effective_message.reply_text("✅ Propietario del bot reconocido. Ya puedes administrar GAMAER CITY desde este chat privado."); return
    if admins or BOT_OWNER_ID:
        await update.effective_message.reply_text("ℹ️ Ya hay un propietario o administradores configurados. Solicita que te añadan con /addadmin."); return
    try:
        member = await context.bot.get_chat_member(GROUP_ID, user.id)
        if member.status != ChatMemberStatus.OWNER:
            await update.effective_message.reply_text("🔒 Solo el propietario del grupo puede reclamar el primer acceso administrativo."); return
    except TelegramError:
        await update.effective_message.reply_text("❌ No pude verificar que seas el propietario del grupo. Revisa GROUP_ID y los permisos del bot."); return
    admins.add(user.id); await store.save("admins.json", sorted(admins)); await audit("claim_first_admin", user.id)
    await update.effective_message.reply_text("✅ Ya eres administrador de GAMAER CITY. Usa /help para configurar el bot.")


async def admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cmd = update.effective_message.text.split()[0].split("@")[0]
    if not await private_admin(update, None if cmd == "/listadmins" else "owner"):
        return
    if cmd == "/listadmins":
        lines = [f"• <code>{user_id}</code> — {esc(await role_of(user_id))}" for user_id in sorted(admins | owner_ids())]
        await update.effective_message.reply_text("👮 Equipo:\n" + "\n".join(lines), parse_mode=ParseMode.HTML)
        return
    target = parse_user_id(context.args[0]) if len(context.args) == 1 else None
    if target is None:
        await update.effective_message.reply_text("Usa un user_id numérico. Telegram no permite resolver @username de forma fiable sin interacción previa.")
        return
    if cmd == "/addadmin":
        done = await set_role(target, "admin", update.effective_user.id)
        await update.effective_message.reply_text("✅ Admin añadido." if done else "ℹ️ Ese usuario ya es propietario.")
    else:
        done = await set_role(target, "user", update.effective_user.id)
        await update.effective_message.reply_text("✅ Admin eliminado." if done else "❌ No se puede quitar a un propietario ni a un admin definido en ADMIN_IDS.")


async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("📜 <b>Reglas de GAMAER CITY</b>\n\n" + await store.load("rules.txt"), parse_mode=ParseMode.HTML, reply_markup=public_buttons())


async def setrules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "configure"): return
    text = update.effective_message.text.partition(" ")[2].strip()
    if not text: await update.effective_message.reply_text("Usa /setreglas texto"); return
    await store.save("rules.txt", esc(text)); await refresh_pinned_message(context); await update.effective_message.reply_text("✅ Reglas guardadas.")


async def announcement_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "announce"): return
    text = update.effective_message.text.partition(" ")[2].strip()
    if not text or all(not any(char.isalnum() for char in part) for part in context.args):
        admin_states[update.effective_user.id] = {"flow": "announcement"}
        await flow_prompt(update, "📢 Escribe ahora el mensaje del anuncio. También puedes responder a un mensaje con /anuncio para copiarlo al grupo.\n\n/cancelar para salir.")
        return
    await publish_announcement(update, context, text)


async def publish_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    try:
        await context.bot.get_chat(GROUP_ID)
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
        await update.effective_message.reply_text("✅ Anuncio enviado correctamente al grupo.")
    except TelegramError as exc: LOG.exception("announcement"); await update.effective_message.reply_text(f"❌ No se pudo anunciar: {esc(exc)}")


async def test_group_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "configure"): return
    try:
        chat = await context.bot.get_chat(GROUP_ID)
        sent = await context.bot.send_message(GROUP_ID, f"🔧 Prueba de conexión de GAMAER CITY\nChat: {esc(chat.title or chat.username or GROUP_ID)}")
        await update.effective_message.reply_text(f"✅ Envío correcto al grupo. Mensaje: {sent.message_id}")
    except TelegramError as exc:
        await update.effective_message.reply_text(f"❌ Telegram no permite enviar al GROUP_ID={GROUP_ID}. Revisa que sea el ID -100... del grupo y que el bot no esté silenciado: {esc(exc)}")


async def reset_flow_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    if not user_id: return
    admin_states.pop(user_id, None)
    message_id = last_flow_messages.pop(user_id, None)
    if message_id and update.effective_chat:
        try:
            await context.bot.delete_message(update.effective_chat.id, message_id)
        except TelegramError:
            LOG.debug("No se pudo borrar el mensaje del flujo", exc_info=True)


async def moderation_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "configure"): return
    if not context.args or context.args[0].lower() not in {"on", "off"}: await update.effective_message.reply_text("Usa /moderacion on|off"); return
    settings = await store.load("settings.json"); settings["moderation"] = context.args[0].lower() == "on"; await store.save("settings.json", settings)
    await update.effective_message.reply_text(f"✅ Moderación {'activada' if settings['moderation'] else 'desactivada'}.")


async def server_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    server = await store.load("server.json")
    if not server.get("ip"):
        await update.effective_message.reply_text("ℹ️ La IP del servidor todavía no está configurada. El equipo debe establecerla antes de mostrarla.", reply_markup=public_buttons())
        return
    await update.effective_message.reply_text(
        f"🎮 <b>{esc(server.get('name', GROUP_NAME))}</b>\n"
        f"🌐 IP del servidor: <code>{esc(server['ip'])}</code>", parse_mode=ParseMode.HTML, reply_markup=public_buttons())


async def setserver_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "configure"): return
    if not context.args:
        await update.effective_message.reply_text("Usa /setservidor IP [nombre del servidor]")
        return
    ip = context.args[0]
    if len(ip) > 100 or not re.fullmatch(r"[A-Za-z0-9_.:-]+", ip):
        await update.effective_message.reply_text("IP inválida."); return
    server = await store.load("server.json")
    server.update({"ip": ip, "name": " ".join(context.args[1:]) or server.get("name", GROUP_NAME)})
    await store.save("server.json", server); await refresh_pinned_message(context)
    await update.effective_message.reply_text("✅ Datos del servidor guardados.")


async def filter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "moderate"): return
    settings = await store.load("settings.json")
    ui_only = context.args and all(not any(char.isalnum() for char in part) for part in context.args)
    if not context.args or ui_only:
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
    if not await private_admin(update, "configure"): return
    config = await store.load("auto_replies.json")
    ui_only = context.args and all(not any(char.isalnum() for char in part) for part in context.args)
    if not context.args or ui_only:
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
        config.setdefault("rules", {})[trigger] = esc(reply)[:1000]
    else:
        await update.effective_message.reply_text("Usa /auto on|off, /auto list, /auto add palabra respuesta o /auto remove palabra"); return
    await store.save("auto_replies.json", config); await update.effective_message.reply_text("✅ Respuestas automáticas actualizadas.")


async def moderate_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "moderate"):
        return
    message = update.effective_message
    cmd = message.text.split()[0].split("@")[0]
    target = parse_user_id(context.args[0]) if context.args else None
    if target is None:
        await message.reply_text(f"Usa {cmd} ID" + (" MINUTOS [motivo]" if cmd == "/mute" else " [motivo]"))
        return
    if await is_admin(target) or target == context.bot.id:
        await message.reply_text("❌ No se puede sancionar a miembros del equipo.")
        return
    actor = update.effective_user.id
    if cmd in {"/ban", "/kick"}:
        reason = " ".join(context.args[1:]) or "Sin motivo"
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=CONFIRM_TTL)
        confirmations = {k: v for k, v in (await store.load("moderation_confirmations.json")).items() if datetime.fromisoformat(v["created_at"]) > cutoff}
        confirmation_id = uid()
        confirmations[confirmation_id] = {"action": cmd[1:], "target": target, "reason": reason, "admin_id": actor, "created_at": now()}
        await store.save("moderation_confirmations.json", confirmations)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Confirmar", callback_data=f"confirmmod:{confirmation_id}"), InlineKeyboardButton("❌ Cancelar", callback_data=f"cancelmod:{confirmation_id}")]])
        await message.reply_text(f"⚠️ ¿Confirmas {cmd[1:]} a <code>{target}</code>?\nMotivo: {esc(reason)}\n(Caduca en {CONFIRM_TTL // 60} min)", parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return
    try:
        if cmd == "/mute":
            minutes = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 0
            if not 1 <= minutes <= 40320:
                await message.reply_text("Usa /mute ID MINUTOS [motivo] (entre 1 y 40320 minutos).")
                return
            await mute_user(context, target, minutes)
            detail = f"{minutes} min · " + (" ".join(context.args[2:]) or "Sin motivo")
        elif cmd == "/unmute":
            await context.bot.restrict_chat_member(GROUP_ID, target, await default_permissions(context))
            detail = "silencio retirado"
        else:  # /warn
            warns = await store.load("warns.json")
            key = f"{GROUP_ID}:{target}"
            warns[key] = count = int(warns.get(key, 0)) + 1
            await store.save("warns.json", warns)
            if count >= 3:
                await context.bot.ban_chat_member(GROUP_ID, target)
            await audit("warn", actor, target, f"{count}/3 · " + (" ".join(context.args[1:]) or "Sin motivo"))
            await message.reply_text(f"⚠️ Advertencia {count}/3 registrada." + (" Tercera advertencia: usuario baneado." if count >= 3 else ""))
            return
        await audit(cmd[1:], actor, target, detail)
        await message.reply_text(f"✅ {cmd[1:]} aplicado a <code>{target}</code>. {esc(detail)}", parse_mode=ParseMode.HTML)
    except TelegramError as exc:
        await message.reply_text(f"❌ Error de Telegram: {esc(exc)}")


async def moderation_confirmation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query
    if not await callback_guard(call, "moderate"):
        return
    action, confirmation_id = call.data.split(":", 1)
    confirmations = await store.load("moderation_confirmations.json")
    item = confirmations.pop(confirmation_id, None)
    await store.save("moderation_confirmations.json", confirmations)
    if not item:
        await safe_edit(call, "ℹ️ Esta acción ya fue procesada o caducó.")
        return
    if action == "cancelmod":
        await safe_edit(call, "❌ Acción cancelada.")
        return
    if datetime.fromisoformat(item["created_at"]) < datetime.now(timezone.utc) - timedelta(seconds=CONFIRM_TTL):
        await safe_edit(call, "⌛ La confirmación caducó. Vuelve a lanzar el comando.")
        return
    try:
        await context.bot.ban_chat_member(GROUP_ID, item["target"])
        if item["action"] == "kick":
            await context.bot.unban_chat_member(GROUP_ID, item["target"], only_if_banned=True)
        await audit(item["action"], call.from_user.id, item["target"], item["reason"])
        await safe_edit(call, f"✅ {item['action']} confirmado por {mention(call.from_user)}", parse_mode=ParseMode.HTML)
    except TelegramError as exc:
        await safe_edit(call, f"❌ Telegram rechazó la acción: {esc(exc)}")


async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.effective_message
    if await is_exempt(context, message):
        return False
    links = extract_links(message)
    if not links:
        return False
    settings = await store.load("settings.json")
    if not settings.get("moderation", True):
        return False
    bad = [link for link in links if not link_allowed(link)]
    if not bad:
        return False
    user = message.from_user
    try:
        await message.delete()
    except TelegramError:
        LOG.warning("No se pudo borrar enlace", exc_info=True)
    link_id = uid()
    pending = await store.load("pending_links.json")
    while len(pending) >= 500:  # tope para que un ataque de spam no haga crecer el archivo sin límite
        pending.pop(next(iter(pending)))
    pending[link_id] = {"link_id": link_id, "url": bad[0][:500], "user_id": user.id, "username": user.username, "name": user.full_name, "chat_id": message.chat_id, "message_id": message.message_id, "timestamp": now()}
    await store.save("pending_links.json", pending)
    try:
        await context.bot.send_message(GROUP_ID, f"⚠️ {mention(user)}: tu enlace fue retirado y está en revisión por un administrador.", parse_mode=ParseMode.HTML)
    except TelegramError:
        LOG.warning("No se pudo avisar del enlace retirado", exc_info=True)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Validar", callback_data=f"validar:{link_id}"), InlineKeyboardButton("🚫 Expulsar", callback_data=f"expulsar:{link_id}")]])
    username = f"@{esc(user.username)}" if user.username else "sin usuario"
    info = f"🔎 <b>Enlace pendiente</b> #{link_id}\nURL: <code>{esc(bad[0][:500])}</code>\nAutor: {esc(user.full_name)} {username} (<code>{user.id}</code>)\nFecha: {now()}"
    await notify_staff(context, "moderate", info, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    return True


async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "moderate"): return
    pending = await store.load("pending_links.json")
    if not pending: await update.effective_message.reply_text("✅ No hay enlaces pendientes."); return
    for item in list(pending.values())[:20]:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Validar", callback_data=f"validar:{item['link_id']}"), InlineKeyboardButton("🚫 Expulsar", callback_data=f"expulsar:{item['link_id']}")]])
        await update.effective_message.reply_text(f"#{item['link_id']} <code>{esc(item['url'])}</code>\n{esc(item['name'])}", parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query
    if not await callback_guard(call, "moderate"):
        return
    action, link_id = call.data.split(":", 1)
    pending = await store.load("pending_links.json")
    resolved = await store.load("resolved_links.json")
    if link_id in resolved or link_id not in pending:
        await safe_edit(call, "ℹ️ Este enlace ya fue resuelto.")
        return
    item = pending.pop(link_id)
    resolved[link_id] = {**item, "action": action, "admin_id": call.from_user.id, "resolved_at": now()}
    while len(resolved) > 2000:
        resolved.pop(next(iter(resolved)))
    await store.save("pending_links.json", pending)
    await store.save("resolved_links.json", resolved)
    try:
        if action == "validar":
            await context.bot.send_message(GROUP_ID, f"🔗 Enlace validado, enviado originalmente por {mention_html(item['user_id'], item['name'])}:\n{esc(item['url'])}", parse_mode=ParseMode.HTML)
            result = "✅ Validado"
        else:
            await context.bot.ban_chat_member(GROUP_ID, item["user_id"])
            await context.bot.unban_chat_member(GROUP_ID, item["user_id"], only_if_banned=True)
            result = "🚫 Expulsado"
    except TelegramError as exc:
        result = f"❌ Error: {esc(exc)}"
    await audit(f"link_{action}", call.from_user.id, item["user_id"], item["url"][:200])
    await safe_edit(call, f"{result} por {mention(call.from_user)}", parse_mode=ParseMode.HTML)


def parse_translation(data: Any) -> tuple[str, str]:
    """Extrae (texto traducido, idioma detectado) de la respuesta del endpoint gtx."""
    translated = "".join(str(part[0]) for part in (data[0] or []) if part and part[0])
    language = str(data[2]) if len(data) > 2 and data[2] else ""
    return translated, language


_translate_slots = asyncio.Semaphore(3)


async def translate_text(text: str) -> tuple[str, str]:
    params = {"client": "gtx", "sl": "auto", "tl": "es", "dt": "t", "q": text[:1000]}
    async with _translate_slots:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get("https://translate.googleapis.com/translate_a/single", params=params) as response:
                response.raise_for_status()
                return parse_translation(await response.json(content_type=None))


async def translate_and_reply(message: Any) -> None:
    """Se ejecuta en segundo plano para no bloquear la moderación mientras se espera a la red."""
    text = (message.text or "").strip()
    if len(text) < 4 or not any(char.isalpha() for char in text):
        return
    try:
        translated, language = await translate_text(text)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, IndexError, TypeError) as exc:
        LOG.warning("Traducción no disponible: %s", exc)
        return
    if language.split("-")[0] == "es" or not translated or translated.strip().casefold() == text.casefold():
        return
    try:
        await message.reply_text(f"🌐 <b>Traducción al español</b>\n{esc(translated)}", parse_mode=ParseMode.HTML)
    except TelegramError:
        LOG.warning("No se pudo enviar la traducción", exc_info=True)


async def media_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not MEDIA_MODERATION or not group_message(update) or await is_exempt(context, message):
        return
    settings = await store.load("settings.json")
    if settings.get("moderation", True) and message_kind(message) in MEDIA_ATTRS:
        try:
            await message.delete()
            await context.bot.send_message(GROUP_ID, "⚠️ Las fotos, vídeos y archivos requieren autorización de un administrador.")
        except TelegramError:
            LOG.warning("No se pudo moderar multimedia", exc_info=True)


async def devblog_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get("https://rust.facepunch.com/rss/news") as response:
                response.raise_for_status()
                body = await response.read()
        feed = await asyncio.to_thread(feedparser.parse, body)
        entry = feed.entries[0]
        title, link = str(entry.title), str(entry.link)
        if not link.lower().startswith(("https://", "http://")):
            raise ValueError("enlace no válido en el feed")
    except (aiohttp.ClientError, asyncio.TimeoutError, IndexError, AttributeError, ValueError):
        LOG.warning("No se pudo consultar el RSS del devblog", exc_info=True)
        await update.effective_message.reply_text("❌ No se pudo consultar el devblog ahora mismo. Inténtalo más tarde.")
        return
    await update.effective_message.reply_text(f"📰 <b>{esc(title)}</b>\n{esc(link)}", parse_mode=ParseMode.HTML)


async def wipe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = await store.load("wipe_config.json"); target = None
    if config.get("manual"):
        try: target = datetime.fromisoformat(config["manual"])
        except ValueError: pass
    if context.args and context.args[0].lower() == "recordatorio":
        if not target: await update.effective_message.reply_text("ℹ️ Todavía no hay un wipe configurado por el equipo."); return
        if update.effective_user.id not in config.setdefault("reminders", []): config["reminders"].append(update.effective_user.id); await store.save("wipe_config.json", config)
        await update.effective_message.reply_text("✅ Te avisaré por privado una hora antes del wipe. Asegúrate de haber pulsado /start en mi chat privado."); return
    if not target:
        await update.effective_message.reply_text("ℹ️ El próximo wipe todavía no está configurado. El equipo debe usar /setwipe DD/MM/YYYY HH:MM.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Comprobar de nuevo", callback_data="nav:wipe")]])); return
    remaining = target - datetime.now(timezone.utc)
    total = max(0, int(remaining.total_seconds())); days, rem = divmod(total, 86400); hours, rem = divmod(rem, 3600); minutes = rem // 60
    await update.effective_message.reply_text(f"🧨 <b>Próximo wipe de Rust</b>\n📅 {target.strftime('%d/%m/%Y')}\n⏰ {target.strftime('%H:%M')} UTC\n⏳ Faltan: {days} días, {hours} horas, {minutes} minutos", parse_mode=ParseMode.HTML, reply_markup=public_buttons())


async def setwipe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "configure"): return
    try: target = datetime.strptime(" ".join(context.args), "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc); config = await store.load("wipe_config.json"); config["manual"] = target.isoformat(); await store.save("wipe_config.json", config); await update.effective_message.reply_text("✅ Wipe manual guardado en UTC.")
    except ValueError: await update.effective_message.reply_text("Usa /setwipe DD/MM/YYYY HH:MM")


async def close_expired_polls(context: ContextTypes.DEFAULT_TYPE) -> None:
    polls = await store.load("encuestas.json")
    changed = False
    for poll in polls.values():
        if poll.get("closed") or not poll.get("expires_at"):
            continue
        if datetime.fromisoformat(poll["expires_at"]) <= datetime.now(timezone.utc):
            poll["closed"] = changed = True
            if poll.get("message_id"):
                try:
                    await context.bot.edit_message_text(poll_text(poll, closed=True), GROUP_ID, poll["message_id"], parse_mode=ParseMode.HTML, reply_markup=None)
                except TelegramError:
                    LOG.warning("No se pudo cerrar encuesta %s", poll.get("id"))
    if changed:
        await store.save("encuestas.json", polls)


async def send_wipe_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    config = await store.load("wipe_config.json")
    try:
        target = datetime.fromisoformat(config["manual"]) if config.get("manual") else None
    except ValueError:
        target = None
    if not target or config.get("last_reminder") == target.isoformat():
        return
    if target - timedelta(hours=1) <= datetime.now(timezone.utc) < target:
        for user_id in config.get("reminders", []):
            try:
                await context.bot.send_message(user_id, f"⏰ Recordatorio: el wipe de Rust es en menos de una hora ({target.strftime('%d/%m/%Y %H:%M')} UTC).")
            except TelegramError:
                LOG.info("No se pudo avisar del wipe al usuario %s", user_id)
        config["last_reminder"] = target.isoformat()
        await store.save("wipe_config.json", config)


async def flag_stale_tickets(context: ContextTypes.DEFAULT_TYPE) -> None:
    tickets = await store.load("tickets.json")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    changed = False
    for ticket in tickets.values():
        if ticket.get("status") == "abierto" and not ticket.get("timeout_notified") and datetime.fromisoformat(ticket["timestamp"]) < cutoff:
            ticket["timeout_notified"] = changed = True
            await notify_staff(context, "support", f"⏰ El ticket #{ticket['ticket_id']} lleva más de 24 horas abierto.")
    if changed:
        await store.save("tickets.json", tickets)


async def send_event_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    events = await store.load("events.json")
    changed = False
    current = datetime.now(timezone.utc)
    for event in events.values():
        if event.get("status") != "active" or event.get("reminder_sent") or not event.get("starts_at"):
            continue
        starts = datetime.fromisoformat(event["starts_at"])
        if starts - timedelta(hours=1) <= current < starts:
            event["reminder_sent"] = changed = True
            try:
                await context.bot.send_message(GROUP_ID, f"⏰ Recordatorio: el evento comienza en menos de una hora.\n{esc(event['text'])}", parse_mode=ParseMode.HTML)
            except TelegramError:
                LOG.warning("No se pudo enviar el recordatorio del evento %s", event.get("id"))
    if changed:
        await store.save("events.json", events)


async def automation_tick(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tareas idempotentes cada minuto. Cada una falla por separado y todas toleran reinicios."""
    for task in (close_expired_polls, send_wipe_reminders, flag_stale_tickets, send_event_reminders):
        try:
            await task(context)
        except Exception:  # noqa: BLE001 - una tarea rota no debe parar a las demás
            LOG.exception("automation_tick: falló %s", task.__name__)


async def soporte_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if group_message(update):
        try:
            await update.effective_message.delete()
        except TelegramError:
            LOG.debug("No se pudo borrar el comando", exc_info=True)
        await context.bot.send_message(GROUP_ID, "Usa /soporte en mi chat privado para abrir un ticket."); return
    if not context.args: admin_states[update.effective_user.id] = {"flow": "ticket"}; await update.effective_message.reply_text("Escribe el problema que quieres enviar al equipo."); return
    await create_ticket(update, " ".join(context.args), context)


async def create_ticket(update: Update, text: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if rate_limited(user.id, "ticket", 60):
        await update.effective_message.reply_text("⏳ Espera un minuto antes de abrir otro ticket.")
        return
    text = text.strip()[:1500]
    tickets = await store.load("tickets.json")
    ticket_id = uid().upper()
    tickets[ticket_id] = {"ticket_id": ticket_id, "user_id": user.id, "username": user.username, "name": user.full_name, "message": text, "timestamp": now(), "status": "abierto", "admin_id": None}
    await store.save("tickets.json", tickets)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Atender", callback_data=f"atender:{ticket_id}"), InlineKeyboardButton("❌ Cerrar", callback_data=f"cerrar:{ticket_id}")]])
    username = f"@{esc(user.username)}" if user.username else "sin usuario"
    reached = await notify_staff(context, "support", f"🎫 <b>Ticket #{ticket_id}</b>\nUsuario: {esc(user.full_name)} {username} (<code>{user.id}</code>)\n\n{esc(text)}", parse_mode=ParseMode.HTML, reply_markup=keyboard)
    note = "" if reached else " (Aviso: ningún miembro del equipo pudo recibirlo todavía; quedará registrado.)"
    await update.effective_message.reply_text(f"✅ Ticket #{ticket_id} creado. El equipo te responderá por este chat.{note}")


async def tickets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "support"): return
    tickets = await store.load("tickets.json"); active = [x for x in tickets.values() if x["status"] != "cerrado"]
    await update.effective_message.reply_text("\n".join(f"#{x['ticket_id']} — {esc(x['name'])} — {x['status']}" for x in active) or "No hay tickets activos.", parse_mode=ParseMode.HTML)


async def ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query
    if not await callback_guard(call, "support"):
        return
    action, ticket_id = call.data.split(":", 1)
    tickets = await store.load("tickets.json")
    ticket = tickets.get(ticket_id)
    admin_id = call.from_user.id
    if not ticket:
        await safe_edit(call, "Ticket no encontrado.")
        return
    if ticket["status"] == "cerrado":
        await safe_edit(call, f"ℹ️ El ticket #{ticket_id} ya está cerrado.")
        return
    if action in {"atender", "reptk"}:
        if ticket["status"] == "en_proceso" and ticket.get("admin_id") != admin_id:
            await safe_edit(call, f"ℹ️ Ticket ya atendido por {ticket.get('admin_id')}.")
            return
        ticket["status"], ticket["admin_id"] = "en_proceso", admin_id
        await store.save("tickets.json", tickets)
        admin_states[admin_id] = {"flow": "ticket_reply", "ticket_id": ticket_id}
        await safe_edit(call, f"✅ Has tomado #{ticket_id}. Envía ahora tu respuesta (un mensaje). /cancelar para salir.")
        return
    ticket.update(status="cerrado", closed_by=admin_id, closed_at=now())
    await store.save("tickets.json", tickets)
    await audit("ticket_close", admin_id, ticket["user_id"], ticket_id)
    await safe_edit(call, f"✅ Ticket #{ticket_id} cerrado.")
    try:
        await context.bot.send_message(ticket["user_id"], f"Tu ticket #{ticket_id} ha sido cerrado. Si necesitas más ayuda, usa /soporte de nuevo.")
    except TelegramError:
        LOG.info("No se pudo avisar del cierre al usuario %s", ticket["user_id"])


async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query
    try:
        target_id = int(call.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await answer(call)
        return
    if call.from_user.id != target_id:
        await answer(call, "Este botón no es para tu cuenta.", True)
        return
    try:
        member = await context.bot.get_chat_member(GROUP_ID, target_id)
    except TelegramError:
        await answer(call, "No pude comprobar tu estado. Inténtalo de nuevo en unos segundos.", True)
        return
    if member.status in {ChatMemberStatus.LEFT, ChatMemberStatus.BANNED}:
        await answer(call, "Ya no estás en el grupo.", True)
        return
    if member.status == ChatMemberStatus.RESTRICTED:
        if getattr(member, "until_date", None):  # restricción temporal = sanción de moderación, no la puerta de verificación
            await answer(call, "Tienes una restricción temporal activa; este botón no puede levantarla.", True)
            return
        try:
            await context.bot.restrict_chat_member(GROUP_ID, target_id, await default_permissions(context))
        except TelegramError:
            LOG.warning("No se pudo liberar al usuario verificado", exc_info=True)
            await answer(call, "No pude liberarte. Avisa a un administrador.", True)
            return
    verified = await store.load("verified.json")
    verified[str(target_id)] = {"chat_id": GROUP_ID, "timestamp": now()}
    await store.save("verified.json", verified)
    await answer(call, "✅ Verificado")
    await safe_edit(call, "✅ Verificación completada. Ya puedes participar en GAMAER CITY.")


SECTION_PERMISSIONS = {"announcement": "announce", "setserver": "configure", "setwipe": "configure", "admin": "owner", "mod": "owner", "maintenance": "configure"}


async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query
    section = call.data.split(":", 1)[1]
    if not await callback_guard(call, SECTION_PERMISSIONS.get(section)):
        return
    flows = {
        "announcement": ({"flow": "announcement"}, "📢 Escribe ahora el mensaje que quieres publicar en GAMAER CITY.\n\n/cancelar para salir."),
        "setserver": ({"flow": "setserver"}, "🌐 Escribe la IP y opcionalmente el nombre. Ejemplo: 123.45.67.89 GAMAER CITY"),
        "setwipe": ({"flow": "setwipe"}, "🧨 Escribe la fecha UTC con formato DD/MM/YYYY HH:MM. Ejemplo: 20/11/2026 19:00"),
    }
    if section in flows:
        state, prompt = flows[section]
        admin_states[call.from_user.id] = state
        await flow_prompt(update, prompt)
        return
    if section in {"admin", "mod"}:
        role = "admin" if section == "admin" else "moderator"
        admin_states[call.from_user.id] = {"flow": "assign_role", "role": role}
        await flow_prompt(update, f"Escribe el ID numérico para asignar el rol {role}.")
        return
    if section == "rules":
        text = await store.load("rules.txt")
    elif section == "server":
        server = await store.load("server.json")
        text = f"🎮 {esc(server.get('name', GROUP_NAME))}\nIP: <code>{esc(server.get('ip') or 'no configurada')}</code>"
    elif section == "links":
        text = "Usa /pendientes para revisar enlaces."
    elif section == "tickets":
        text = "Usa /tickets para ver tickets activos."
    else:
        settings = await store.load("settings.json")
        settings["maintenance"] = not settings.get("maintenance", False)
        await store.save("settings.json", settings)
        await audit("maintenance_panel", call.from_user.id, details=str(settings["maintenance"]))
        text = f"✅ Mantenimiento {'activado' if settings['maintenance'] else 'desactivado'}"
    await safe_edit(call, text, parse_mode=ParseMode.HTML)


async def public_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query; await answer(call); section = call.data.split(":", 1)[1]
    if section == "rules": text = "📜 <b>Reglas de GAMAER CITY</b>\n\n" + await store.load("rules.txt")
    elif section == "server":
        server = await store.load("server.json")
        text = "ℹ️ La IP aún no está configurada por el equipo." if not server.get("ip") else f"🎮 <b>{esc(server.get('name', GROUP_NAME))}</b>\n🌐 IP: <code>{esc(server['ip'])}</code>"
    elif section == "wipe":
        config = await store.load("wipe_config.json")
        text = "ℹ️ El wipe todavía no está configurado. El equipo debe usar /setwipe." if not config.get("manual") else "🧨 Consulta la fecha y el contador con /wipe."
    elif section == "links":
        links = await store.load("official_links.json"); text = "🔗 <b>Enlaces oficiales</b>\n" + "\n".join(f"• {esc(k.title())}: {esc(v)}" for k, v in links.items() if v) if any(links.values()) else "ℹ️ Todavía no hay enlaces oficiales configurados."
    elif section == "support": text = "🎫 Para abrir un ticket, pulsa /soporte y escribe tu consulta."
    elif section == "events":
        events = await store.load("events.json"); active = [e for e in events.values() if e.get("status") == "active"]; text = "📅 Eventos activos:\n" + "\n".join(f"• #{e['id']} — {esc(e['text'])}" for e in active) if active else "📅 No hay eventos configurados."
    elif section == "giveaways":
        giveaways = await store.load("giveaways.json"); active = [g for g in giveaways.values() if g.get("status") == "active"]; text = "🎁 Sorteos activos:\n" + "\n".join(f"• #{g['id']} — {esc(g['prize'])}" for g in active) if active else "🎁 No hay sorteos configurados."
    else: text = "🤖 Usa /help para ver todos los comandos disponibles."
    await safe_edit(call, text, parse_mode=ParseMode.HTML, reply_markup=public_buttons())


def _in_chat(member: Any) -> bool:
    return member.status in {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER} or (
        member.status == ChatMemberStatus.RESTRICTED and bool(getattr(member, "is_member", False)))


async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    change = update.chat_member
    # Solo cuando alguien ENTRA al grupo: los cambios de estado (mute, ascenso...) también llegan aquí.
    if not change or change.chat.id != GROUP_ID or _in_chat(change.old_chat_member) or not _in_chat(change.new_chat_member):
        return
    member = change.new_chat_member.user
    if member.is_bot:
        return
    verified = await store.load("verified.json")
    if str(member.id) not in verified:
        try:
            await context.bot.restrict_chat_member(GROUP_ID, member.id, ChatPermissions.no_permissions())
        except TelegramError:
            LOG.warning("No se pudo restringir a nuevo miembro", exc_info=True)
    config = await store.load("welcome.json")
    greeting = ""
    if config.get("enabled", True):
        custom = config.get("text") or "👋 Bienvenido {nombre} a {grupo}!"
        greeting = custom.replace("{nombre}", esc(member.first_name or member.full_name)).replace("{grupo}", esc(GROUP_NAME)) + "\n\n"
    text = greeting + "📜 <b>Reglas de GAMAER CITY</b>\n\n" + await store.load("rules.txt") + "\n\nPulsa el botón para confirmar que las has leído y verificarte."
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ He leído las reglas y me verifico", callback_data=f"verify:{member.id}")]])
    await context.bot.send_message(GROUP_ID, text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_states.pop(update.effective_user.id, None); await update.effective_message.reply_text("✅ Flujo cancelado.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _last_error_notice
    error = context.error
    if isinstance(error, BadRequest) and "not modified" in str(error).lower():
        return
    if isinstance(error, (NetworkError, TimedOut)):
        LOG.warning("Error de red transitorio: %s", error)
        return
    LOG.error("Error procesando actualización", exc_info=error)
    if time.monotonic() - _last_error_notice < 600:  # como máximo un aviso cada 10 minutos
        return
    _last_error_notice = time.monotonic()
    for owner in owner_ids():
        try:
            await context.bot.send_message(owner, f"⚠️ El bot registró un error ({type(error).__name__}) y sigue funcionando. Revisa los logs.")
        except TelegramError:
            pass


async def official_links_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    links = await store.load("official_links.json")
    text = "🔗 <b>Enlaces oficiales de GAMAER CITY</b>\n" + "\n".join(f"• {esc(key.title())}: {esc(value)}" for key, value in links.items() if value)
    await update.effective_message.reply_text(text if any(links.values()) else "ℹ️ Todavía no hay enlaces oficiales configurados.", parse_mode=ParseMode.HTML)


async def set_links_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "configure"): return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Usa /setenlaces discord|web|channel|donaciones URL")
        return
    key, value = context.args[0].lower(), " ".join(context.args[1:])
    if key not in {"discord", "web", "channel", "donaciones"}:
        await update.effective_message.reply_text("Categoría inválida."); return
    links = await store.load("official_links.json"); links[key] = value; await store.save("official_links.json", links); await update.effective_message.reply_text("✅ Enlace oficial actualizado.")


async def pin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not group_message(update) or not user or not await has_permission(user.id, "configure"):
        return
    if not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("Responde a un mensaje con /fijar para fijarlo como mensaje oficial.")
        return
    try:
        target = update.effective_message.reply_to_message.message_id
        await context.bot.pin_chat_message(GROUP_ID, target, disable_notification=True)
        settings = await store.load("settings.json")
        settings["pinned_message_id"] = target
        await store.save("settings.json", settings)
        await audit("pin", user.id, details=str(target))
        await update.effective_message.reply_text("✅ Mensaje oficial fijado.")
    except TelegramError as exc:
        await update.effective_message.reply_text(f"❌ No se pudo fijar: {esc(exc)}")


async def maintenance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "configure"): return
    settings = await store.load("settings.json")
    ui_only = context.args and all(not any(char.isalnum() for char in part) for part in context.args)
    if not context.args or ui_only or context.args[0].lower() not in {"on", "off"}:
        await update.effective_message.reply_text(f"Mantenimiento: {'activo' if settings.get('maintenance') else 'inactivo'}"); return
    settings["maintenance"] = context.args[0].lower() == "on"; await store.save("settings.json", settings); await audit("maintenance", update.effective_user.id, details=str(settings["maintenance"]))
    await update.effective_message.reply_text("✅ Modo mantenimiento actualizado.")


async def panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update): return
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Crear anuncio", callback_data="panel:announcement")], [InlineKeyboardButton("🌐 Configurar IP", callback_data="panel:setserver"), InlineKeyboardButton("🧨 Configurar wipe", callback_data="panel:setwipe")], [InlineKeyboardButton("🔎 Enlaces", callback_data="panel:links"), InlineKeyboardButton("🎫 Tickets", callback_data="panel:tickets")], [InlineKeyboardButton("📜 Reglas", callback_data="panel:rules"), InlineKeyboardButton("👮 Admin", callback_data="panel:admin")], [InlineKeyboardButton("🛡️ Mod", callback_data="panel:mod"), InlineKeyboardButton("🛠️ Mantenimiento", callback_data="panel:maintenance")]])
    await update.effective_message.reply_text("🛠️ <b>Panel de GAMAER CITY</b>\nSelecciona una sección:", parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def submit_appeal(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    user = update.effective_user
    if rate_limited(user.id, "appeal", 300):
        await update.effective_message.reply_text("⏳ Espera unos minutos antes de enviar otra apelación.")
        return
    text = text.strip()[:1500]
    appeals = await store.load("appeals.json")
    appeal_id = uid().upper()
    appeals[appeal_id] = {"id": appeal_id, "user_id": user.id, "text": text, "status": "open", "timestamp": now()}
    await store.save("appeals.json", appeals)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Retirar sanción", callback_data=f"appeal:accept:{appeal_id}"), InlineKeyboardButton("⏳ Mantener", callback_data=f"appeal:keep:{appeal_id}")], [InlineKeyboardButton("❌ Rechazar", callback_data=f"appeal:reject:{appeal_id}")]])
    await notify_staff(context, "moderate", f"⚖️ <b>Apelación #{appeal_id}</b>\nUsuario: {mention(user)} (<code>{user.id}</code>)\n\n{esc(text)}", parse_mode=ParseMode.HTML, reply_markup=keyboard)
    await update.effective_message.reply_text("✅ Apelación enviada al equipo.")


async def appeal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text("Usa /apelar en el chat privado del bot.")
        return
    text = " ".join(context.args).strip()
    if not text:
        admin_states[update.effective_user.id] = {"flow": "appeal"}
        await update.effective_message.reply_text("Explica por qué consideras injusta la sanción. /cancelar para salir.")
        return
    await submit_appeal(update, context, text)


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text("Usa /reportar en privado y proporciona el ID del usuario y el motivo.")
        return
    target = parse_user_id(context.args[0]) if context.args else None
    if target is None or len(context.args) < 2:
        await update.effective_message.reply_text("Usa /reportar USER_ID motivo")
        return
    if rate_limited(update.effective_user.id, "report", 30):
        await update.effective_message.reply_text("⏳ Espera unos segundos antes de enviar otro reporte.")
        return
    text = " ".join(context.args[1:])[:1500]
    reports = await store.load("reports.json")
    report_id = uid().upper()
    reports[report_id] = {"id": report_id, "reporter_id": update.effective_user.id, "target_id": target, "text": text, "status": "open", "timestamp": now()}
    await store.save("reports.json", reports)
    await audit("report", update.effective_user.id, target, text)
    await notify_staff(context, "moderate", f"🚨 <b>Reporte #{report_id}</b>\nReportado: <code>{target}</code>\nMotivo: {esc(text)}", parse_mode=ParseMode.HTML)
    await update.effective_message.reply_text("✅ Reporte enviado a los administradores.")


async def appeal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query
    if not await callback_guard(call, "moderate"):
        return
    _, action, appeal_id = call.data.split(":", 2)
    appeals = await store.load("appeals.json")
    appeal = appeals.get(appeal_id)
    if not appeal or appeal.get("status") != "open":
        await safe_edit(call, "ℹ️ Apelación ya resuelta.")
        return
    appeal.update(status=action, reviewed_by=call.from_user.id, reviewed_at=now())
    await store.save("appeals.json", appeals)
    await audit("appeal_" + action, call.from_user.id, appeal["user_id"], appeal_id)
    if action == "accept":
        user_id = appeal["user_id"]
        warns = await store.load("warns.json")
        for key in (f"words:{GROUP_ID}:{user_id}", f"{GROUP_ID}:{user_id}"):
            warns.pop(key, None)
        await store.save("warns.json", warns)
        try:
            await context.bot.unban_chat_member(GROUP_ID, user_id, only_if_banned=True)
            await context.bot.restrict_chat_member(GROUP_ID, user_id, await default_permissions(context))
        except TelegramError:
            LOG.info("Al aceptar la apelación no hizo falta (o no se pudo) restaurar permisos de %s", user_id)
        message = "✅ Apelación aceptada. Tu sanción fue retirada."
    elif action == "keep":
        message = "⏳ La sanción se mantiene tras revisión."
    else:
        message = "❌ Apelación rechazada por el equipo."
    try:
        await context.bot.send_message(appeal["user_id"], message)
    except TelegramError:
        LOG.info("No se pudo notificar la apelación al usuario %s", appeal["user_id"])
    await safe_edit(call, f"Apelación #{appeal_id}: {action} por {mention(call.from_user)}", parse_mode=ParseMode.HTML)


async def roles_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "owner"):
        return
    target = parse_user_id(context.args[0]) if context.args else None
    if target is None or len(context.args) < 2 or context.args[1] not in {"admin", "moderator", "support", "announcer", "user"}:
        await update.effective_message.reply_text("Usa /rol USER_ID admin|moderator|support|announcer|user")
        return
    done = await set_role(target, context.args[1], update.effective_user.id)
    await update.effective_message.reply_text("✅ Rol actualizado." if done else "❌ No se puede cambiar el rol de un propietario ni quitar a un admin definido en ADMIN_IDS.")


async def role_alias_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "owner"):
        return
    alias = update.effective_message.text.split()[0].split("@")[0].lstrip("/").lower()
    role = {"admin": "admin", "mod": "moderator", "support": "support", "announcer": "announcer"}.get(alias)
    target = parse_user_id(context.args[0]) if len(context.args) == 1 else None
    if not role or target is None:
        await update.effective_message.reply_text(f"Usa /{alias} USER_ID")
        return
    if await set_role(target, role, update.effective_user.id):
        await update.effective_message.reply_text(f"✅ Usuario {target} asignado como {role}.")
    else:
        await update.effective_message.reply_text("❌ No se puede cambiar el rol de un propietario.")


async def events_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    events = await store.load("events.json")
    sub = context.args[0].lower() if context.args else ""
    if sub == "crear":
        if not await private_admin(update, "announce"):
            return
        text = " ".join(context.args[1:]).strip()[:1000]
        if not text:
            await update.effective_message.reply_text("Usa /evento crear Título | fecha ISO (2026-11-20T19:00:00, UTC) | detalles")
            return
        event_id = uid().upper()
        event = {"id": event_id, "text": text, "created_at": now(), "status": "active", "reminder_sent": False}
        parts = [part.strip() for part in text.split("|")]
        if len(parts) > 1:
            try:
                starts = datetime.fromisoformat(parts[1])
                event["starts_at"] = (starts if starts.tzinfo else starts.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
            except ValueError:
                pass
        events[event_id] = event
        await store.save("events.json", events)
        await context.bot.send_message(GROUP_ID, f"📅 <b>Evento #{event_id}</b>\n\n{esc(text)}", parse_mode=ParseMode.HTML)
        await update.effective_message.reply_text("✅ Evento publicado." + ("" if "starts_at" in event else " (Sin fecha ISO válida: no habrá recordatorio automático.)"))
        return
    if sub == "cancelar" and len(context.args) > 1:
        if not await private_admin(update, "announce"):
            return
        if context.args[1] in events:
            events[context.args[1]]["status"] = "cancelled"
            await store.save("events.json", events)
            await update.effective_message.reply_text("✅ Evento cancelado.")
        else:
            await update.effective_message.reply_text("Evento no encontrado.")
        return
    active = [event for event in events.values() if event.get("status") == "active"]
    await update.effective_message.reply_text("📅 Eventos activos:\n" + "\n".join(f"#{e['id']} — {esc(e['text'])}" for e in active) if active else "No hay eventos activos.", parse_mode=ParseMode.HTML)


async def giveaway_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    giveaways = await store.load("giveaways.json")
    sub = context.args[0].lower() if context.args else ""
    if sub == "cerrar" and len(context.args) > 1:
        if not await private_admin(update, "announce"):
            return
        giveaway = giveaways.get(context.args[1])
        if not giveaway:
            await update.effective_message.reply_text("Sorteo no encontrado.")
            return
        if giveaway.get("status") != "active":
            await update.effective_message.reply_text("Ese sorteo ya está cerrado.")
            return
        winner = secrets.choice(giveaway["participants"]) if giveaway["participants"] else None
        giveaway.update(status="closed", winner=winner)
        await store.save("giveaways.json", giveaways)
        await audit("giveaway_close", update.effective_user.id, winner, context.args[1])
        if winner:
            name = "participante"
            try:
                name = (await context.bot.get_chat_member(GROUP_ID, winner)).user.full_name
            except TelegramError:
                pass
            await context.bot.send_message(GROUP_ID, f"🎉 Sorteo #{context.args[1]} cerrado. Ganador: {mention_html(winner, name)}\nPremio: {esc(giveaway['prize'])}", parse_mode=ParseMode.HTML)
        else:
            await context.bot.send_message(GROUP_ID, f"🎁 Sorteo #{context.args[1]} cerrado sin participantes.")
        await update.effective_message.reply_text("✅ Sorteo cerrado.")
        return
    if sub == "crear":
        if not await private_admin(update, "announce"):
            return
        prize = " ".join(context.args[1:]).strip()[:300]
        if not prize:
            await update.effective_message.reply_text("Usa /sorteo crear Premio")
            return
        giveaway_id = uid().upper()
        giveaways[giveaway_id] = {"id": giveaway_id, "prize": prize, "participants": [], "status": "active", "created_at": now()}
        await store.save("giveaways.json", giveaways)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🎟️ Participar", callback_data=f"giveaway:{giveaway_id}")]])
        await context.bot.send_message(GROUP_ID, f"🎁 <b>Sorteo #{giveaway_id}</b>\nPremio: {esc(prize)}\nPulsa el botón para participar.", parse_mode=ParseMode.HTML, reply_markup=keyboard)
        await update.effective_message.reply_text("✅ Sorteo publicado.")
        return
    active = [g for g in giveaways.values() if g.get("status") == "active"]
    await update.effective_message.reply_text("🎁 Sorteos activos:\n" + "\n".join(f"#{g['id']} — {esc(g['prize'])} ({len(g['participants'])} participantes)" for g in active) if active else "No hay sorteos activos.", parse_mode=ParseMode.HTML)


async def giveaway_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query
    giveaway_id = call.data.split(":", 1)[1]
    giveaways = await store.load("giveaways.json")
    giveaway = giveaways.get(giveaway_id)
    if not giveaway or giveaway.get("status") != "active":
        await answer(call, "Sorteo cerrado", True)
        return
    user_id = call.from_user.id
    if user_id in giveaway["participants"]:
        await answer(call, "Ya estás participando", True)
        return
    giveaway["participants"].append(user_id)
    await store.save("giveaways.json", giveaways)
    await answer(call, "Participación registrada")


async def responder_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "support"): return
    if not recent_messages:
        await update.effective_message.reply_text("No hay mensajes recientes en caché."); return
    lines = []
    for index, message in enumerate(recent_messages, 1):
        kind = message_kind(message)
        summary = (message.text or message.caption or "").replace("\n", " ")[:60]
        lines.append(f"{index}. {esc(message.from_user.full_name)} · {kind} · {esc(summary)}")
    admin_states[update.effective_user.id] = {"flow": "respond_number"}
    await update.effective_message.reply_text("Selecciona el número del mensaje:\n" + "\n".join(lines))


async def encuesta_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "announce"): return
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


def poll_text(poll: dict[str, Any], closed: bool = False) -> str:
    counts = [sum(1 for vote in poll.get("votes", {}).values() if vote == i) for i in range(len(poll["options"]))]
    header = "📊 <b>Encuesta cerrada: " if closed else "📊 <b>Encuesta: "
    return header + esc(poll["title"]) + "</b>\n\n" + "\n".join(f"{i + 1}. {esc(x)} — {counts[i]} votos" for i, x in enumerate(poll["options"]))


async def poll_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    call = update.callback_query
    try:
        _, poll_id, option = call.data.split(":", 2)
        index = int(option)
    except ValueError:
        await answer(call)
        return
    polls = await store.load("encuestas.json")
    poll = polls.get(poll_id)
    if not poll or poll.get("closed"):
        await answer(call, "Encuesta cerrada", True)
        return
    if not 0 <= index < len(poll["options"]):
        await answer(call)
        return
    voter = str(call.from_user.id)
    if voter in poll["votes"]:
        await answer(call, "Ya has votado", True)
        return
    poll["votes"][voter] = index
    await store.save("encuestas.json", polls)
    await answer(call, "Voto registrado")
    await safe_edit(call, poll_text(poll), parse_mode=ParseMode.HTML, reply_markup=call.message.reply_markup)


async def encuestas_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    polls = await store.load("encuestas.json"); active = [p for p in polls.values() if not p.get("closed")]
    await update.effective_message.reply_text("📊 <b>Encuestas activas</b>\n" + "\n".join(f"• #{p['id']} — {esc(p['title'])} ({len(p['votes'])} votos)" for p in active) if active else "📊 No hay encuestas configuradas.", parse_mode=ParseMode.HTML, reply_markup=public_buttons())


async def cerrar_encuesta_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_admin(update, "announce"):
        return
    if not context.args:
        await update.effective_message.reply_text("Usa /cerrar_encuesta ID")
        return
    polls = await store.load("encuestas.json")
    poll = polls.get(context.args[0])
    if not poll:
        await update.effective_message.reply_text("Encuesta no encontrada.")
        return
    poll["closed"] = True
    await store.save("encuestas.json", polls)
    if poll.get("message_id"):
        try:
            await context.bot.edit_message_text(poll_text(poll, closed=True), GROUP_ID, poll["message_id"], parse_mode=ParseMode.HTML, reply_markup=None)
        except TelegramError:
            LOG.warning("No se pudo actualizar el mensaje de la encuesta %s", context.args[0])
    await update.effective_message.reply_text("✅ Encuesta cerrada.")


FLOW_PERMISSIONS = {"setserver": "configure", "setwipe": "configure", "announcement": "announce", "assign_role": "owner", "respond_number": "support", "respond_text": "support", "ticket_reply": "support"}


async def handle_private_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Flujos de varios pasos. Solo en privado, con permiso comprobado en cada paso y caducidad automática."""
    message, user = update.effective_message, update.effective_user
    state = admin_states.get(user.id)
    if not state:
        return
    flow, text = state.get("flow"), (message.text or "").strip()
    permission = FLOW_PERMISSIONS.get(flow)
    if permission and not await has_permission(user.id, permission):
        admin_states.pop(user.id, None)
        await message.reply_text("🔒 Tu rol no tiene permiso para esta función.")
        return
    if flow == "setserver":
        admin_states.pop(user.id, None)
        args = text.split()
        if not args or len(args[0]) > 100 or not re.fullmatch(r"[A-Za-z0-9_.:-]+", args[0]):
            await message.reply_text("❌ IP inválida.")
            return
        server = await store.load("server.json")
        server.update({"ip": args[0], "name": " ".join(args[1:]) or server.get("name", GROUP_NAME)})
        await store.save("server.json", server)
        await refresh_pinned_message(context)
        await message.reply_text("✅ IP del servidor guardada y publicada.")
    elif flow == "setwipe":
        admin_states.pop(user.id, None)
        try:
            target = datetime.strptime(text, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            await message.reply_text("❌ Formato inválido. Usa DD/MM/YYYY HH:MM.")
            return
        config = await store.load("wipe_config.json")
        config["manual"] = target.isoformat()
        await store.save("wipe_config.json", config)
        await message.reply_text(f"✅ Wipe guardado: {target.strftime('%d/%m/%Y %H:%M')} UTC.")
    elif flow == "announcement":
        admin_states.pop(user.id, None)
        await publish_announcement(update, context, text)
    elif flow == "assign_role":
        target = parse_user_id(text)
        if target is None:
            await message.reply_text("Escribe un ID numérico o /cancelar.")
            return
        admin_states.pop(user.id, None)
        done = await set_role(target, state["role"], user.id)
        await message.reply_text(f"✅ Usuario {target} asignado como {state['role']}." if done else "❌ No se puede cambiar el rol de un propietario.")
    elif flow == "respond_number":
        try:
            target_message = list(recent_messages)[int(text) - 1]
        except (ValueError, IndexError):
            await message.reply_text("Escribe un número válido o /cancelar.")
            return
        admin_states[user.id] = {"flow": "respond_text", "target": target_message}
        await message.reply_text("Escribe el texto de respuesta. /cancelar para salir.")
    elif flow == "respond_text":
        target_message = state["target"]
        admin_states.pop(user.id, None)
        await context.bot.send_message(GROUP_ID, f"🛠️ <b>Respuesta de administración</b> para {mention(target_message.from_user)}\n\n{esc(text)}", parse_mode=ParseMode.HTML, reply_to_message_id=target_message.message_id)
        await message.reply_text("✅ Respuesta enviada.")
    elif flow == "ticket":
        admin_states.pop(user.id, None)
        await create_ticket(update, text, context)
    elif flow == "appeal":
        admin_states.pop(user.id, None)
        await submit_appeal(update, context, text)
    elif flow == "ticket_reply":
        admin_states.pop(user.id, None)
        ticket = (await store.load("tickets.json")).get(state["ticket_id"])
        if not ticket or ticket.get("admin_id") != user.id or ticket.get("status") != "en_proceso":
            await message.reply_text("ℹ️ Ese ticket ya no está asignado a ti.")
            return
        try:
            await context.bot.send_message(ticket["user_id"], f"🛠️ <b>Respuesta del equipo (ticket #{state['ticket_id']})</b>\n\n{esc(text)}", parse_mode=ParseMode.HTML)
        except TelegramError:
            await message.reply_text("❌ No pude entregar la respuesta: el usuario no ha iniciado el bot o lo bloqueó.")
            return
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Responder otra vez", callback_data=f"reptk:{state['ticket_id']}"), InlineKeyboardButton("✅ Cerrar ticket", callback_data=f"cerrar:{state['ticket_id']}")]])
        await message.reply_text("✅ Respuesta enviada.", reply_markup=keyboard)


async def interactive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not message or not user or not chat:
        return
    if chat.type == "private":
        await handle_private_flow(update, context)
        return
    if not group_message(update):
        return
    exempt = await is_exempt(context, message)
    if (await store.load("settings.json")).get("maintenance") and not exempt:
        try:
            await message.delete()
        except TelegramError:
            LOG.debug("No se pudo borrar mensaje en mantenimiento", exc_info=True)
        return
    recent_messages.append(message)
    if await moderate_words(update, context) or await process_link(update, context):
        return
    if await automatic_reply(update, context):
        return
    if TRANSLATE_ENABLED and not exempt and message.text:
        context.application.create_task(translate_and_reply(message))


async def media_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not message or not user or not chat:
        return
    if chat.type == "private":
        state = admin_states.get(user.id)
        if state and state.get("flow") == "announcement" and await has_permission(user.id, "announce"):
            admin_states.pop(user.id, None)
            try:
                await context.bot.copy_message(GROUP_ID, chat.id, message.message_id)
                await message.reply_text("✅ Multimedia enviada correctamente al grupo.")
            except TelegramError as exc:
                await message.reply_text(f"❌ No se pudo enviar al grupo: {esc(exc)}")
        return
    if not group_message(update):
        return
    exempt = await is_exempt(context, message)
    if (await store.load("settings.json")).get("maintenance") and not exempt:
        try:
            await message.delete()
        except TelegramError:
            LOG.debug("No se pudo borrar mensaje en mantenimiento", exc_info=True)
        return
    recent_messages.append(message)
    if await moderate_words(update, context):
        return
    await media_moderation(update, context)


async def post_init(application: Application) -> None:
    await refresh_admins()
    public_commands = [
        BotCommand("start", "🚀 Iniciar el bot"), BotCommand("help", "❓ Ver ayuda y comandos"), BotCommand("reglas", "📜 Ver reglas de GAMAER CITY"),
        BotCommand("servidor", "🎮 Ver la IP del servidor"), BotCommand("enlaces", "🔗 Ver enlaces oficiales"), BotCommand("devblog", "📰 Ver último devblog"),
        BotCommand("wipe", "🧨 Ver próximo wipe"), BotCommand("wipes", "📅 Ver calendario de wipes"), BotCommand("soporte", "🎫 Abrir ticket"),
        BotCommand("apelar", "⚖️ Apelar una sanción"), BotCommand("reportar", "🚨 Reportar un usuario"), BotCommand("eventos", "📅 Ver eventos"),
        BotCommand("sorteos", "🎁 Ver sorteos"), BotCommand("encuestas", "📊 Ver encuestas activas"), BotCommand("cancelar", "❌ Cancelar flujo actual"),
    ]
    admin_commands = public_commands + [
        BotCommand("panel", "🛠️ Abrir panel administrativo"), BotCommand("anuncio", "📢 Crear anuncio"), BotCommand("pendientes", "🔎 Revisar enlaces pendientes"),
        BotCommand("tickets", "🎫 Gestionar tickets"), BotCommand("responder", "💬 Responder mensaje"), BotCommand("moderacion", "🛡️ Activar o desactivar moderación"),
        BotCommand("filtro", "🚫 Gestionar filtro de palabras"), BotCommand("auto", "🤖 Gestionar respuestas automáticas"), BotCommand("setreglas", "📜 Cambiar reglas"),
        BotCommand("setservidor", "🎮 Cambiar IP del servidor"), BotCommand("setenlaces", "🔗 Configurar enlaces oficiales"), BotCommand("setwipe", "🧨 Configurar wipe"),
        BotCommand("mantenimiento", "🔧 Activar modo mantenimiento"), BotCommand("fijar", "📌 Fijar mensaje oficial"), BotCommand("rol", "👤 Asignar rol"),
        BotCommand("evento", "📅 Crear o cancelar evento"), BotCommand("sorteo", "🎁 Crear o cerrar sorteo"), BotCommand("encuesta", "📊 Crear encuesta"),
        BotCommand("cerrar_encuesta", "🔒 Cerrar encuesta"), BotCommand("testgrupo", "🔧 Probar envío al grupo"),
        BotCommand("addadmin", "👮 Añadir administrador"), BotCommand("admin", "👮 Asignar administrador por ID"), BotCommand("mod", "🛡️ Asignar moderador por ID"), BotCommand("support", "🎫 Asignar soporte por ID"), BotCommand("announcer", "📢 Asignar anunciante por ID"), BotCommand("deladmin", "❌ Eliminar administrador"), BotCommand("listadmins", "👥 Listar administradores"),
        BotCommand("ban", "🔨 Banear usuario"), BotCommand("kick", "🚪 Expulsar usuario"), BotCommand("mute", "🔇 Silenciar usuario"),
        BotCommand("unmute", "🔊 Quitar silencio"), BotCommand("warn", "⚠️ Advertir usuario"), BotCommand("claimadmin", "🔑 Reclamar acceso inicial"),
    ]
    # Los comandos de administración solo se muestran a cada miembro del equipo; la autorización se vuelve a comprobar al ejecutar.
    await application.bot.set_my_commands(public_commands, scope=BotCommandScopeAllPrivateChats())
    await application.bot.set_my_commands(public_commands, scope=BotCommandScopeAllGroupChats())
    for admin_id in sorted(admins | ({BOT_OWNER_ID} if BOT_OWNER_ID else set())):
        try:
            await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except TelegramError:
            LOG.info("No se pudo registrar el menú de comandos para %s (¿aún no inició el bot?)", admin_id)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    application.job_queue.run_repeating(guarded_job(automation_tick), interval=60, first=10, name="rust133-automation")
    LOG.info("Bot iniciado con admins %s y grupo %s", sorted(admins), GROUP_ID)


ALLOWED_UPDATES = [UpdateType.MESSAGE, UpdateType.EDITED_MESSAGE, UpdateType.CALLBACK_QUERY, UpdateType.CHAT_MEMBER]

COMMANDS: list[tuple[Any, Any]] = [
    ("start", start_cmd), ("claimadmin", claim_admin_cmd), (["help", "ayuda"], help_cmd), ("reglas", rules_cmd), ("devblog", devblog_cmd),
    ("servidor", server_cmd), ("enlaces", official_links_cmd), (["wipe", "wipes"], wipe_cmd), ("soporte", soporte_cmd), ("apelar", appeal_cmd),
    ("reportar", report_cmd), ("cancelar", cancel_cmd), ("testgrupo", test_group_cmd), (["addadmin", "deladmin", "listadmins"], admins_cmd),
    (["admin", "mod", "support", "announcer"], role_alias_cmd), ("anuncio", announcement_cmd), ("moderacion", moderation_cmd),
    ("mantenimiento", maintenance_cmd), ("panel", panel_cmd), ("fijar", pin_cmd), ("rol", roles_cmd), (["evento", "eventos"], events_cmd),
    (["sorteo", "sorteos"], giveaway_cmd), ("setenlaces", set_links_cmd), ("setservidor", setserver_cmd), ("filtro", filter_cmd),
    ("auto", auto_reply_cmd), (["ban", "kick", "mute", "unmute", "warn"], moderate_user), ("pendientes", pending_cmd),
    ("setreglas", setrules_cmd), ("setwipe", setwipe_cmd), ("tickets", tickets_cmd), ("responder", responder_cmd),
    ("encuesta", encuesta_cmd), ("encuestas", encuestas_cmd), ("cerrar_encuesta", cerrar_encuesta_cmd),
]
CALLBACKS: list[tuple[Any, str]] = [
    (link_callback, r"^(validar|expulsar):"), (ticket_callback, r"^(atender|cerrar|reptk):"), (poll_callback, r"^voto:"),
    (verify_callback, r"^verify:"), (public_nav_callback, r"^nav:"), (panel_callback, r"^panel:"), (giveaway_callback, r"^giveaway:"),
    (appeal_callback, r"^appeal:"), (moderation_confirmation_callback, r"^(confirmmod|cancelmod):"),
]


def build_app() -> Application:
    if not valid_token() or not GROUP_ID:
        raise RuntimeError("Configura TELEGRAM_TOKEN y GROUP_ID (en .env o en el entorno)")
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    for names, handler in COMMANDS:
        app.add_handler(CommandHandler(names, guarded(handler)))
    for handler, pattern in CALLBACKS:
        app.add_handler(CallbackQueryHandler(guarded(handler), pattern=pattern))
    app.add_handler(ChatMemberHandler(guarded(new_member), ChatMemberHandler.CHAT_MEMBER))
    in_group, in_private = filters.Chat(GROUP_ID), filters.ChatType.PRIVATE
    app.add_handler(MessageHandler(filters.COMMAND, guarded(reset_flow_on_command)), group=-1)
    app.add_handler(MessageHandler(in_group & filters.TEXT & ~filters.COMMAND, guarded(interactive_text)))
    app.add_handler(MessageHandler(in_group & ~filters.TEXT & ~filters.COMMAND & ~filters.StatusUpdate.ALL, guarded(media_router)))
    app.add_handler(MessageHandler(in_private & filters.TEXT & ~filters.COMMAND, guarded(interactive_text)))
    app.add_handler(MessageHandler(in_private & ~filters.TEXT & ~filters.COMMAND, guarded(media_router)))
    app.add_error_handler(error_handler)
    return app


def main() -> None:
    require_env()
    if not valid_token():
        raise SystemExit("TELEGRAM_TOKEN no configurado o inválido")
    build_app().run_polling(allowed_updates=ALLOWED_UPDATES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
