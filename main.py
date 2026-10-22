#!/usr/bin/env python3
"""
OnlyFans_ManagerBot - V6
- Chat privado: registro, verificación, pagos, contenido
- Grupo privado: comunidad con roles (normal / VIP / creador / admin)
- Comandos diferenciados + cooldown 30 min para promocionar
- Anuncios, soporte, invitaciones, silenciar grupo, etc.
- Multilingüe (prioridad español)
"""

import telebot
from telebot import types
import sqlite3
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict

# ==================== CONFIGURACIÓN ====================
TELEGRAM_TOKEN = "PON_AQUI_TU_TOKEN"
ADMIN_ID = 7653419875

GROUP_ID = None                               # -100xxxxxxxxxx  (pon el ID real)
GROUP_INVITE = "https://t.me/+oMkBHSWhjf5lNTZh"
PRIVATE_CHANNEL_ID = None                     # -100yyyyyyyyyy

CREATOR_FEE = 50.0
PROMO_COOLDOWN_MINUTES = 30                   # Límite para /promo
WEBAPP_VERIFICATION_URL = "https://TU_DOMINIO.com/verification.html"

DB_FILE = "bot.db"
bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")

# Memoria temporal para cooldowns y mute
promo_cooldown = {}          # user_id -> timestamp
group_muted = False          # Silencio global del grupo

# ==================== TEXTOS (prioridad ES) ====================
TEXTS = {
    "es": {
        "welcome": "💖 <b>Bienvenido/a, {name}</b>\n\nPlataforma de contenido exclusivo.\nElige una opción:",
        "age_title": "🔒 <b>Confirmación de Edad</b>",
        "age_text": "Este bot contiene contenido para adultos.\n\n¿Confirmas que eres <b>mayor de 18 años</b>?\n\n<i>La verificación real se hace después con la cámara.</i>",
        "age_yes": "✅ Sí, soy mayor de 18",
        "age_no": "❌ Soy menor",
        "age_denied": "🚫 Este servicio es solo para mayores de 18 años.",
        "terms_accept": "✅ Acepto",
        "terms_deny": "❌ No acepto",
        "terms_must": "Debes aceptar los términos para continuar.",
        "menu_explore": "🔍 Explorar Creadores",
        "menu_subs": "📋 Mis Suscripciones",
        "menu_account": "👤 Mi Cuenta",
        "menu_help": "❓ Ayuda",
        "menu_creator": "🎨 Panel Creador",
        "menu_admin": "🔧 Panel Admin",
        "back": "« Volver",
        "back_menu": "« Menú",
        "must_pay": "🔒 <b>Debes pagar para ver el contenido</b>",
        "has_sub": "✅ <b>Tienes suscripción activa</b>",
        "view_content": "📥 Ver contenido",
        "cancel_sub": "❌ Cancelar suscripción",
        "report": "📢 Reportar",
        "request_verif": "📸 Verificación con cámara",
        "verif_pending": "Ya tienes una verificación pendiente",
        "verif_done": "Ya estás verificado",
        "banned": "🚫 Tu cuenta está baneada.",
        "no_creators": "Aún no hay creadores verificados.",
        "group_welcome": "👋 Bienvenido/a al grupo, {name}!\n\nEscribe /ayuda para ver los comandos.\nRegístrate en privado con /start.",
        "use_private": "⚠️ Este comando se usa en <b>chat privado</b> conmigo.",
        "only_vip": "👑 Este comando es solo para usuarios <b>VIP</b> (con suscripción activa).",
        "only_admin": "🔒 Solo administradores pueden usar este comando.",
        "only_creator": "🎨 Solo creadores verificados pueden usar este comando.",
        "group_muted": "🔇 El grupo está en silencio. Solo admins pueden hablar.",
        "help_text": (
            "❓ <b>Ayuda (privado)</b>\n\n"
            "• Solo puedes ver contenido con <b>suscripción pagada</b>.\n"
            "• Usa la <b>verificación con cámara</b> para badges.\n"
            "• Para ser Creador paga 50$ y espera aprobación."
        ),
    },
    "en": {
        "welcome": "💖 <b>Welcome, {name}</b>\n\nExclusive content platform.\nChoose an option:",
        "age_title": "🔒 <b>Age Confirmation</b>",
        "age_text": "This bot contains adult content.\n\nDo you confirm you are <b>over 18</b>?",
        "age_yes": "✅ Yes, I am over 18",
        "age_no": "❌ I am underage",
        "age_denied": "🚫 Adults only.",
        "terms_accept": "✅ I accept",
        "terms_deny": "❌ I do not accept",
        "terms_must": "You must accept the terms.",
        "menu_explore": "🔍 Explore Creators",
        "menu_subs": "📋 My Subscriptions",
        "menu_account": "👤 My Account",
        "menu_help": "❓ Help",
        "menu_creator": "🎨 Creator Panel",
        "menu_admin": "🔧 Admin Panel",
        "back": "« Back",
        "back_menu": "« Menu",
        "must_pay": "🔒 <b>You must pay to view content</b>",
        "has_sub": "✅ <b>Active subscription</b>",
        "view_content": "📥 View content",
        "cancel_sub": "❌ Cancel subscription",
        "report": "📢 Report",
        "request_verif": "📸 Camera verification",
        "verif_pending": "Verification pending",
        "verif_done": "Already verified",
        "banned": "🚫 Banned.",
        "no_creators": "No creators yet.",
        "group_welcome": "👋 Welcome to the group, {name}!\n\nType /help for commands.\nRegister in private with /start.",
        "use_private": "⚠️ Use this in <b>private chat</b>.",
        "only_vip": "👑 VIP only (active subscription).",
        "only_admin": "🔒 Admins only.",
        "only_creator": "🎨 Creators only.",
        "group_muted": "🔇 Group is muted. Admins only.",
        "help_text": "❓ <b>Help</b>\n\n• Paid subscription required for content.\n• Camera verification for badges.\n• Pay $50 to become Creator.",
    }
}

def get_lang(user_id=None, tg_user=None):
    if tg_user and getattr(tg_user, "language_code", None):
        return "es" if tg_user.language_code.lower().startswith("es") else "en"
    if user_id:
        u = get_user(user_id)
        if u and u["language"] in ("es", "en"):
            return u["language"]
    return "es"

def t(key, lang="es", **kwargs):
    text = TEXTS.get(lang, TEXTS["es"]).get(key, TEXTS["es"].get(key, key))
    try:
        return text.format(**kwargs) if kwargs else text
    except:
        return text

# ==================== BASE DE DATOS ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        role TEXT DEFAULT 'user', language TEXT DEFAULT 'es',
        age_declared INTEGER DEFAULT 0, terms_accepted INTEGER DEFAULT 0,
        age_verified_real INTEGER DEFAULT 0, gender TEXT, gender_verified INTEGER DEFAULT 0,
        creator_verified INTEGER DEFAULT 0, banned INTEGER DEFAULT 0, ban_reason TEXT,
        joined_at TEXT, last_active TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS creators (
        user_id INTEGER PRIMARY KEY, display_name TEXT, bio TEXT,
        monthly_price REAL DEFAULT 9.99, quarterly_price REAL DEFAULT 24.99,
        private_channel_id INTEGER, invite_link TEXT,
        total_subscribers INTEGER DEFAULT 0, total_earnings REAL DEFAULT 0,
        created_at TEXT, FOREIGN KEY(user_id) REFERENCES users(user_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, creator_id INTEGER,
        plan TEXT, amount REAL, status TEXT DEFAULT 'active',
        start_date TEXT, end_date TEXT, payment_method TEXT, created_at TEXT,
        UNIQUE(user_id, creator_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS content (
        id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id INTEGER, title TEXT,
        description TEXT, file_ids TEXT, media_types TEXT,
        is_premium INTEGER DEFAULT 1, views INTEGER DEFAULT 0, created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, creator_id INTEGER,
        type TEXT, amount REAL, currency TEXT DEFAULT 'USD', status TEXT DEFAULT 'pending',
        payment_method TEXT, screenshot_file_id TEXT, reference TEXT,
        created_at TEXT, reviewed_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        doc_photo_id TEXT, selfie_photo_id TEXT, status TEXT DEFAULT 'pending',
        assigned_gender TEXT, source TEXT DEFAULT 'manual',
        created_at TEXT, reviewed_at TEXT, reviewed_by INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER, reported_id INTEGER,
        reason TEXT, details TEXT, status TEXT DEFAULT 'open', created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, action TEXT,
        target_id INTEGER, details TEXT, created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS cooldowns (
        user_id INTEGER, command TEXT, last_used TEXT,
        PRIMARY KEY (user_id, command)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS group_settings (
        key TEXT PRIMARY KEY, value TEXT
    )""")

    # Defaults
    defaults = {
        "payment_methods": (
            "💳 <b>Formas de pago:</b>\n\n"
            "• Transferencia / Bizum\n"
            "• Crypto (USDT TRC20 / BTC)\n"
            "• Telegram Stars\n\n"
            "<i>El admin actualizará los datos exactos.</i>"
        ),
        "terms": (
            "📜 <b>Términos y Condiciones</b>\n\n"
            "1. Debes ser mayor de 18 años.\n"
            "2. Uso personal únicamente.\n"
            "3. Prohibida la redistribución.\n"
            "4. Ban por incumplimientos.\n"
            "5. Al continuar aceptas estos términos."
        ),
        "group_rules": (
            "📜 <b>Reglas del grupo</b>\n\n"
            "1. Respeta a todos los miembros.\n"
            "2. No spam ni contenido ilegal.\n"
            "3. Los VIP pueden promocionar cada 30 minutos.\n"
            "4. Usa /soporte para ayuda.\n"
            "5. El admin puede silenciar el grupo."
        ),
        "announcement": "📢 Bienvenidos a la comunidad. Usa /ayuda para ver los comandos."
    }
    for k, v in defaults.items():
        if not c.execute("SELECT 1 FROM settings WHERE key=?", (k,)).fetchone():
            c.execute("INSERT INTO settings VALUES (?, ?)", (k, v))

    if not c.execute("SELECT 1 FROM group_settings WHERE key='muted'").fetchone():
        c.execute("INSERT INTO group_settings VALUES ('muted', '0')")

    conn.commit()
    conn.close()
    ensure_admin()

def ensure_admin():
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("""INSERT OR IGNORE INTO users
        (user_id, role, age_declared, terms_accepted, age_verified_real, gender_verified, creator_verified, language, joined_at, last_active)
        VALUES (?, 'admin', 1, 1, 2, 1, 2, 'es', ?, ?)""", (ADMIN_ID, now, now))
    conn.execute("""UPDATE users SET role='admin', age_declared=1, terms_accepted=1,
        age_verified_real=2, gender_verified=1, creator_verified=2 WHERE user_id=?""", (ADMIN_ID,))
    conn.execute("""INSERT OR IGNORE INTO creators (user_id, display_name, bio, created_at)
        VALUES (?, 'Admin Principal', 'Creador principal', ?)""", (ADMIN_ID, now))
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_setting(key):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else ""

def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_group_setting(key):
    conn = get_db()
    row = conn.execute("SELECT value FROM group_settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None

def set_group_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO group_settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def log_admin(admin_id, action, target_id=None, details=""):
    conn = get_db()
    conn.execute("INSERT INTO admin_logs (admin_id, action, target_id, details, created_at) VALUES (?,?,?,?,?)",
                 (admin_id, action, target_id, details, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return u

def upsert_user(tg_user):
    conn = get_db()
    now = datetime.now().isoformat()
    lang = "es" if (tg_user.language_code or "").lower().startswith("es") else "en"
    conn.execute("""INSERT INTO users (user_id, username, first_name, language, joined_at, last_active)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username, first_name=excluded.first_name,
            language=excluded.language, last_active=excluded.last_active""",
                 (tg_user.id, tg_user.username, tg_user.first_name, lang, now, now))
    conn.commit()
    conn.close()

def is_admin(uid):
    return uid == ADMIN_ID

def is_banned(uid):
    u = get_user(uid)
    return u and u["banned"] == 1

def is_creator(uid):
    u = get_user(uid)
    return u and u["role"] in ("creator", "admin") and u["creator_verified"] == 2

def is_vip(uid):
    """VIP = tiene al menos 1 suscripción activa O es creador/admin"""
    if is_admin(uid) or is_creator(uid):
        return True
    conn = get_db()
    row = conn.execute("""SELECT 1 FROM subscriptions
        WHERE user_id=? AND status='active' AND end_date > ?""",
                       (uid, datetime.now().isoformat())).fetchone()
    conn.close()
    return bool(row)

def format_price(price):
    return f"${price:.2f}"

def has_active_sub(user_id, creator_id):
    conn = get_db()
    row = conn.execute("""SELECT 1 FROM subscriptions
        WHERE user_id=? AND creator_id=? AND status='active' AND end_date > ?""",
                       (user_id, creator_id, datetime.now().isoformat())).fetchone()
    conn.close()
    return bool(row)

def get_badges(user):
    badges = []
    if user and user["age_verified_real"] == 2:
        badges.append("🔞✅")
    if user and user["gender_verified"] == 1 and user["gender"]:
        badges.append("♂️" if user["gender"] == "male" else "♀️")
    if is_vip(user["user_id"] if user else 0):
        badges.append("👑")
    return " ".join(badges) if badges else ""

def get_gender_text(user, lang="es"):
    if not user or not user["gender_verified"]:
        return "No verificado" if lang == "es" else "Not verified"
    return ("Masculino" if lang == "es" else "Male") if user["gender"] == "male" else ("Femenino" if lang == "es" else "Female")

def is_private_chat(message):
    return message.chat.type == "private"

def is_our_group(message):
    if GROUP_ID is None:
        return message.chat.type in ("group", "supergroup")
    return message.chat.id == GROUP_ID

def check_cooldown(user_id, command, minutes=PROMO_COOLDOWN_MINUTES):
    conn = get_db()
    row = conn.execute("SELECT last_used FROM cooldowns WHERE user_id=? AND command=?",
                       (user_id, command)).fetchone()
    conn.close()
    if not row:
        return True, 0
    last = datetime.fromisoformat(row["last_used"])
    diff = (datetime.now() - last).total_seconds() / 60
    if diff >= minutes:
        return True, 0
    return False, int(minutes - diff)

def set_cooldown(user_id, command):
    conn = get_db()
    conn.execute("""INSERT OR REPLACE INTO cooldowns (user_id, command, last_used)
        VALUES (?, ?, ?)""", (user_id, command, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def is_group_muted():
    return get_group_setting("muted") == "1"

# ==================== MENÚ PRIVADO ====================
def main_menu_kb(user_id, lang):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(t("menu_explore", lang), callback_data="menu_explore"),
        types.InlineKeyboardButton(t("menu_subs", lang), callback_data="menu_subs")
    )
    kb.add(
        types.InlineKeyboardButton(t("menu_account", lang), callback_data="menu_account"),
        types.InlineKeyboardButton(t("menu_help", lang), callback_data="menu_help")
    )
    if is_creator(user_id):
        kb.add(types.InlineKeyboardButton(t("menu_creator", lang), callback_data="creator_panel"))
    if is_admin(user_id):
        kb.add(types.InlineKeyboardButton(t("menu_admin", lang), callback_data="admin_panel"))
    return kb

def send_main_menu(chat_id, user_id, message_id=None, lang=None):
    user = get_user(user_id)
    lang = lang or (user["language"] if user else "es")
    name = user["first_name"] if user else "User"
    text = t("welcome", lang, name=name)
    kb = main_menu_kb(user_id, lang)
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)

# ==================== START (PRIVADO) ====================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    if not is_private_chat(message):
        lang = get_lang(tg_user=message.from_user)
        bot.reply_to(message, t("use_private", lang))
        return
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, t("banned", get_lang(tg_user=message.from_user)))
        return
    upsert_user(message.from_user)
    user = get_user(message.from_user.id)
    lang = user["language"] or get_lang(tg_user=message.from_user)
    if not user["age_declared"]:
        ask_age_declaration(message.chat.id, lang)
        return
    if not user["terms_accepted"]:
        ask_terms(message.chat.id, lang)
        return
    send_main_menu(message.chat.id, message.from_user.id, lang=lang)

def ask_age_declaration(chat_id, lang="es"):
    text = f"{t('age_title', lang)}\n\n{t('age_text', lang)}"
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton(t("age_yes", lang), callback_data="age_yes"),
        types.InlineKeyboardButton(t("age_no", lang), callback_data="age_no")
    )
    bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ("age_yes", "age_no"))
def cb_age(call):
    lang = get_lang(call.from_user.id, call.from_user)
    if call.data == "age_no":
        bot.edit_message_text(t("age_denied", lang), call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    conn = get_db()
    conn.execute("UPDATE users SET age_declared=1 WHERE user_id=?", (call.from_user.id,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id)
    ask_terms(call.message.chat.id, lang, call.message.message_id)

def ask_terms(chat_id, lang="es", message_id=None):
    text = get_setting("terms")
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton(t("terms_accept", lang), callback_data="terms_yes"),
        types.InlineKeyboardButton(t("terms_deny", lang), callback_data="terms_no")
    )
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ("terms_yes", "terms_no"))
def cb_terms(call):
    lang = get_lang(call.from_user.id, call.from_user)
    if call.data == "terms_no":
        bot.edit_message_text(t("terms_must", lang), call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    conn = get_db()
    conn.execute("UPDATE users SET terms_accepted=1 WHERE user_id=?", (call.from_user.id,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id)
    send_main_menu(call.message.chat.id, call.from_user.id, call.message.message_id, lang)

# ==================== BIENVENIDA GRUPO ====================
@bot.message_handler(content_types=["new_chat_members"])
def on_new_member(message):
    if GROUP_ID and message.chat.id != GROUP_ID:
        return
    for member in message.new_chat_members:
        if member.id == bot.get_me().id:
            bot.send_message(message.chat.id,
                "✅ Bot añadido al grupo.\n\n"
                "Configura en main.py:\n"
                f"<code>GROUP_ID = {message.chat.id}</code>"
            )
            continue
        if member.is_bot:
            continue
        upsert_user(member)
        lang = get_lang(tg_user=member)
        bot.send_message(message.chat.id, t("group_welcome", lang, name=member.first_name or "Usuario"))

# ==================== COMANDOS DEL GRUPO ====================
# Todos los comandos de grupo se escuchan aquí

@bot.message_handler(commands=["ayuda", "help", "comandos"])
def cmd_group_help(message):
    if is_private_chat(message):
        # En privado muestra ayuda del bot
        lang = get_lang(tg_user=message.from_user)
        bot.send_message(message.chat.id, t("help_text", lang))
        return

    if GROUP_ID and message.chat.id != GROUP_ID:
        return

    uid = message.from_user.id
    vip = is_vip(uid)
    admin = is_admin(uid)
    creator = is_creator(uid)

    text = (
        "📜 <b>Comandos del grupo</b>\n\n"
        "<b>Todos los usuarios:</b>\n"
        "/ayuda — Ver esta lista\n"
        "/reglas — Reglas del grupo\n"
        "/soporte — Contactar soporte\n"
        "/yo — Tu perfil rápido\n"
        "/anuncio — Ver último anuncio de la app\n\n"
    )
    if vip or admin:
        text += (
            "<b>👑 Comandos VIP:</b>\n"
            "/promo — Promocionar tu perfil de creador (cada 30 min)\n"
            "/invitar — Generar enlace de invitación a tu perfil\n"
            "/vip — Info VIP\n\n"
        )
    if creator or admin:
        text += (
            "<b>🎨 Comandos Creador:</b>\n"
            "/miperfil — Ver/editar tu perfil de creador\n\n"
        )
    if admin:
        text += (
            "<b>🔧 Comandos Admin:</b>\n"
            "/silenciar — Silenciar el grupo\n"
            "/activar — Quitar silencio\n"
            "/broadcast <texto> — Anuncio a todo el grupo\n"
            "/setanuncio <texto> — Guardar anuncio de la app\n"
            "/stats — Estadísticas\n"
        )

    bot.reply_to(message, text)

@bot.message_handler(commands=["reglas", "rules"])
def cmd_rules(message):
    if is_private_chat(message):
        return
    if GROUP_ID and message.chat.id != GROUP_ID:
        return
    bot.reply_to(message, get_setting("group_rules"))

@bot.message_handler(commands=["soporte", "support"])
def cmd_support(message):
    if is_private_chat(message):
        bot.send_message(message.chat.id, "📬 Escribe tu mensaje y el admin te responderá.")
        return
    if GROUP_ID and message.chat.id != GROUP_ID:
        return

    uid = message.from_user.id
    text = message.text.split(maxsplit=1)
    if len(text) < 2:
        bot.reply_to(message, "Uso: <code>/soporte tu mensaje aquí</code>")
        return

    msg = text[1]
    bot.reply_to(message, "✅ Mensaje enviado al soporte. Te responderán en privado.")
    bot.send_message(ADMIN_ID,
        f"📬 <b>Soporte desde grupo</b>\n"
        f"De: {message.from_user.first_name} (@{message.from_user.username})\n"
        f"ID: <code>{uid}</code>\n\n{msg}"
    )

@bot.message_handler(commands=["yo", "me", "perfil"])
def cmd_me(message):
    if GROUP_ID and not is_private_chat(message) and message.chat.id != GROUP_ID:
        return
    upsert_user(message.from_user)
    user = get_user(message.from_user.id)
    badges = get_badges(user)
    vip = "Sí 👑" if is_vip(message.from_user.id) else "No"
    role = user["role"] if user else "user"
    text = (
        f"👤 <b>{message.from_user.first_name}</b> {badges}\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Rol: {role}\n"
        f"VIP: {vip}\n"
        f"Género: {get_gender_text(user)}\n"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=["anuncio", "announcement"])
def cmd_announcement(message):
    if GROUP_ID and not is_private_chat(message) and message.chat.id != GROUP_ID:
        return
    bot.reply_to(message, get_setting("announcement") or "No hay anuncios por ahora.")

# ---------- COMANDOS VIP ----------
@bot.message_handler(commands=["promo", "promocionar", "promocion"])
def cmd_promo(message):
    if is_private_chat(message):
        bot.reply_to(message, "Este comando se usa en el <b>grupo</b>.")
        return
    if GROUP_ID and message.chat.id != GROUP_ID:
        return

    uid = message.from_user.id
    if not is_vip(uid):
        bot.reply_to(message, t("only_vip", get_lang(tg_user=message.from_user)))
        return

    if not is_creator(uid):
        bot.reply_to(message, "Solo los <b>creadores verificados</b> pueden promocionar su perfil.\nConviértete en creador desde el bot en privado.")
        return

    ok, wait = check_cooldown(uid, "promo")
    if not ok:
        bot.reply_to(message, f"⏳ Debes esperar <b>{wait} minutos</b> para volver a promocionar.")
        return

    conn = get_db()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (uid,)).fetchone()
    user = get_user(uid)
    conn.close()

    if not c:
        bot.reply_to(message, "No tienes perfil de creador configurado.")
        return

    badges = get_badges(user)
    name = c["display_name"] or message.from_user.first_name
    text = (
        f"🔥 <b>PROMOCIÓN DE CREADOR</b>\n\n"
        f"🎨 {name} {badges}\n"
        f"{c['bio'] or ''}\n\n"
        f"💰 Mensual: {format_price(c['monthly_price'])}\n"
        f"💰 Trimestral: {format_price(c['quarterly_price'])}\n\n"
        f"➡️ Suscríbete desde el bot en privado: /start"
    )
    set_cooldown(uid, "promo")
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["invitar", "invite"])
def cmd_invite(message):
    if is_private_chat(message):
        bot.reply_to(message, "Este comando se usa en el <b>grupo</b>.")
        return
    if GROUP_ID and message.chat.id != GROUP_ID:
        return

    uid = message.from_user.id
    if not is_vip(uid):
        bot.reply_to(message, t("only_vip", get_lang(tg_user=message.from_user)))
        return

    if not is_creator(uid):
        bot.reply_to(message, "Solo creadores pueden generar invitaciones a su perfil.")
        return

    # Deep link al bot con start param
    me = bot.get_me()
    link = f"https://t.me/{me.username}?start=creator_{uid}"
    bot.reply_to(message,
        f"🔗 <b>Tu enlace de invitación:</b>\n\n"
        f"{link}\n\n"
        f"Compártelo para que la gente vea tu perfil de creador."
    )

@bot.message_handler(commands=["vip"])
def cmd_vip_info(message):
    if GROUP_ID and not is_private_chat(message) and message.chat.id != GROUP_ID:
        return
    if not is_vip(message.from_user.id):
        bot.reply_to(message, t("only_vip", get_lang(tg_user=message.from_user)))
        return
    bot.reply_to(message,
        "👑 <b>Beneficios VIP</b>\n\n"
        "• Puedes usar /promo cada 30 minutos\n"
        "• /invitar para compartir tu perfil\n"
        "• Acceso prioritario a novedades\n"
        "• Badge 👑 en tu perfil\n"
    )

# ---------- COMANDOS ADMIN GRUPO ----------
@bot.message_handler(commands=["silenciar", "mute"])
def cmd_mute(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, t("only_admin", get_lang(tg_user=message.from_user)))
        return
    if is_private_chat(message):
        return
    set_group_setting("muted", "1")
    global group_muted
    group_muted = True
    bot.reply_to(message, "🔇 <b>Grupo silenciado.</b> Solo administradores pueden escribir.")
    log_admin(message.from_user.id, "mute_group")

@bot.message_handler(commands=["activar", "unmute"])
def cmd_unmute(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, t("only_admin", get_lang(tg_user=message.from_user)))
        return
    if is_private_chat(message):
        return
    set_group_setting("muted", "0")
    global group_muted
    group_muted = False
    bot.reply_to(message, "🔉 <b>Grupo activado.</b> Todos pueden escribir.")
    log_admin(message.from_user.id, "unmute_group")

@bot.message_handler(commands=["broadcast"])
def cmd_broadcast(message):
    if not is_admin(message.from_user.id):
        return
    if is_private_chat(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Uso: <code>/broadcast texto del anuncio</code>")
        return
    text = f"📢 <b>ANUNCIO</b>\n\n{parts[1]}"
    bot.send_message(message.chat.id, text)
    log_admin(message.from_user.id, "broadcast", details=parts[1][:100])

@bot.message_handler(commands=["setanuncio"])
def cmd_set_announcement(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Uso: <code>/setanuncio texto del anuncio</code>")
        return
    set_setting("announcement", parts[1])
    bot.reply_to(message, "✅ Anuncio de la aplicación actualizado.")

@bot.message_handler(commands=["stats"])
def cmd_stats(message):
    if not is_admin(message.from_user.id):
        return
    conn = get_db()
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    vips = conn.execute("""SELECT COUNT(DISTINCT user_id) FROM subscriptions
        WHERE status='active' AND end_date > ?""", (datetime.now().isoformat(),)).fetchone()[0]
    creators = conn.execute("SELECT COUNT(*) FROM creators").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM transactions WHERE status='pending'").fetchone()[0]
    conn.close()
    bot.reply_to(message,
        f"📊 <b>Estadísticas</b>\n\n"
        f"Usuarios: {users}\n"
        f"VIP activos: {vips}\n"
        f"Creadores: {creators}\n"
        f"Pagos pendientes: {pending}\n"
        f"Grupo silenciado: {'Sí' if is_group_muted() else 'No'}"
    )

# Filtro de silencio del grupo
@bot.message_handler(func=lambda m: m.chat.type in ("group", "supergroup") and is_group_muted() and not is_admin(m.from_user.id),
                     content_types=["text", "photo", "video", "document", "sticker", "animation", "voice"])
def filter_muted(message):
    if GROUP_ID and message.chat.id != GROUP_ID:
        return
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except:
        pass

# ==================== CALLBACKS PRIVADOS (menús) ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_main")
def cb_menu_main(call):
    lang = get_lang(call.from_user.id)
    send_main_menu(call.message.chat.id, call.from_user.id, call.message.message_id, lang)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "menu_help")
def cb_help(call):
    lang = get_lang(call.from_user.id)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(t("help_text", lang), call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "menu_account")
def cb_account(call):
    user = get_user(call.from_user.id)
    lang = get_lang(call.from_user.id)
    badges = get_badges(user)
    gender = get_gender_text(user, lang)
    role = user["role"] if user else "user"
    vip = "Sí 👑" if is_vip(call.from_user.id) else "No"

    text = (
        f"👤 <b>Mi Cuenta</b> {badges}\n\n"
        f"ID: <code>{call.from_user.id}</code>\n"
        f"Rol: {role}\n"
        f"VIP: {vip}\n"
        f"Género: {gender}\n"
        f"Edad verificada: {'Sí 🔞✅' if user and user['age_verified_real'] == 2 else 'No'}\n"
    )
    kb = types.InlineKeyboardMarkup()
    if not (user and user["age_verified_real"] == 2):
        kb.add(types.InlineKeyboardButton(
            t("request_verif", lang),
            web_app=types.WebAppInfo(url=WEBAPP_VERIFICATION_URL)
        ))
    if user and user["creator_verified"] != 2:
        kb.add(types.InlineKeyboardButton("🎨 Convertirme en Creador ($50)", callback_data="become_creator"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "menu_explore")
def cb_explore(call):
    lang = get_lang(call.from_user.id)
    conn = get_db()
    creators = conn.execute("""
        SELECT c.*, u.first_name, u.gender, u.gender_verified, u.age_verified_real
        FROM creators c JOIN users u ON c.user_id = u.user_id
        WHERE u.creator_verified = 2 AND u.banned = 0
    """).fetchall()
    conn.close()

    if not creators:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
        bot.edit_message_text(t("no_creators", lang), call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    text = "🔍 <b>Creadores</b>\n\n"
    kb = types.InlineKeyboardMarkup()
    for c in creators:
        badges = get_badges(c)
        name = c["display_name"] or c["first_name"] or "Creador"
        text += f"• {name} {badges} — {format_price(c['monthly_price'])}/mes\n"
        kb.add(types.InlineKeyboardButton(f"{name} {badges}", callback_data=f"creator_{c['user_id']}"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("creator_"))
def cb_creator_profile(call):
    lang = get_lang(call.from_user.id)
    creator_id = int(call.data.split("_")[1])
    conn = get_db()
    c = conn.execute("""SELECT c.*, u.first_name, u.gender, u.gender_verified, u.age_verified_real
        FROM creators c JOIN users u ON c.user_id = u.user_id WHERE c.user_id=?""", (creator_id,)).fetchone()
    conn.close()
    if not c:
        bot.answer_callback_query(call.id, "No encontrado", show_alert=True)
        return

    badges = get_badges(c)
    name = c["display_name"] or c["first_name"]
    subscribed = has_active_sub(call.from_user.id, creator_id)

    text = (
        f"🎨 <b>{name}</b> {badges}\n\n"
        f"{c['bio'] or ''}\n\n"
        f"💰 Mensual: {format_price(c['monthly_price'])}\n"
        f"💰 Trimestral: {format_price(c['quarterly_price'])}\n"
    )
    kb = types.InlineKeyboardMarkup()
    if subscribed:
        text += f"\n{t('has_sub', lang)}"
        kb.add(types.InlineKeyboardButton(t("view_content", lang), callback_data=f"view_{creator_id}"))
    else:
        text += f"\n{t('must_pay', lang)}"
        kb.add(types.InlineKeyboardButton(f"💳 Mensual {format_price(c['monthly_price'])}", callback_data=f"sub_monthly_{creator_id}"))
        kb.add(types.InlineKeyboardButton(f"💳 Trimestral {format_price(c['quarterly_price'])}", callback_data=f"sub_quarterly_{creator_id}"))
    kb.add(types.InlineKeyboardButton(t("report", lang), callback_data=f"report_{creator_id}"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="menu_explore"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

# ==================== PAGOS ====================
@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("sub_"))
def cb_subscribe(call):
    parts = call.data.split("_")
    plan, creator_id = parts[1], int(parts[2])
    lang = get_lang(call.from_user.id)
    conn = get_db()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (creator_id,)).fetchone()
    conn.close()
    if not c:
        bot.answer_callback_query(call.id, "Error", show_alert=True)
        return
    price = c["monthly_price"] if plan == "monthly" else c["quarterly_price"]
    text = (
        f"💳 <b>Suscripción {plan}</b>\n\nPrecio: {format_price(price)}\n\n"
        f"{get_setting('payment_methods')}\n\nDespués de pagar, envía la <b>captura</b>."
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Ya pagué - Enviar captura", callback_data=f"send_proof_{plan}_{creator_id}"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data=f"creator_{creator_id}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("send_proof_"))
def cb_send_proof(call):
    parts = call.data.split("_")
    plan, creator_id = parts[2], int(parts[3])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📸 Envía ahora la <b>captura del pago</b> (foto).")
    bot.register_next_step_handler(msg, lambda m: process_payment_proof(m, plan, creator_id))

def process_payment_proof(message, plan, creator_id):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Envía una foto.")
        return
    file_id = message.photo[-1].file_id
    conn = get_db()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (creator_id,)).fetchone()
    amount = c["monthly_price"] if plan == "monthly" else c["quarterly_price"]
    cur = conn.cursor()
    cur.execute("""INSERT INTO transactions (user_id, creator_id, type, amount, status, payment_method, screenshot_file_id, created_at)
        VALUES (?, ?, ?, ?, 'pending', 'manual', ?, ?)""",
                (message.from_user.id, creator_id, f"sub_{plan}", amount, file_id, datetime.now().isoformat()))
    tx_id = cur.lastrowid
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Captura recibida. Esperando verificación del admin.")
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_tx_{tx_id}"),
        types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_tx_{tx_id}")
    )
    bot.send_photo(ADMIN_ID, file_id,
        caption=f"💳 <b>NUEVO PAGO</b>\nUser: {message.from_user.id}\nCreator: {creator_id}\nPlan: {plan}\nMonto: {format_price(amount)}\nTX #{tx_id}",
        reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("approve_tx_"))
def cb_approve_tx(call):
    if not is_admin(call.from_user.id):
        return
    tx_id = int(call.data.split("_")[2])
    conn = get_db()
    tx = conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
    if not tx or tx["status"] != "pending":
        bot.answer_callback_query(call.id, "Ya procesado", show_alert=True)
        conn.close()
        return
    now = datetime.now()
    if tx["type"] == "creator_fee":
        conn.execute("UPDATE users SET role='creator', creator_verified=2 WHERE user_id=?", (tx["user_id"],))
        conn.execute("""INSERT OR IGNORE INTO creators (user_id, display_name, bio, created_at)
            VALUES (?, ?, 'Nuevo creador', ?)""", (tx["user_id"], f"Creator {tx['user_id']}", now.isoformat()))
        conn.execute("UPDATE transactions SET status='approved', reviewed_at=? WHERE id=?", (now.isoformat(), tx_id))
        conn.commit()
        conn.close()
        bot.send_message(tx["user_id"], "✅ ¡Has sido aprobado como <b>Creador</b>!")
        try:
            bot.edit_message_caption(caption=call.message.caption + "\n\n✅ APROBADO", chat_id=call.message.chat.id, message_id=call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id, "Creador aprobado")
        return

    days = 30 if "monthly" in tx["type"] else 90
    end = (now + timedelta(days=days)).isoformat()
    conn.execute("""INSERT OR REPLACE INTO subscriptions
        (user_id, creator_id, plan, amount, status, start_date, end_date, payment_method, created_at)
        VALUES (?, ?, ?, ?, 'active', ?, ?, 'manual', ?)""",
                 (tx["user_id"], tx["creator_id"], tx["type"], tx["amount"], now.isoformat(), end, now.isoformat()))
    conn.execute("UPDATE creators SET total_subscribers=total_subscribers+1, total_earnings=total_earnings+? WHERE user_id=?",
                 (tx["amount"], tx["creator_id"]))
    conn.execute("UPDATE transactions SET status='approved', reviewed_at=? WHERE id=?", (now.isoformat(), tx_id))
    conn.commit()
    conn.close()

    invite_msg = ""
    if PRIVATE_CHANNEL_ID:
        try:
            link = bot.create_chat_invite_link(PRIVATE_CHANNEL_ID, member_limit=1, name=f"Sub {tx['user_id']}")
            invite_msg = f"\n\n🔗 Acceso al contenido:\n{link.invite_link}"
        except:
            invite_msg = "\n\n⚠️ Contacta al admin para el acceso."

    bot.send_message(tx["user_id"], f"✅ <b>Pago aprobado</b>\nSuscripción activa hasta {end[:10]}.{invite_msg}")
    try:
        bot.edit_message_caption(caption=call.message.caption + "\n\n✅ APROBADO", chat_id=call.message.chat.id, message_id=call.message.message_id)
    except:
        pass
    bot.answer_callback_query(call.id, "Aprobado")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("reject_tx_"))
def cb_reject_tx(call):
    if not is_admin(call.from_user.id):
        return
    tx_id = int(call.data.split("_")[2])
    conn = get_db()
    tx = conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
    if not tx or tx["status"] != "pending":
        bot.answer_callback_query(call.id, "Ya procesado", show_alert=True)
        conn.close()
        return
    conn.execute("UPDATE transactions SET status='rejected', reviewed_at=? WHERE id=?", (datetime.now().isoformat(), tx_id))
    if tx["type"] == "creator_fee":
        conn.execute("UPDATE users SET creator_verified=0 WHERE user_id=?", (tx["user_id"],))
    conn.commit()
    conn.close()
    bot.send_message(tx["user_id"], "❌ Tu pago fue rechazado.")
    try:
        bot.edit_message_caption(caption=call.message.caption + "\n\n❌ RECHAZADO", chat_id=call.message.chat.id, message_id=call.message.message_id)
    except:
        pass
    bot.answer_callback_query(call.id, "Rechazado")

# ==================== VERIFICACIÓN ====================
@bot.message_handler(content_types=["web_app_data"])
def handle_webapp(message):
    try:
        data = json.loads(message.web_app_data.data)
    except:
        bot.send_message(message.chat.id, "Error al procesar.")
        return
    user_id = message.from_user.id
    conn = get_db()
    conn.execute("INSERT INTO verifications (user_id, status, source, created_at) VALUES (?, 'pending', 'webapp', ?)",
                 (user_id, datetime.now().isoformat()))
    conn.execute("UPDATE users SET age_verified_real=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "📸 Datos recibidos. Ahora envía las <b>fotos</b> (documento + selfie).")
    bot.send_message(ADMIN_ID, f"📸 Nueva verificación (Mini App)\nUsuario: {user_id}")

@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    if not is_private_chat(message):
        return
    user = get_user(message.from_user.id)
    if not user or user["age_verified_real"] == 2:
        return
    file_id = message.photo[-1].file_id
    conn = get_db()
    ver = conn.execute("SELECT * FROM verifications WHERE user_id=? AND status='pending' ORDER BY id DESC LIMIT 1",
                       (message.from_user.id,)).fetchone()
    if not ver:
        cur = conn.cursor()
        cur.execute("INSERT INTO verifications (user_id, doc_photo_id, status, source, created_at) VALUES (?, ?, 'pending', 'manual', ?)",
                    (message.from_user.id, file_id, datetime.now().isoformat()))
        conn.execute("UPDATE users SET age_verified_real=1 WHERE user_id=?", (message.from_user.id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "📸 Documento recibido. Ahora envía tu <b>selfie</b>.")
        return
    if not ver["doc_photo_id"]:
        conn.execute("UPDATE verifications SET doc_photo_id=? WHERE id=?", (file_id, ver["id"]))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "📸 Documento recibido. Ahora envía tu <b>selfie</b>.")
        return
    if not ver["selfie_photo_id"]:
        conn.execute("UPDATE verifications SET selfie_photo_id=? WHERE id=?", (file_id, ver["id"]))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ Fotos recibidas. Esperando revisión del admin.")
        kb = types.InlineKeyboardMarkup()
        kb.row(
            types.InlineKeyboardButton("♂️ Hombre", callback_data=f"verif_male_{ver['id']}"),
            types.InlineKeyboardButton("♀️ Mujer", callback_data=f"verif_female_{ver['id']}")
        )
        kb.add(types.InlineKeyboardButton("❌ Rechazar", callback_data=f"verif_reject_{ver['id']}"))
        bot.send_message(ADMIN_ID, f"📸 <b>Verificación pendiente</b>\nUsuario: {message.from_user.id}")
        bot.send_photo(ADMIN_ID, ver["doc_photo_id"] or file_id, caption="Documento")
        bot.send_photo(ADMIN_ID, file_id, caption="Selfie", reply_markup=kb)
        return
    conn.close()

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("verif_"))
def cb_verify(call):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    action, ver_id = parts[1], int(parts[2])
    conn = get_db()
    ver = conn.execute("SELECT * FROM verifications WHERE id=?", (ver_id,)).fetchone()
    if not ver or ver["status"] != "pending":
        bot.answer_callback_query(call.id, "Ya procesado", show_alert=True)
        conn.close()
        return
    now = datetime.now().isoformat()
    if action == "reject":
        conn.execute("UPDATE verifications SET status='rejected', reviewed_at=?, reviewed_by=? WHERE id=?",
                     (now, call.from_user.id, ver_id))
        conn.execute("UPDATE users SET age_verified_real=0 WHERE user_id=?", (ver["user_id"],))
        conn.commit()
        conn.close()
        bot.send_message(ver["user_id"], "❌ Verificación rechazada.")
        bot.answer_callback_query(call.id, "Rechazado")
        return
    gender = "male" if action == "male" else "female"
    conn.execute("UPDATE verifications SET status='approved', assigned_gender=?, reviewed_at=?, reviewed_by=? WHERE id=?",
                 (gender, now, call.from_user.id, ver_id))
    conn.execute("UPDATE users SET age_verified_real=2, gender=?, gender_verified=1 WHERE user_id=?",
                 (gender, ver["user_id"]))
    conn.commit()
    conn.close()
    badge = "♂️" if gender == "male" else "♀️"
    bot.send_message(ver["user_id"], f"✅ <b>Verificación aprobada</b>\nBadges: 🔞✅ {badge}")
    bot.answer_callback_query(call.id, f"Aprobado ({gender})")

# ==================== OTROS ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_subs")
def cb_subs(call):
    lang = get_lang(call.from_user.id)
    conn = get_db()
    subs = conn.execute("""SELECT s.*, c.display_name FROM subscriptions s
        JOIN creators c ON s.creator_id = c.user_id
        WHERE s.user_id=? AND s.status='active' AND s.end_date > ?""",
                        (call.from_user.id, datetime.now().isoformat())).fetchall()
    conn.close()
    text = "No tienes suscripciones activas." if not subs else "📋 <b>Mis Suscripciones</b>\n\n" + "\n".join(
        f"• {s['display_name']} — hasta {s['end_date'][:10]}" for s in subs)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "become_creator")
def cb_become_creator(call):
    lang = get_lang(call.from_user.id)
    user = get_user(call.from_user.id)
    if user["creator_verified"] == 2:
        bot.answer_callback_query(call.id, "Ya eres creador", show_alert=True)
        return
    text = f"🎨 Convertirse en Creador — {format_price(CREATOR_FEE)}\n\n{get_setting('payment_methods')}"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(f"💸 Ya pagué {format_price(CREATOR_FEE)}", callback_data="pay_creator_fee"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="menu_account"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "pay_creator_fee")
def cb_pay_creator_fee(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"📸 Envía la captura del pago de ${CREATOR_FEE}.")
    bot.register_next_step_handler(msg, process_creator_fee)

def process_creator_fee(message):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Envía una foto.")
        return
    file_id = message.photo[-1].file_id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO transactions (user_id, type, amount, status, payment_method, screenshot_file_id, created_at)
        VALUES (?, 'creator_fee', ?, 'pending', 'manual', ?, ?)""",
                (message.from_user.id, CREATOR_FEE, file_id, datetime.now().isoformat()))
    tx_id = cur.lastrowid
    conn.execute("UPDATE users SET creator_verified=1 WHERE user_id=?", (message.from_user.id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Recibido. Esperando aprobación.")
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Aprobar Creador", callback_data=f"approve_tx_{tx_id}"),
        types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_tx_{tx_id}")
    )
    bot.send_photo(ADMIN_ID, file_id, caption=f"🎨 CREATOR FEE\nUser: {message.from_user.id}\nTX #{tx_id}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "admin_panel")
def cb_admin_panel(call):
    if not is_admin(call.from_user.id):
        return
    conn = get_db()
    pending_tx = conn.execute("SELECT COUNT(*) FROM transactions WHERE status='pending'").fetchone()[0]
    pending_ver = conn.execute("SELECT COUNT(*) FROM verifications WHERE status='pending'").fetchone()[0]
    conn.close()
    text = (
        f"🔧 <b>Panel Admin</b>\n\n"
        f"Pagos pendientes: {pending_tx}\n"
        f"Verificaciones pendientes: {pending_ver}\n"
        f"Grupo: {GROUP_INVITE}\n"
        f"GROUP_ID: {GROUP_ID or 'No configurado'}\n"
        f"Canal: {PRIVATE_CHANNEL_ID or 'No configurado'}\n"
        f"Silenciado: {'Sí' if is_group_muted() else 'No'}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Menú", callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "creator_panel")
def cb_creator_panel(call):
    if not is_creator(call.from_user.id):
        bot.answer_callback_query(call.id, "No eres creador", show_alert=True)
        return
    conn = get_db()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (call.from_user.id,)).fetchone()
    conn.close()
    text = f"🎨 <b>Panel Creador</b>\n\nSuscriptores: {c['total_subscribers']}\nGanancias: {format_price(c['total_earnings'])}"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Menú", callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

# Deep link: /start creator_XXXX
@bot.message_handler(func=lambda m: m.text and m.text.startswith("/start creator_"))
def deep_link_creator(message):
    if not is_private_chat(message):
        return
    try:
        creator_id = int(message.text.split("_")[1])
    except:
        return
    upsert_user(message.from_user)
    # Reutilizar el callback de perfil
    class FakeCall:
        def __init__(self):
            self.data = f"creator_{creator_id}"
            self.from_user = message.from_user
            self.message = message
            self.id = "0"
    # Simplificado: enviar perfil directamente
    conn = get_db()
    c = conn.execute("SELECT c.*, u.first_name FROM creators c JOIN users u ON c.user_id=u.user_id WHERE c.user_id=?", (creator_id,)).fetchone()
    conn.close()
    if not c:
        bot.send_message(message.chat.id, "Creador no encontrado.")
        return
    badges = get_badges(c)
    name = c["display_name"] or c["first_name"]
    text = f"🎨 <b>{name}</b> {badges}\n\n{c['bio'] or ''}\n\n💰 {format_price(c['monthly_price'])}/mes"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(f"Suscribirse {format_price(c['monthly_price'])}", callback_data=f"sub_monthly_{creator_id}"))
    kb.add(types.InlineKeyboardButton("« Menú", callback_data="menu_main"))
    bot.send_message(message.chat.id, text, reply_markup=kb)

# ==================== ARRANQUE ====================
if __name__ == "__main__":
    init_db()
    # Cargar estado de mute
    global group_muted
    group_muted = is_group_muted()
    print("OnlyFans_ManagerBot V6 started")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"GROUP_ID: {GROUP_ID}")
    print(f"PRIVATE_CHANNEL_ID: {PRIVATE_CHANNEL_ID}")
    print(f"Promo cooldown: {PROMO_COOLDOWN_MINUTES} min")
    bot.infinity_polling()
