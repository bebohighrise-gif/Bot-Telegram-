#!/usr/bin/env python3
"""
OnlyFans_ManagerBot - V7
- TODO el contenido (fotos/vídeos) se ve SOLO dentro del bot (protect_content)
- Buscador de usuarios y creadores
- Creadores suben contenido desde el bot
- Grupo = comunidad (roles VIP/normal/admin)
- Multilingüe (prioridad español)
"""

import telebot
from telebot import types
import sqlite3
import json
from datetime import datetime, timedelta

# ==================== CONFIGURACIÓN ====================
TELEGRAM_TOKEN = "PON_AQUI_TU_TOKEN"
ADMIN_ID = 7653419875

GROUP_ID = None                               # -100xxxxxxxxxx
GROUP_INVITE = "https://t.me/+oMkBHSWhjf5lNTZh"

CREATOR_FEE = 50.0
PROMO_COOLDOWN_MINUTES = 30
WEBAPP_VERIFICATION_URL = "https://TU_DOMINIO.com/verification.html"

DB_FILE = "bot.db"
bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")

group_muted = False

# ==================== TEXTOS ====================
TEXTS = {
    "es": {
        "welcome": "💖 <b>Bienvenido/a, {name}</b>\n\nPlataforma de contenido exclusivo.\nTodo el contenido se ve <b>solo aquí dentro del bot</b>.\nElige una opción:",
        "age_title": "🔒 <b>Confirmación de Edad</b>",
        "age_text": "Este bot contiene contenido para adultos.\n\n¿Confirmas que eres <b>mayor de 18 años</b>?",
        "age_yes": "✅ Sí, soy mayor de 18",
        "age_no": "❌ Soy menor",
        "age_denied": "🚫 Solo para mayores de 18.",
        "terms_accept": "✅ Acepto",
        "terms_deny": "❌ No acepto",
        "terms_must": "Debes aceptar los términos.",
        "menu_explore": "🔍 Explorar",
        "menu_search": "🔎 Buscar",
        "menu_subs": "📋 Mis Suscripciones",
        "menu_account": "👤 Mi Cuenta",
        "menu_help": "❓ Ayuda",
        "menu_creator": "🎨 Panel Creador",
        "menu_admin": "🔧 Panel Admin",
        "back": "« Volver",
        "back_menu": "« Menú",
        "must_pay": "🔒 <b>Debes pagar para ver el contenido</b>\nEl contenido solo se muestra dentro del bot.",
        "has_sub": "✅ <b>Suscripción activa</b>",
        "view_content": "📸 Ver contenido",
        "no_content": "Este creador aún no ha subido contenido.",
        "report": "📢 Reportar",
        "request_verif": "📸 Verificación con cámara",
        "banned": "🚫 Tu cuenta está baneada.",
        "no_creators": "Aún no hay creadores.",
        "search_prompt": "🔎 Escribe el nombre o @usuario que quieres buscar:",
        "search_results": "🔎 <b>Resultados</b> ({n}):",
        "search_empty": "No se encontraron resultados.",
        "group_welcome": "👋 Bienvenido/a al grupo, {name}!\nUsa /ayuda · Regístrate en privado con /start",
        "use_private": "⚠️ Usa este comando en <b>chat privado</b>.",
        "only_vip": "👑 Solo usuarios <b>VIP</b>.",
        "only_admin": "🔒 Solo administradores.",
        "only_creator": "🎨 Solo creadores.",
        "help_text": (
            "❓ <b>Ayuda</b>\n\n"
            "• El contenido <b>solo se ve dentro del bot</b> (no hay canales externos).\n"
            "• Usa <b>Buscar</b> para encontrar creadores.\n"
            "• Paga la suscripción para desbloquear fotos/vídeos.\n"
            "• Verificación con cámara para badges.\n"
            "• Para ser Creador: 50$."
        ),
    },
    "en": {
        "welcome": "💖 <b>Welcome, {name}</b>\n\nExclusive content platform.\nAll content is viewed <b>only inside this bot</b>.",
        "age_title": "🔒 <b>Age Confirmation</b>",
        "age_text": "Adult content. Confirm you are <b>over 18</b>?",
        "age_yes": "✅ Yes, over 18",
        "age_no": "❌ Underage",
        "age_denied": "🚫 Adults only.",
        "terms_accept": "✅ I accept",
        "terms_deny": "❌ I do not accept",
        "terms_must": "You must accept the terms.",
        "menu_explore": "🔍 Explore",
        "menu_search": "🔎 Search",
        "menu_subs": "📋 My Subscriptions",
        "menu_account": "👤 My Account",
        "menu_help": "❓ Help",
        "menu_creator": "🎨 Creator Panel",
        "menu_admin": "🔧 Admin Panel",
        "back": "« Back",
        "back_menu": "« Menu",
        "must_pay": "🔒 <b>You must pay to view content</b>",
        "has_sub": "✅ <b>Active subscription</b>",
        "view_content": "📸 View content",
        "no_content": "This creator has no content yet.",
        "report": "📢 Report",
        "request_verif": "📸 Camera verification",
        "banned": "🚫 Banned.",
        "no_creators": "No creators yet.",
        "search_prompt": "🔎 Type the name or @username to search:",
        "search_results": "🔎 <b>Results</b> ({n}):",
        "search_empty": "No results found.",
        "group_welcome": "👋 Welcome, {name}! /help · Register in private with /start",
        "use_private": "⚠️ Use in <b>private chat</b>.",
        "only_vip": "👑 VIP only.",
        "only_admin": "🔒 Admins only.",
        "only_creator": "🎨 Creators only.",
        "help_text": "❓ <b>Help</b>\n\n• Content only inside the bot.\n• Search to find creators.\n• Subscribe to unlock media.\n• $50 to become Creator.",
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

# ==================== DB ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        role TEXT DEFAULT 'user', language TEXT DEFAULT 'es',
        age_declared INTEGER DEFAULT 0, terms_accepted INTEGER DEFAULT 0,
        age_verified_real INTEGER DEFAULT 0, gender TEXT, gender_verified INTEGER DEFAULT 0,
        creator_verified INTEGER DEFAULT 0, banned INTEGER DEFAULT 0, ban_reason TEXT,
        joined_at TEXT, last_active TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS creators (
        user_id INTEGER PRIMARY KEY, display_name TEXT, bio TEXT,
        monthly_price REAL DEFAULT 9.99, quarterly_price REAL DEFAULT 24.99,
        total_subscribers INTEGER DEFAULT 0, total_earnings REAL DEFAULT 0,
        created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, creator_id INTEGER,
        plan TEXT, amount REAL, status TEXT DEFAULT 'active',
        start_date TEXT, end_date TEXT, payment_method TEXT, created_at TEXT,
        UNIQUE(user_id, creator_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS content (
        id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id INTEGER, title TEXT,
        description TEXT, file_id TEXT, media_type TEXT DEFAULT 'photo',
        is_premium INTEGER DEFAULT 1, views INTEGER DEFAULT 0, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, creator_id INTEGER,
        type TEXT, amount REAL, currency TEXT DEFAULT 'USD', status TEXT DEFAULT 'pending',
        payment_method TEXT, screenshot_file_id TEXT, created_at TEXT, reviewed_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        doc_photo_id TEXT, selfie_photo_id TEXT, status TEXT DEFAULT 'pending',
        assigned_gender TEXT, source TEXT DEFAULT 'manual',
        created_at TEXT, reviewed_at TEXT, reviewed_by INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER, reported_id INTEGER,
        reason TEXT, details TEXT, status TEXT DEFAULT 'open', created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, action TEXT,
        target_id INTEGER, details TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS cooldowns (
        user_id INTEGER, command TEXT, last_used TEXT, PRIMARY KEY (user_id, command))""")
    c.execute("""CREATE TABLE IF NOT EXISTS group_settings (key TEXT PRIMARY KEY, value TEXT)""")

    defaults = {
        "payment_methods": "💳 <b>Formas de pago:</b>\n\n• Transferencia / Bizum\n• Crypto (USDT / BTC)\n• Telegram Stars\n\n<i>El admin actualiza los datos.</i>",
        "terms": "📜 <b>Términos</b>\n\n1. Mayor de 18.\n2. Uso personal.\n3. Prohibida redistribución.\n4. Ban por incumplimientos.\n5. Al continuar aceptas.",
        "group_rules": "📜 <b>Reglas del grupo</b>\n\n1. Respeta a todos.\n2. No spam.\n3. VIP pueden /promo cada 30 min.\n4. /soporte para ayuda.\n5. Admin puede silenciar.",
        "announcement": "📢 Bienvenidos. Usa /ayuda. Todo el contenido se ve solo dentro del bot."
    }
    for k, v in defaults.items():
        if not c.execute("SELECT 1 FROM settings WHERE key=?", (k,)).fetchone():
            c.execute("INSERT INTO settings VALUES (?,?)", (k, v))
    if not c.execute("SELECT 1 FROM group_settings WHERE key='muted'").fetchone():
        c.execute("INSERT INTO group_settings VALUES ('muted','0')")
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
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()

def get_group_setting(key):
    conn = get_db()
    row = conn.execute("SELECT value FROM group_settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None

def set_group_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO group_settings (key, value) VALUES (?,?)", (key, value))
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
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name,
        language=excluded.language, last_active=excluded.last_active""",
                 (tg_user.id, tg_user.username, tg_user.first_name, lang, now, now))
    conn.commit()
    conn.close()

def is_admin(uid): return uid == ADMIN_ID
def is_banned(uid):
    u = get_user(uid)
    return u and u["banned"] == 1
def is_creator(uid):
    u = get_user(uid)
    return u and u["role"] in ("creator", "admin") and u["creator_verified"] == 2
def is_vip(uid):
    if is_admin(uid) or is_creator(uid): return True
    conn = get_db()
    row = conn.execute("SELECT 1 FROM subscriptions WHERE user_id=? AND status='active' AND end_date>?",
                       (uid, datetime.now().isoformat())).fetchone()
    conn.close()
    return bool(row)
def format_price(p): return f"${p:.2f}"
def has_active_sub(user_id, creator_id):
    conn = get_db()
    row = conn.execute("SELECT 1 FROM subscriptions WHERE user_id=? AND creator_id=? AND status='active' AND end_date>?",
                       (user_id, creator_id, datetime.now().isoformat())).fetchone()
    conn.close()
    return bool(row)
def get_badges(user):
    badges = []
    if user and user["age_verified_real"] == 2: badges.append("🔞✅")
    if user and user["gender_verified"] and user["gender"]:
        badges.append("♂️" if user["gender"] == "male" else "♀️")
    if user and is_vip(user["user_id"]): badges.append("👑")
    return " ".join(badges)
def get_gender_text(user, lang="es"):
    if not user or not user["gender_verified"]: return "No verificado" if lang=="es" else "Not verified"
    return ("Masculino" if lang=="es" else "Male") if user["gender"]=="male" else ("Femenino" if lang=="es" else "Female")
def is_private_chat(m): return m.chat.type == "private"
def check_cooldown(user_id, command, minutes=PROMO_COOLDOWN_MINUTES):
    conn = get_db()
    row = conn.execute("SELECT last_used FROM cooldowns WHERE user_id=? AND command=?", (user_id, command)).fetchone()
    conn.close()
    if not row: return True, 0
    diff = (datetime.now() - datetime.fromisoformat(row["last_used"])).total_seconds() / 60
    if diff >= minutes: return True, 0
    return False, int(minutes - diff)
def set_cooldown(user_id, command):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO cooldowns (user_id, command, last_used) VALUES (?,?,?)",
                 (user_id, command, datetime.now().isoformat()))
    conn.commit()
    conn.close()
def is_group_muted(): return get_group_setting("muted") == "1"

# ==================== MENÚ ====================
def main_menu_kb(user_id, lang):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(t("menu_explore", lang), callback_data="menu_explore"),
        types.InlineKeyboardButton(t("menu_search", lang), callback_data="menu_search")
    )
    kb.add(
        types.InlineKeyboardButton(t("menu_subs", lang), callback_data="menu_subs"),
        types.InlineKeyboardButton(t("menu_account", lang), callback_data="menu_account")
    )
    kb.add(types.InlineKeyboardButton(t("menu_help", lang), callback_data="menu_help"))
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
        except: pass
    bot.send_message(chat_id, text, reply_markup=kb)

# ==================== START ====================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    if not is_private_chat(message):
        bot.reply_to(message, t("use_private", get_lang(tg_user=message.from_user)))
        return
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, t("banned", get_lang(tg_user=message.from_user)))
        return
    # Deep link creator_
    if message.text and "creator_" in message.text:
        try:
            cid = int(message.text.split("creator_")[1].split()[0])
            upsert_user(message.from_user)
            show_creator_profile(message.chat.id, message.from_user.id, cid)
            return
        except: pass

    upsert_user(message.from_user)
    user = get_user(message.from_user.id)
    lang = user["language"] or get_lang(tg_user=message.from_user)
    if not user["age_declared"]:
        ask_age(message.chat.id, lang)
        return
    if not user["terms_accepted"]:
        ask_terms(message.chat.id, lang)
        return
    send_main_menu(message.chat.id, message.from_user.id, lang=lang)

def ask_age(chat_id, lang="es"):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(t("age_yes", lang), callback_data="age_yes"),
           types.InlineKeyboardButton(t("age_no", lang), callback_data="age_no"))
    bot.send_message(chat_id, f"{t('age_title', lang)}\n\n{t('age_text', lang)}", reply_markup=kb)

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
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(t("terms_accept", lang), callback_data="terms_yes"),
           types.InlineKeyboardButton(t("terms_deny", lang), callback_data="terms_no"))
    text = get_setting("terms")
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except: pass
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

# ==================== BUSCADOR ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_search")
def cb_search(call):
    lang = get_lang(call.from_user.id)
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, t("search_prompt", lang))
    bot.register_next_step_handler(msg, process_search)

def process_search(message):
    if not is_private_chat(message):
        return
    lang = get_lang(message.from_user.id, message.from_user)
    q = (message.text or "").strip().lstrip("@").lower()
    if not q or len(q) < 2:
        bot.send_message(message.chat.id, "Escribe al menos 2 caracteres.")
        return

    conn = get_db()
    # Buscar creadores y usuarios
    results = conn.execute("""
        SELECT u.user_id, u.username, u.first_name, u.role, u.gender, u.gender_verified,
               u.age_verified_real, c.display_name, c.monthly_price, c.bio
        FROM users u
        LEFT JOIN creators c ON u.user_id = c.user_id
        WHERE u.banned = 0 AND (
            LOWER(u.username) LIKE ? OR LOWER(u.first_name) LIKE ?
            OR LOWER(c.display_name) LIKE ?
        )
        LIMIT 15
    """, (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    conn.close()

    if not results:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
        bot.send_message(message.chat.id, t("search_empty", lang), reply_markup=kb)
        return

    text = t("search_results", lang, n=len(results)) + "\n\n"
    kb = types.InlineKeyboardMarkup()
    for r in results:
        name = r["display_name"] or r["first_name"] or r["username"] or str(r["user_id"])
        badges = get_badges(r)
        role_icon = "🎨" if r["role"] in ("creator", "admin") and r.get("display_name") else "👤"
        label = f"{role_icon} {name} {badges}"
        text += f"• {label}\n"
        kb.add(types.InlineKeyboardButton(label[:60], callback_data=f"profile_{r['user_id']}"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("profile_"))
def cb_profile(call):
    uid = int(call.data.split("_")[1])
    show_creator_profile(call.message.chat.id, call.from_user.id, uid, call.message.message_id)
    bot.answer_callback_query(call.id)

def show_creator_profile(chat_id, viewer_id, target_id, message_id=None):
    lang = get_lang(viewer_id)
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (target_id,)).fetchone()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (target_id,)).fetchone()
    content_count = conn.execute("SELECT COUNT(*) FROM content WHERE creator_id=?", (target_id,)).fetchone()[0]
    conn.close()

    if not u:
        bot.send_message(chat_id, "Usuario no encontrado.")
        return

    badges = get_badges(u)
    name = (c["display_name"] if c else None) or u["first_name"] or "Usuario"
    is_cre = c is not None and u["creator_verified"] == 2

    text = f"{'\ud83c\udfa8' if is_cre else '\ud83d\udc64'} <b>{name}</b> {badges}\n\n"
    if u["username"]:
        text += f"@{u['username']}\n"
    text += f"Género: {get_gender_text(u, lang)}\n"
    if is_cre:
        text += f"\n{c['bio'] or ''}\n\n"
        text += f"💰 Mensual: {format_price(c['monthly_price'])}\n"
        text += f"💰 Trimestral: {format_price(c['quarterly_price'])}\n"
        text += f"📸 Contenidos: {content_count}\n"
        text += f"👥 Suscriptores: {c['total_subscribers']}\n"

    kb = types.InlineKeyboardMarkup()
    if is_cre:
        subscribed = has_active_sub(viewer_id, target_id)
        if subscribed:
            text += f"\n{t('has_sub', lang)}"
            kb.add(types.InlineKeyboardButton(t("view_content", lang), callback_data=f"viewcontent_{target_id}_0"))
        else:
            text += f"\n{t('must_pay', lang)}"
            kb.add(types.InlineKeyboardButton(f"💳 Mensual {format_price(c['monthly_price'])}", callback_data=f"sub_monthly_{target_id}"))
            kb.add(types.InlineKeyboardButton(f"💳 Trimestral {format_price(c['quarterly_price'])}", callback_data=f"sub_quarterly_{target_id}"))
        kb.add(types.InlineKeyboardButton(t("report", lang), callback_data=f"report_{target_id}"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except: pass
    bot.send_message(chat_id, text, reply_markup=kb)

# ==================== VER CONTENIDO (SOLO DENTRO DEL BOT) ====================
@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("viewcontent_"))
def cb_view_content(call):
    parts = call.data.split("_")
    creator_id = int(parts[1])
    offset = int(parts[2]) if len(parts) > 2 else 0
    lang = get_lang(call.from_user.id)

    if not has_active_sub(call.from_user.id, creator_id) and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, t("must_pay", lang), show_alert=True)
        return

    conn = get_db()
    items = conn.execute("""SELECT * FROM content WHERE creator_id=? ORDER BY id DESC LIMIT 5 OFFSET ?""",
                         (creator_id, offset)).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM content WHERE creator_id=?", (creator_id,)).fetchone()[0]
    conn.close()

    if not items:
        bot.answer_callback_query(call.id, t("no_content", lang), show_alert=True)
        return

    bot.answer_callback_query(call.id)
    for item in items:
        caption = f"📸 {item['title'] or 'Contenido'}\n{item['description'] or ''}"
        try:
            if item["media_type"] == "video":
                bot.send_video(call.message.chat.id, item["file_id"], caption=caption,
                               protect_content=True)
            else:
                bot.send_photo(call.message.chat.id, item["file_id"], caption=caption,
                               protect_content=True)
            # Contar vista
            conn = get_db()
            conn.execute("UPDATE content SET views = views + 1 WHERE id=?", (item["id"],))
            conn.commit()
            conn.close()
        except Exception as e:
            bot.send_message(call.message.chat.id, f"Error al cargar contenido #{item['id']}")

    # Navegación
    kb = types.InlineKeyboardMarkup()
    nav = []
    if offset > 0:
        nav.append(types.InlineKeyboardButton("◀ Anterior", callback_data=f"viewcontent_{creator_id}_{max(0, offset-5)}"))
    if offset + 5 < total:
        nav.append(types.InlineKeyboardButton("Siguiente ▶", callback_data=f"viewcontent_{creator_id}_{offset+5}"))
    if nav:
        kb.row(*nav)
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data=f"profile_{creator_id}"))
    bot.send_message(call.message.chat.id,
        f"Mostrando {offset+1}–{min(offset+5, total)} de {total}\n"
        f"<i>El contenido está protegido y solo se ve dentro del bot.</i>",
        reply_markup=kb)

# ==================== EXPLORAR ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_explore")
def cb_explore(call):
    lang = get_lang(call.from_user.id)
    conn = get_db()
    creators = conn.execute("""
        SELECT c.*, u.first_name, u.username, u.gender, u.gender_verified, u.age_verified_real
        FROM creators c JOIN users u ON c.user_id = u.user_id
        WHERE u.creator_verified = 2 AND u.banned = 0
        ORDER BY c.total_subscribers DESC LIMIT 20
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
        kb.add(types.InlineKeyboardButton(f"{name} {badges}", callback_data=f"profile_{c['user_id']}"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

# ==================== PANEL CREADOR: SUBIR CONTENIDO ====================
@bot.callback_query_handler(func=lambda c: c.data == "creator_panel")
def cb_creator_panel(call):
    if not is_creator(call.from_user.id):
        bot.answer_callback_query(call.id, "No eres creador", show_alert=True)
        return
    lang = get_lang(call.from_user.id)
    conn = get_db()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (call.from_user.id,)).fetchone()
    count = conn.execute("SELECT COUNT(*) FROM content WHERE creator_id=?", (call.from_user.id,)).fetchone()[0]
    conn.close()
    text = (
        f"🎨 <b>Panel Creador</b>\n\n"
        f"Suscriptores: {c['total_subscribers']}\n"
        f"Ganancias: {format_price(c['total_earnings'])}\n"
        f"Contenidos subidos: {count}\n\n"
        f"El contenido solo se ve dentro del bot (protegido)."
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Subir foto/vídeo", callback_data="upload_content"))
    kb.add(types.InlineKeyboardButton("📋 Mis contenidos", callback_data="my_contents"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "upload_content")
def cb_upload(call):
    if not is_creator(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        "📸 Envía ahora la <b>foto o vídeo</b> que quieres publicar.\n"
        "Luego podrás poner título (opcional).\n\n"
        "<i>Se guardará y solo los suscriptores lo verán dentro del bot.</i>")
    bot.register_next_step_handler(msg, process_upload_media)

def process_upload_media(message):
    if not is_private_chat(message) or not is_creator(message.from_user.id):
        return
    file_id = None
    media_type = "photo"
    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
    else:
        bot.send_message(message.chat.id, "❌ Envía una foto o un vídeo.")
        return

    # Guardar temporalmente y pedir título
    bot.send_message(message.chat.id, "✅ Media recibido. Ahora escribe un <b>título</b> (o /skip para sin título):")
    bot.register_next_step_handler(message, lambda m: save_content(m, file_id, media_type))

def save_content(message, file_id, media_type):
    title = None if message.text == "/skip" else (message.text or "")[:100]
    conn = get_db()
    conn.execute("""INSERT INTO content (creator_id, title, file_id, media_type, is_premium, created_at)
        VALUES (?, ?, ?, ?, 1, ?)""",
                 (message.from_user.id, title, file_id, media_type, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id,
        f"✅ Contenido publicado.\n"
        f"Tipo: {media_type}\nTítulo: {title or '(sin título)'}\n\n"
        f"Solo tus suscriptores podrán verlo dentro del bot.")

@bot.callback_query_handler(func=lambda c: c.data == "my_contents")
def cb_my_contents(call):
    if not is_creator(call.from_user.id):
        return
    conn = get_db()
    items = conn.execute("SELECT id, title, media_type, views, created_at FROM content WHERE creator_id=? ORDER BY id DESC LIMIT 20",
                         (call.from_user.id,)).fetchall()
    conn.close()
    if not items:
        bot.answer_callback_query(call.id, "No tienes contenidos aún", show_alert=True)
        return
    text = "📋 <b>Tus contenidos</b>\n\n"
    for i in items:
        text += f"#{i['id']} [{i['media_type']}] {i['title'] or 'Sin título'} — {i['views']} vistas\n"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Panel", callback_data="creator_panel"))
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
    text = (f"💳 <b>Suscripción {plan}</b>\n\nPrecio: {format_price(price)}\n\n"
            f"{get_setting('payment_methods')}\n\nEnvía la captura después de pagar.")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Ya pagué", callback_data=f"send_proof_{plan}_{creator_id}"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data=f"profile_{creator_id}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("send_proof_"))
def cb_send_proof(call):
    parts = call.data.split("_")
    plan, creator_id = parts[2], int(parts[3])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📸 Envía la <b>captura del pago</b>.")
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
        VALUES (?,?,?,?,'pending','manual',?,?)""",
                (message.from_user.id, creator_id, f"sub_{plan}", amount, file_id, datetime.now().isoformat()))
    tx_id = cur.lastrowid
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Captura recibida. Esperando al admin.")
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_tx_{tx_id}"),
           types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_tx_{tx_id}"))
    bot.send_photo(ADMIN_ID, file_id,
        caption=f"💳 PAGO\nUser: {message.from_user.id}\nCreator: {creator_id}\n{plan} {format_price(amount)}\nTX #{tx_id}",
        reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("approve_tx_"))
def cb_approve_tx(call):
    if not is_admin(call.from_user.id): return
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
        conn.execute("INSERT OR IGNORE INTO creators (user_id, display_name, bio, created_at) VALUES (?,?,?,?)",
                     (tx["user_id"], f"Creator {tx['user_id']}", "Nuevo creador", now.isoformat()))
        conn.execute("UPDATE transactions SET status='approved', reviewed_at=? WHERE id=?", (now.isoformat(), tx_id))
        conn.commit()
        conn.close()
        bot.send_message(tx["user_id"], "✅ Aprobado como <b>Creador</b>. Ya puedes subir contenido desde el Panel Creador.")
        bot.answer_callback_query(call.id, "Creador aprobado")
        return

    days = 30 if "monthly" in tx["type"] else 90
    end = (now + timedelta(days=days)).isoformat()
    conn.execute("""INSERT OR REPLACE INTO subscriptions
        (user_id, creator_id, plan, amount, status, start_date, end_date, payment_method, created_at)
        VALUES (?,?,?,?,'active',?,?,?,?)""",
                 (tx["user_id"], tx["creator_id"], tx["type"], tx["amount"], now.isoformat(), end, "manual", now.isoformat()))
    conn.execute("UPDATE creators SET total_subscribers=total_subscribers+1, total_earnings=total_earnings+? WHERE user_id=?",
                 (tx["amount"], tx["creator_id"]))
    conn.execute("UPDATE transactions SET status='approved', reviewed_at=? WHERE id=?", (now.isoformat(), tx_id))
    conn.commit()
    conn.close()
    bot.send_message(tx["user_id"],
        f"✅ <b>Pago aprobado</b>\nSuscripción activa hasta {end[:10]}.\n\n"
        f"Ya puedes ver el contenido <b>dentro del bot</b> desde el perfil del creador.")
    bot.answer_callback_query(call.id, "Aprobado")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("reject_tx_"))
def cb_reject_tx(call):
    if not is_admin(call.from_user.id): return
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
    bot.send_message(tx["user_id"], "❌ Pago rechazado.")
    bot.answer_callback_query(call.id, "Rechazado")

# ==================== CUENTA / OTROS MENÚS ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_main")
def cb_menu_main(call):
    send_main_menu(call.message.chat.id, call.from_user.id, call.message.message_id, get_lang(call.from_user.id))
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
    text = (f"👤 <b>Mi Cuenta</b> {badges}\n\n"
            f"ID: <code>{call.from_user.id}</code>\n"
            f"Rol: {user['role'] if user else 'user'}\n"
            f"VIP: {'Sí 👑' if is_vip(call.from_user.id) else 'No'}\n"
            f"Género: {get_gender_text(user, lang)}\n"
            f"Edad verificada: {'Sí' if user and user['age_verified_real']==2 else 'No'}\n")
    kb = types.InlineKeyboardMarkup()
    if not (user and user["age_verified_real"] == 2):
        kb.add(types.InlineKeyboardButton(t("request_verif", lang), web_app=types.WebAppInfo(url=WEBAPP_VERIFICATION_URL)))
    if user and user["creator_verified"] != 2:
        kb.add(types.InlineKeyboardButton("🎨 Ser Creador ($50)", callback_data="become_creator"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "menu_subs")
def cb_subs(call):
    lang = get_lang(call.from_user.id)
    conn = get_db()
    subs = conn.execute("""SELECT s.*, c.display_name FROM subscriptions s
        JOIN creators c ON s.creator_id=c.user_id
        WHERE s.user_id=? AND s.status='active' AND s.end_date>?""",
                        (call.from_user.id, datetime.now().isoformat())).fetchall()
    conn.close()
    text = "No tienes suscripciones." if not subs else "📋 <b>Mis Suscripciones</b>\n\n" + "\n".join(
        f"• {s['display_name']} hasta {s['end_date'][:10]}" for s in subs)
    kb = types.InlineKeyboardMarkup()
    for s in (subs or []):
        kb.add(types.InlineKeyboardButton(f"Ver {s['display_name']}", callback_data=f"viewcontent_{s['creator_id']}_0"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "become_creator")
def cb_become_creator(call):
    lang = get_lang(call.from_user.id)
    text = f"🎨 Ser Creador — {format_price(CREATOR_FEE)}\n\n{get_setting('payment_methods')}"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(f"💸 Ya pagué", callback_data="pay_creator_fee"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="menu_account"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "pay_creator_fee")
def cb_pay_creator_fee(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"📸 Envía captura del pago de ${CREATOR_FEE}.")
    bot.register_next_step_handler(msg, process_creator_fee)

def process_creator_fee(message):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Envía una foto.")
        return
    file_id = message.photo[-1].file_id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO transactions (user_id, type, amount, status, payment_method, screenshot_file_id, created_at)
        VALUES (?,'creator_fee',?,'pending','manual',?,?)""",
                (message.from_user.id, CREATOR_FEE, file_id, datetime.now().isoformat()))
    tx_id = cur.lastrowid
    conn.execute("UPDATE users SET creator_verified=1 WHERE user_id=?", (message.from_user.id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Recibido. Esperando aprobación.")
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_tx_{tx_id}"),
           types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_tx_{tx_id}"))
    bot.send_photo(ADMIN_ID, file_id, caption=f"🎨 CREATOR FEE\nUser: {message.from_user.id}\nTX #{tx_id}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "admin_panel")
def cb_admin_panel(call):
    if not is_admin(call.from_user.id): return
    conn = get_db()
    pending_tx = conn.execute("SELECT COUNT(*) FROM transactions WHERE status='pending'").fetchone()[0]
    pending_ver = conn.execute("SELECT COUNT(*) FROM verifications WHERE status='pending'").fetchone()[0]
    contents = conn.execute("SELECT COUNT(*) FROM content").fetchone()[0]
    conn.close()
    text = (f"🔧 <b>Admin</b>\n\nPagos pendientes: {pending_tx}\n"
            f"Verificaciones: {pending_ver}\nContenidos totales: {contents}\n"
            f"Grupo: {GROUP_INVITE}\nGROUP_ID: {GROUP_ID or 'No config'}")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Menú", callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

# ==================== VERIFICACIÓN ====================
@bot.message_handler(content_types=["web_app_data"])
def handle_webapp(message):
    user_id = message.from_user.id
    conn = get_db()
    conn.execute("INSERT INTO verifications (user_id, status, source, created_at) VALUES (?,'pending','webapp',?)",
                 (user_id, datetime.now().isoformat()))
    conn.execute("UPDATE users SET age_verified_real=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "📸 Datos recibidos. Envía ahora las fotos (documento + selfie).")
    bot.send_message(ADMIN_ID, f"📸 Verificación Mini App — User {user_id}")

@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    if not is_private_chat(message): return
    user = get_user(message.from_user.id)
    if not user or user["age_verified_real"] == 2: return
    file_id = message.photo[-1].file_id
    conn = get_db()
    ver = conn.execute("SELECT * FROM verifications WHERE user_id=? AND status='pending' ORDER BY id DESC LIMIT 1",
                       (message.from_user.id,)).fetchone()
    if not ver:
        cur = conn.cursor()
        cur.execute("INSERT INTO verifications (user_id, doc_photo_id, status, source, created_at) VALUES (?,?, 'pending','manual',?)",
                    (message.from_user.id, file_id, datetime.now().isoformat()))
        conn.execute("UPDATE users SET age_verified_real=1 WHERE user_id=?", (message.from_user.id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "Documento recibido. Envía tu <b>selfie</b>.")
        return
    if not ver["doc_photo_id"]:
        conn.execute("UPDATE verifications SET doc_photo_id=? WHERE id=?", (file_id, ver["id"]))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "Documento recibido. Envía tu <b>selfie</b>.")
        return
    if not ver["selfie_photo_id"]:
        conn.execute("UPDATE verifications SET selfie_photo_id=? WHERE id=?", (file_id, ver["id"]))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ Fotos recibidas. Esperando admin.")
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("♂️ Hombre", callback_data=f"verif_male_{ver['id']}"),
               types.InlineKeyboardButton("♀️ Mujer", callback_data=f"verif_female_{ver['id']}"))
        kb.add(types.InlineKeyboardButton("❌ Rechazar", callback_data=f"verif_reject_{ver['id']}"))
        bot.send_message(ADMIN_ID, f"📸 Verificación — User {message.from_user.id}")
        bot.send_photo(ADMIN_ID, ver["doc_photo_id"] or file_id, caption="Documento")
        bot.send_photo(ADMIN_ID, file_id, caption="Selfie", reply_markup=kb)
        return
    conn.close()

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("verif_"))
def cb_verify(call):
    if not is_admin(call.from_user.id): return
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
    conn.execute("UPDATE users SET age_verified_real=2, gender=?, gender_verified=1 WHERE user_id=?", (gender, ver["user_id"]))
    conn.commit()
    conn.close()
    badge = "♂️" if gender == "male" else "♀️"
    bot.send_message(ver["user_id"], f"✅ Verificación aprobada. Badges: 🔞✅ {badge}")
    bot.answer_callback_query(call.id, "Aprobado")

# ==================== GRUPO (comunidad) ====================
@bot.message_handler(content_types=["new_chat_members"])
def on_new_member(message):
    if GROUP_ID and message.chat.id != GROUP_ID: return
    for m in message.new_chat_members:
        if m.id == bot.get_me().id:
            bot.send_message(message.chat.id, f"✅ Bot añadido.\nPon en main.py:\n<code>GROUP_ID = {message.chat.id}</code>")
            continue
        if m.is_bot: continue
        upsert_user(m)
        bot.send_message(message.chat.id, t("group_welcome", get_lang(tg_user=m), name=m.first_name or "Usuario"))

@bot.message_handler(commands=["ayuda", "help", "comandos"])
def cmd_help_group(message):
    if is_private_chat(message):
        bot.send_message(message.chat.id, t("help_text", get_lang(tg_user=message.from_user)))
        return
    if GROUP_ID and message.chat.id != GROUP_ID: return
    uid = message.from_user.id
    text = ("📜 <b>Comandos del grupo</b>\n\n"
            "/ayuda /reglas /soporte /yo /anuncio\n\n")
    if is_vip(uid):
        text += "👑 VIP: /promo (30 min) /invitar /vip\n\n"
    if is_admin(uid):
        text += "🔧 Admin: /silenciar /activar /broadcast /setanuncio /stats\n"
    bot.reply_to(message, text)

@bot.message_handler(commands=["reglas", "rules"])
def cmd_rules(message):
    if is_private_chat(message): return
    if GROUP_ID and message.chat.id != GROUP_ID: return
    bot.reply_to(message, get_setting("group_rules"))

@bot.message_handler(commands=["soporte", "support"])
def cmd_support(message):
    if GROUP_ID and not is_private_chat(message) and message.chat.id != GROUP_ID: return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Uso: /soporte tu mensaje")
        return
    bot.reply_to(message, "✅ Enviado al soporte.")
    bot.send_message(ADMIN_ID, f"📬 Soporte de {message.from_user.id} (@{message.from_user.username}):\n{parts[1]}")

@bot.message_handler(commands=["yo", "me"])
def cmd_me(message):
    if GROUP_ID and not is_private_chat(message) and message.chat.id != GROUP_ID: return
    upsert_user(message.from_user)
    user = get_user(message.from_user.id)
    bot.reply_to(message, f"👤 <b>{message.from_user.first_name}</b> {get_badges(user)}\nVIP: {'Sí' if is_vip(message.from_user.id) else 'No'}\nRol: {user['role'] if user else 'user'}")

@bot.message_handler(commands=["anuncio"])
def cmd_anuncio(message):
    if GROUP_ID and not is_private_chat(message) and message.chat.id != GROUP_ID: return
    bot.reply_to(message, get_setting("announcement") or "Sin anuncios.")

@bot.message_handler(commands=["promo", "promocionar"])
def cmd_promo(message):
    if is_private_chat(message):
        bot.reply_to(message, "Usa /promo en el <b>grupo</b>.")
        return
    if GROUP_ID and message.chat.id != GROUP_ID: return
    uid = message.from_user.id
    if not is_vip(uid):
        bot.reply_to(message, t("only_vip", get_lang(tg_user=message.from_user)))
        return
    if not is_creator(uid):
        bot.reply_to(message, "Solo creadores pueden promocionar.")
        return
    ok, wait = check_cooldown(uid, "promo")
    if not ok:
        bot.reply_to(message, f"⏳ Espera {wait} minutos.")
        return
    conn = get_db()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (uid,)).fetchone()
    user = get_user(uid)
    conn.close()
    if not c: return
    name = c["display_name"] or message.from_user.first_name
    text = (f"🔥 <b>PROMO CIÓN</b>\n\n🎨 {name} {get_badges(user)}\n"
            f"{c['bio'] or ''}\n💰 {format_price(c['monthly_price'])}/mes\n\n"
            f"➡️ Suscríbete en el bot: /start")
    set_cooldown(uid, "promo")
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["invitar", "invite"])
def cmd_invite(message):
    if is_private_chat(message):
        bot.reply_to(message, "Usa /invitar en el grupo.")
        return
    if GROUP_ID and message.chat.id != GROUP_ID: return
    if not is_vip(message.from_user.id):
        bot.reply_to(message, t("only_vip", get_lang(tg_user=message.from_user)))
        return
    if not is_creator(message.from_user.id):
        bot.reply_to(message, "Solo creadores.")
        return
    me = bot.get_me()
    link = f"https://t.me/{me.username}?start=creator_{message.from_user.id}"
    bot.reply_to(message, f"🔗 Tu enlace:\n{link}")

@bot.message_handler(commands=["vip"])
def cmd_vip(message):
    if not is_vip(message.from_user.id):
        bot.reply_to(message, t("only_vip", get_lang(tg_user=message.from_user)))
        return
    bot.reply_to(message, "👑 Beneficios VIP: /promo cada 30 min, /invitar, badge 👑, acceso prioritario.")

@bot.message_handler(commands=["silenciar", "mute"])
def cmd_mute(message):
    if not is_admin(message.from_user.id): return
    if is_private_chat(message): return
    set_group_setting("muted", "1")
    global group_muted
    group_muted = True
    bot.reply_to(message, "🔇 Grupo silenciado.")

@bot.message_handler(commands=["activar", "unmute"])
def cmd_unmute(message):
    if not is_admin(message.from_user.id): return
    if is_private_chat(message): return
    set_group_setting("muted", "0")
    global group_muted
    group_muted = False
    bot.reply_to(message, "🔉 Grupo activado.")

@bot.message_handler(commands=["broadcast"])
def cmd_broadcast(message):
    if not is_admin(message.from_user.id) or is_private_chat(message): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "/broadcast texto")
        return
    bot.send_message(message.chat.id, f"📢 <b>ANUNCIO</b>\n\n{parts[1]}")

@bot.message_handler(commands=["setanuncio"])
def cmd_setanuncio(message):
    if not is_admin(message.from_user.id): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "/setanuncio texto")
        return
    set_setting("announcement", parts[1])
    bot.reply_to(message, "✅ Anuncio actualizado.")

@bot.message_handler(commands=["stats"])
def cmd_stats(message):
    if not is_admin(message.from_user.id): return
    conn = get_db()
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    vips = conn.execute("SELECT COUNT(DISTINCT user_id) FROM subscriptions WHERE status='active' AND end_date>?",
                        (datetime.now().isoformat(),)).fetchone()[0]
    contents = conn.execute("SELECT COUNT(*) FROM content").fetchone()[0]
    conn.close()
    bot.reply_to(message, f"📊 Usuarios: {users}\nVIP: {vips}\nContenidos: {contents}")

@bot.message_handler(func=lambda m: m.chat.type in ("group", "supergroup") and is_group_muted() and not is_admin(m.from_user.id),
                     content_types=["text", "photo", "video", "sticker", "animation", "voice", "document"])
def filter_muted(message):
    if GROUP_ID and message.chat.id != GROUP_ID: return
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

# ==================== ARRANQUE ====================
if __name__ == "__main__":
    init_db()
    global group_muted
    group_muted = is_group_muted()
    print("OnlyFans_ManagerBot V7 started")
    print(f"Admin: {ADMIN_ID} | GROUP_ID: {GROUP_ID}")
    print("Contenido: SOLO dentro del bot (protect_content)")
    bot.infinity_polling()
