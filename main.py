#!/usr/bin/env python3
"""Bot de moderación y anuncios para la comunidad Rust 133 Devblog.

El bot debe ser administrador del grupo con permisos para borrar mensajes,
restringir usuarios y fijar mensajes. Para leer todos los mensajes, desactiva
el Privacy Mode de BotFather.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import sqlite3
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Iterable

import telebot
from telebot import types

LOG = logging.getLogger("rust133bot")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
DB_FILE = os.getenv("DB_FILE", "bot.db")
GROUP_ID = int(os.getenv("GROUP_ID", "0") or 0)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().lstrip("-").isdigit()}
if ADMIN_ID:
    ADMIN_IDS.add(ADMIN_ID)
ALLOWED_DOMAINS = {d.strip().lower().lstrip("www.") for d in os.getenv("ALLOWED_DOMAINS", "rust.facepunch.com,facepunch.com,store.steampowered.com,steamcommunity.com").split(",") if d.strip()}
TRANSLATION_ENABLED = os.getenv("TRANSLATION_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_LINKS = 20
URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>]+")
SHORTENER_DOMAINS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "cutt.ly", "is.gd", "rb.gy"}

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML", threaded=True)
_db_lock = threading.RLock()
_admin_drafts: dict[int, str] = {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=False)


def validate_runtime_config() -> None:
    if not TELEGRAM_TOKEN or not re.fullmatch(r"\d{6,12}:[A-Za-z0-9_-]{20,}", TELEGRAM_TOKEN):
        raise RuntimeError("TELEGRAM_TOKEN no está configurado o no parece válido")
    if not ADMIN_IDS:
        raise RuntimeError("Configura ADMIN_ID o ADMIN_IDS con al menos un administrador")
    if not GROUP_ID:
        LOG.warning("GROUP_ID no está configurado: el bot podrá iniciar, pero no moderará ningún grupo")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=20000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _db_lock, db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS link_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL, username TEXT, url TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL, reviewed_at TEXT, reviewed_by INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_link_events_status ON link_events(status, id DESC);
        CREATE TABLE IF NOT EXISTS moderation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, admin_id INTEGER,
            target_id INTEGER, chat_id INTEGER, details TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS warnings (
            chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(chat_id, user_id)
        );
        """)
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('link_mode','review')")
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('rules',?)", (default_rules(),))


def default_rules() -> str:
    return ("📜 <b>Reglas de Rust 133 Devblog</b>\n\n"
            "1. Respeta a la comunidad y al equipo de moderación.\n"
            "2. No spam, flood, estafas, phishing ni enlaces sospechosos.\n"
            "3. No publiques invitaciones a otros servidores sin autorización.\n"
            "4. Las fotos, vídeos y archivos deben estar relacionados con Rust.\n"
            "5. No compartas datos personales ni contenido ilegal.\n"
            "6. Los moderadores pueden borrar contenido y expulsar cuentas.\n\n"
            "Usa /ayuda para ver los comandos disponibles.")


def setting(key: str, fallback: str = "") -> str:
    with _db_lock, db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else fallback


def set_setting(key: str, value: str) -> None:
    with _db_lock, db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))


def log_action(action: str, admin_id: int | None, target_id: int | None = None, chat_id: int | None = None, details: str = "") -> None:
    with _db_lock, db() as conn:
        conn.execute("INSERT INTO moderation_logs(action,admin_id,target_id,chat_id,details,created_at) VALUES(?,?,?,?,?,?)",
                     (action, admin_id, target_id, chat_id, details[:1000], now()))


def is_admin(user_id: int | None) -> bool:
    return bool(user_id and user_id in ADMIN_IDS)


def is_group(message: types.Message) -> bool:
    return message.chat.type in {"group", "supergroup"}


def user_label(user: types.User | None) -> str:
    if not user:
        return "usuario"
    return f"{esc(user.first_name or '')} (@{esc(user.username)})" if user.username else esc(user.first_name or user.id)


def message_text(message: types.Message) -> str:
    return (message.text or message.caption or "").strip()


def urls_in(message: types.Message) -> list[str]:
    return URL_RE.findall(message_text(message))[:MAX_LINKS]


def hostname(url: str) -> str:
    value = re.sub(r"(?i)^https?://", "", url).split("/", 1)[0].split("?", 1)[0].split(":", 1)[0].lower().lstrip("www.")
    return value


def link_is_allowed(url: str) -> bool:
    host = hostname(url)
    return any(host == domain or host.endswith("." + domain) for domain in ALLOWED_DOMAINS)


def suspicious_url(url: str) -> bool:
    host = hostname(url)
    return host in SHORTENER_DOMAINS or not link_is_allowed(url)


def link_mode() -> str:
    current = setting("link_mode", "review")
    return current if current in {"off", "review", "auto"} else "review"


def record_link(message: types.Message, url: str) -> int:
    with _db_lock, db() as conn:
        cur = conn.execute("INSERT INTO link_events(chat_id,message_id,user_id,username,url,status,created_at) VALUES(?,?,?,?,?,?,?)",
                           (message.chat.id, message.message_id, message.from_user.id, message.from_user.username, url, "pending", now()))
        return int(cur.lastrowid)


def review_keyboard(event_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("🚫 Expulsar", callback_data=f"linkban:{event_id}"),
           types.InlineKeyboardButton("✅ No hacer nada", callback_data=f"linkignore:{event_id}"))
    return kb


def notify_link_review(message: types.Message, event_id: int, url: str) -> None:
    text = (f"🔎 <b>Enlace pendiente de revisión</b> #{event_id}\n"
            f"Usuario: {user_label(message.from_user)} (<code>{message.from_user.id}</code>)\n"
            f"URL: <code>{esc(url)}</code>\nGrupo: <code>{message.chat.id}</code>")
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, text, reply_markup=review_keyboard(event_id))
        except Exception as exc:
            LOG.warning("No se pudo avisar al admin %s: %s", admin_id, exc)


def ban_user(chat_id: int, user_id: int, admin_id: int, reason: str = "Regla de enlaces") -> bool:
    try:
        bot.ban_chat_member(chat_id, user_id)
        log_action("ban", admin_id, user_id, chat_id, reason)
        return True
    except Exception as exc:
        LOG.warning("No se pudo expulsar a %s: %s", user_id, exc)
        return False


def moderate_links(message: types.Message) -> bool:
    if not is_group(message) or is_admin(message.from_user.id) or not message.from_user:
        return False
    links = [url for url in urls_in(message) if suspicious_url(url)]
    if not links:
        return False
    mode = link_mode()
    if mode == "off":
        return False
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception as exc:
        LOG.warning("No se pudo borrar mensaje con enlace: %s", exc)
    event_id = record_link(message, links[0])
    if mode == "auto":
        ban_user(message.chat.id, message.from_user.id, 0, f"Enlace no permitido: {links[0]}")
        return True
    notify_link_review(message, event_id, links[0])
    try:
        bot.send_message(message.chat.id, "⚠️ El mensaje fue retirado por contener un enlace no autorizado. Un moderador revisará el caso.")
    except Exception:
        pass
    return True


def probably_spanish(text: str) -> bool:
    lower = " " + text.lower() + " "
    markers = (" el ", " la ", " los ", " las ", " que ", " una ", " para ", " con ", " por ", " de ", " del ", " español")
    return any(marker in lower for marker in markers) or bool(re.search(r"[áéíóúñ¿¡]", text.lower()))


def translate_to_spanish(text: str) -> str | None:
    if not TRANSLATION_ENABLED or not GEMINI_API_KEY or not text or probably_spanish(text):
        return None
    prompt = ("Traduce al español el siguiente mensaje de una comunidad de Rust. "
              "Devuelve únicamente la traducción, conserva URLs, nombres propios y formato.\n\n" + text[:3500])
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode())
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()[:4000]
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
        LOG.warning("Traducción no disponible: %s", exc)
        return None


def send_translation(message: types.Message) -> None:
    if not is_group(message) or not message.text or message.text.startswith("/") or is_admin(message.from_user.id):
        return
    translated = translate_to_spanish(message.text)
    if translated and translated.casefold() != message.text.casefold():
        try:
            bot.reply_to(message, f"🌐 <b>Traducción al español</b>\n{esc(translated)}")
        except Exception as exc:
            LOG.warning("No se pudo publicar traducción: %s", exc)


def require_admin(message: types.Message) -> bool:
    if message.chat.type != "private" or not is_admin(message.from_user.id):
        if message.chat.type == "private":
            bot.reply_to(message, "🔒 Este comando solo está disponible para administradores autorizados.")
        return False
    return True


def announcement_target() -> int:
    if not GROUP_ID:
        raise RuntimeError("GROUP_ID no está configurado")
    return GROUP_ID


def send_announcement(message: types.Message, text: str | None = None) -> None:
    target = announcement_target()
    source = message.reply_to_message
    if source:
        bot.copy_message(target, message.chat.id, source.message_id)
    elif text:
        bot.send_message(target, f"📢 <b>Anuncio de Rust 133 Devblog</b>\n\n{esc(text)}", disable_web_page_preview=False)
    else:
        raise ValueError("Escribe el anuncio o responde a un mensaje multimedia con /anuncio")


@bot.message_handler(commands=["start", "ayuda", "help"])
def cmd_help(message: types.Message) -> None:
    if message.chat.type == "private" and is_admin(message.from_user.id):
        bot.reply_to(message, "<b>Panel de administración</b>\n\n"
                     "/anuncio texto — publicar texto\n"
                     "/anuncio respondiendo a foto/archivo — copiar multimedia\n"
                     "/wipe texto — anunciar wipe\n"
                     "/links — enlaces pendientes\n"
                     "/enlaces off|review|auto — política de enlaces\n"
                     "/permitir dominio.com — añadir dominio permitido\n"
                     "/reglas — ver reglas\n"
                     "/setreglas texto — cambiar reglas\n"
                     "/ban ID — expulsar usuario\n/unban ID — quitar baneo\n/warn ID motivo — advertir\n"
                     "/estado — estado de configuración")
    else:
        bot.reply_to(message, "🤖 <b>Rust 133 Devblog</b>\n\n" + setting("rules", default_rules()))


@bot.message_handler(commands=["anuncio"])
def cmd_announcement(message: types.Message) -> None:
    if not require_admin(message):
        return
    text = message_text(message)[len("/anuncio"):].strip()
    try:
        send_announcement(message, text or None)
        bot.reply_to(message, "✅ Anuncio enviado al grupo.")
        log_action("announcement", message.from_user.id, chat_id=GROUP_ID, details=text[:500])
    except Exception as exc:
        bot.reply_to(message, f"❌ No se pudo enviar: {esc(exc)}")


@bot.message_handler(commands=["wipe"])
def cmd_wipe(message: types.Message) -> None:
    if not require_admin(message):
        return
    text = message_text(message)[len("/wipe"):].strip()
    if not text:
        bot.reply_to(message, "Uso: /wipe <fecha, hora y detalles>")
        return
    send_announcement(message, f"🧹 <b>AVISO DE WIPE</b>\n\n{esc(text)}")
    bot.reply_to(message, "✅ Aviso de wipe enviado.")


@bot.message_handler(commands=["reglas"])
def cmd_rules(message: types.Message) -> None:
    if message.chat.type == "private" and not is_admin(message.from_user.id):
        return
    bot.reply_to(message, setting("rules", default_rules()))


@bot.message_handler(commands=["setreglas"])
def cmd_set_rules(message: types.Message) -> None:
    if not require_admin(message):
        return
    text = message_text(message)[len("/setreglas"):].strip()
    if not text or len(text) > 3500:
        bot.reply_to(message, "Uso: /setreglas <texto de reglas, máximo 3500 caracteres>")
        return
    set_setting("rules", esc(text))
    bot.reply_to(message, "✅ Reglas actualizadas.")


@bot.message_handler(commands=["enlaces"])
def cmd_links_policy(message: types.Message) -> None:
    if not require_admin(message):
        return
    value = message_text(message)[len("/enlaces"):].strip().lower()
    if value not in {"off", "review", "auto"}:
        bot.reply_to(message, f"Política actual: <b>{link_mode()}</b>. Usa off, review o auto.")
        return
    set_setting("link_mode", value)
    bot.reply_to(message, f"✅ Política de enlaces: <b>{value}</b>")


@bot.message_handler(commands=["permitir"])
def cmd_allow_domain(message: types.Message) -> None:
    if not require_admin(message):
        return
    domain = message_text(message)[len("/permitir"):].strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain):
        bot.reply_to(message, "Uso: /permitir dominio.com")
        return
    ALLOWED_DOMAINS.add(domain.lstrip("www."))
    bot.reply_to(message, f"✅ Dominio permitido: <code>{esc(domain)}</code>")


@bot.message_handler(commands=["links"])
def cmd_pending_links(message: types.Message) -> None:
    if not require_admin(message):
        return
    with _db_lock, db() as conn:
        rows = conn.execute("SELECT id,username,url,created_at FROM link_events WHERE status='pending' ORDER BY id DESC LIMIT 15").fetchall()
    if not rows:
        bot.reply_to(message, "✅ No hay enlaces pendientes.")
        return
    for row in rows:
        bot.send_message(message.chat.id, f"#{row['id']} @{esc(row['username'] or 'sin_usuario')} · <code>{esc(row['url'])}</code>\n{row['created_at']}", reply_markup=review_keyboard(row["id"]))


@bot.message_handler(commands=["ban", "unban", "warn"])
def cmd_moderation(message: types.Message) -> None:
    if not require_admin(message):
        return
    parts = message_text(message).split(maxsplit=2)
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit() or not GROUP_ID:
        bot.reply_to(message, "Uso: /ban ID, /unban ID o /warn ID motivo")
        return
    target = int(parts[1])
    action = parts[0].split("@")[0][1:]
    try:
        if action == "ban":
            ok = ban_user(GROUP_ID, target, message.from_user.id, "Expulsión manual")
            bot.reply_to(message, "✅ Usuario expulsado." if ok else "❌ Telegram rechazó la expulsión.")
        elif action == "unban":
            bot.unban_chat_member(GROUP_ID, target, only_if_banned=True)
            log_action("unban", message.from_user.id, target, GROUP_ID)
            bot.reply_to(message, "✅ Baneo retirado.")
        else:
            reason = parts[2] if len(parts) > 2 else "Sin motivo"
            with _db_lock, db() as conn:
                conn.execute("INSERT INTO warnings(chat_id,user_id,count) VALUES(?,?,1) ON CONFLICT(chat_id,user_id) DO UPDATE SET count=count+1", (GROUP_ID, target))
            log_action("warn", message.from_user.id, target, GROUP_ID, reason)
            bot.reply_to(message, f"✅ Advertencia registrada para <code>{target}</code>.")
    except Exception as exc:
        bot.reply_to(message, f"❌ Error: {esc(exc)}")


@bot.message_handler(commands=["estado"])
def cmd_status(message: types.Message) -> None:
    if not require_admin(message):
        return
    with _db_lock, db() as conn:
        pending = conn.execute("SELECT COUNT(*) AS n FROM link_events WHERE status='pending'").fetchone()["n"]
    bot.reply_to(message, f"<b>Estado</b>\nGrupo: <code>{GROUP_ID or 'no configurado'}</code>\n"
                 f"Política enlaces: <b>{link_mode()}</b>\nPendientes: <b>{pending}</b>\n"
                 f"Traducción: <b>{'activa' if TRANSLATION_ENABLED and GEMINI_API_KEY else 'inactiva'}</b>")


@bot.callback_query_handler(func=lambda call: call.data.startswith(("linkban:", "linkignore:")))
def callback_link_review(call: types.CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Solo un administrador puede revisar esto", show_alert=True)
        return
    action, raw_id = call.data.split(":", 1)
    if not raw_id.isdigit():
        return
    event_id = int(raw_id)
    with _db_lock, db() as conn:
        row = conn.execute("SELECT * FROM link_events WHERE id=? AND status='pending'", (event_id,)).fetchone()
        if not row:
            bot.answer_callback_query(call.id, "Ya revisado")
            return
        status = "banned" if action == "linkban" else "ignored"
        conn.execute("UPDATE link_events SET status=?,reviewed_at=?,reviewed_by=? WHERE id=?", (status, now(), call.from_user.id, event_id))
    if action == "linkban":
        ok = ban_user(row["chat_id"], row["user_id"], call.from_user.id, f"Enlace revisado: {row['url']}")
        result = "expulsado" if ok else "no se pudo expulsar"
    else:
        result = "sin sanción"
        log_action("link_ignore", call.from_user.id, row["user_id"], row["chat_id"], row["url"])
    bot.answer_callback_query(call.id, f"Usuario {result}")
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(call.message.chat.id, f"✅ Caso #{event_id}: usuario {result}.")
    except Exception:
        pass


@bot.message_handler(content_types=["text", "photo", "video", "document", "audio", "animation", "voice",
                                    "sticker", "contact", "location", "venue", "poll"])
def group_message(message: types.Message) -> None:
    if not is_group(message):
        if message.chat.type == "private" and is_admin(message.from_user.id) and message.content_type != "text":
            caption = message.caption or ""
            if caption.startswith("/anuncio"):
                try:
                    bot.copy_message(announcement_target(), message.chat.id, message.message_id)
                    bot.reply_to(message, "✅ Multimedia anunciada en el grupo.")
                except Exception as exc:
                    bot.reply_to(message, f"❌ No se pudo anunciar: {esc(exc)}")
        return
    if moderate_links(message):
        return
    send_translation(message)


def main() -> None:
    validate_runtime_config()
    init_db()
    LOG.info("Bot Rust 133 Devblog iniciado; grupo=%s; admins=%s", GROUP_ID or "no configurado", sorted(ADMIN_IDS))
    bot.infinity_polling(skip_pending=True, allowed_updates=["message", "callback_query", "my_chat_member"])


if __name__ == "__main__":
    main()
