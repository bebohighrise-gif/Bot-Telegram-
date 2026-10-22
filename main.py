#!/usr/bin/env python3
"""
OnlyFans_ManagerBot - V8
- Todos tienen perfil (buscable)
- Solo creadores (pagaron $50) pueden publicar fotos/vídeos
- Planes flexibles: pack fotos, mensual, trimestral, videollamada, custom
- Likes / No me gusta / Comentarios en cada contenido
- Máxima protección: protect_content (no reenviar, difícil guardar)
- Grupo comunidad + VIP + admin
"""

import telebot
from telebot import types
import sqlite3
import json
from datetime import datetime, timedelta

TELEGRAM_TOKEN = "PON_AQUI_TU_TOKEN"
ADMIN_ID = 7653419875
GROUP_ID = None
GROUP_INVITE = "https://t.me/+oMkBHSWhjf5lNTZh"
CREATOR_FEE = 50.0
PROMO_COOLDOWN_MINUTES = 30
WEBAPP_VERIFICATION_URL = "https://TU_DOMINIO.com/verification.html"
DB_FILE = "bot.db"

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")
group_muted = False

# Tipos de plan disponibles
PLAN_TYPES = {
    "pack3": {"name": "Pack 3 fotos", "default_price": 4.99, "days": 0, "credits": 3},
    "pack10": {"name": "Pack 10 fotos", "default_price": 12.99, "days": 0, "credits": 10},
    "monthly": {"name": "Mensual (ilimitado)", "default_price": 9.99, "days": 30, "credits": 0},
    "quarterly": {"name": "Trimestral (ilimitado)", "default_price": 24.99, "days": 90, "credits": 0},
    "videocall": {"name": "Videollamada", "default_price": 29.99, "days": 0, "credits": 0},
    "custom": {"name": "Personalizado", "default_price": 0, "days": 0, "credits": 0},
}

TEXTS = {
    "es": {
        "welcome": "💖 <b>Bienvenido/a, {name}</b>\n\nContenido exclusivo <b>solo dentro del bot</b>.\nElige una opción:",
        "age_title": "🔒 <b>Confirmación de Edad</b>",
        "age_text": "Contenido para adultos. ¿Eres <b>mayor de 18</b>?",
        "age_yes": "✅ Sí, mayor de 18",
        "age_no": "❌ Soy menor",
        "age_denied": "🚫 Solo mayores de 18.",
        "terms_accept": "✅ Acepto",
        "terms_deny": "❌ No acepto",
        "terms_must": "Debes aceptar los términos.",
        "menu_explore": "🔍 Explorar",
        "menu_search": "🔎 Buscar",
        "menu_subs": "📋 Mis planes",
        "menu_account": "👤 Mi perfil",
        "menu_help": "❓ Ayuda",
        "menu_creator": "🎨 Panel Creador",
        "menu_admin": "🔧 Admin",
        "back": "« Volver",
        "back_menu": "« Menú",
        "must_pay": "🔒 Necesitas un plan activo para ver este contenido.",
        "has_sub": "✅ Tienes acceso",
        "view_content": "📸 Ver contenido",
        "no_content": "Sin contenido aún.",
        "report": "📢 Reportar",
        "request_verif": "📸 Verificar con cámara",
        "banned": "🚫 Cuenta baneada.",
        "no_creators": "Aún no hay creadores.",
        "search_prompt": "🔎 Escribe nombre o @usuario:",
        "search_empty": "Sin resultados.",
        "group_welcome": "👋 Bienvenido/a, {name}! /ayuda · Regístrate en privado: /start",
        "use_private": "⚠️ Usa en <b>chat privado</b>.",
        "only_vip": "👑 Solo VIP.",
        "only_admin": "🔒 Solo admin.",
        "only_creator": "🎨 Solo creadores.",
        "help_text": (
            "❓ <b>Ayuda</b>\n\n"
            "• Todos tienen perfil (buscable).\n"
            "• Solo <b>creadores</b> (pagan $50) publican fotos/vídeos.\n"
            "• Planes: packs de fotos, mensual, videollamada...\n"
            "• Contenido protegido (no reenviar fácilmente).\n"
            "• Puedes dar like, dislike y comentar."
        ),
    },
    "en": {
        "welcome": "💖 <b>Welcome, {name}</b>\n\nExclusive content <b>only inside the bot</b>.",
        "age_title": "🔒 <b>Age Confirmation</b>",
        "age_text": "Adult content. Are you <b>over 18</b>?",
        "age_yes": "✅ Yes, over 18",
        "age_no": "❌ Underage",
        "age_denied": "🚫 Adults only.",
        "terms_accept": "✅ I accept",
        "terms_deny": "❌ I do not accept",
        "terms_must": "Accept the terms.",
        "menu_explore": "🔍 Explore",
        "menu_search": "🔎 Search",
        "menu_subs": "📋 My plans",
        "menu_account": "👤 My profile",
        "menu_help": "❓ Help",
        "menu_creator": "🎨 Creator Panel",
        "menu_admin": "🔧 Admin",
        "back": "« Back",
        "back_menu": "« Menu",
        "must_pay": "🔒 You need an active plan.",
        "has_sub": "✅ You have access",
        "view_content": "📸 View content",
        "no_content": "No content yet.",
        "report": "📢 Report",
        "request_verif": "📸 Camera verification",
        "banned": "🚫 Banned.",
        "no_creators": "No creators yet.",
        "search_prompt": "🔎 Type name or @username:",
        "search_empty": "No results.",
        "group_welcome": "👋 Welcome, {name}! /help · Register in private: /start",
        "use_private": "⚠️ Use in <b>private chat</b>.",
        "only_vip": "👑 VIP only.",
        "only_admin": "🔒 Admin only.",
        "only_creator": "🎨 Creators only.",
        "help_text": "❓ Help\n\n• Everyone has a profile.\n• Only creators publish.\n• Flexible plans.\n• Protected content.\n• Likes & comments.",
    }
}

def get_lang(user_id=None, tg_user=None):
    if tg_user and getattr(tg_user, "language_code", None):
        return "es" if tg_user.language_code.lower().startswith("es") else "en"
    if user_id:
        u = get_user(user_id)
        if u and u["language"] in ("es", "en"): return u["language"]
    return "es"

def t(key, lang="es", **kwargs):
    text = TEXTS.get(lang, TEXTS["es"]).get(key, TEXTS["es"].get(key, key))
    try: return text.format(**kwargs) if kwargs else text
    except: return text

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
        bio TEXT DEFAULT '', joined_at TEXT, last_active TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS creators (
        user_id INTEGER PRIMARY KEY, display_name TEXT, bio TEXT,
        total_subscribers INTEGER DEFAULT 0, total_earnings REAL DEFAULT 0,
        created_at TEXT)""")
    # Planes que ofrece cada creador
    c.execute("""CREATE TABLE IF NOT EXISTS creator_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id INTEGER,
        plan_type TEXT, name TEXT, price REAL, days INTEGER DEFAULT 0,
        credits INTEGER DEFAULT 0, description TEXT, active INTEGER DEFAULT 1)""")
    # Compras / suscripciones del usuario
    c.execute("""CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, creator_id INTEGER,
        plan_id INTEGER, plan_type TEXT, amount REAL, status TEXT DEFAULT 'active',
        start_date TEXT, end_date TEXT, credits_left INTEGER DEFAULT 0,
        payment_method TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS content (
        id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id INTEGER, title TEXT,
        description TEXT, file_id TEXT, media_type TEXT DEFAULT 'photo',
        is_premium INTEGER DEFAULT 1, views INTEGER DEFAULT 0,
        likes INTEGER DEFAULT 0, dislikes INTEGER DEFAULT 0, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS reactions (
        user_id INTEGER, content_id INTEGER, reaction TEXT,
        PRIMARY KEY (user_id, content_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, content_id INTEGER, user_id INTEGER,
        text TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, creator_id INTEGER,
        type TEXT, amount REAL, status TEXT DEFAULT 'pending',
        payment_method TEXT, screenshot_file_id TEXT, plan_id INTEGER,
        created_at TEXT, reviewed_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        doc_photo_id TEXT, selfie_photo_id TEXT, status TEXT DEFAULT 'pending',
        assigned_gender TEXT, source TEXT DEFAULT 'manual',
        created_at TEXT, reviewed_at TEXT, reviewed_by INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER, reported_id INTEGER,
        reason TEXT, status TEXT DEFAULT 'open', created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, action TEXT,
        target_id INTEGER, details TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS cooldowns (
        user_id INTEGER, command TEXT, last_used TEXT, PRIMARY KEY (user_id, command))""")
    c.execute("""CREATE TABLE IF NOT EXISTS group_settings (key TEXT PRIMARY KEY, value TEXT)""")

    defaults = {
        "payment_methods": "💳 <b>Formas de pago:</b>\n\n• Transferencia / Bizum\n• Crypto (USDT/BTC)\n• Telegram Stars\n\n<i>El admin actualiza los datos.</i>",
        "terms": "📜 <b>Términos</b>\n1. +18.\n2. Uso personal.\n3. Prohibida redistribución.\n4. Ban por incumplimientos.",
        "group_rules": "📜 <b>Reglas</b>\n1. Respeta.\n2. No spam.\n3. /promo cada 30 min (VIP).\n4. /soporte.\n5. Admin puede silenciar.",
        "announcement": "📢 Contenido solo dentro del bot. Usa /ayuda."
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
    conn.execute("UPDATE users SET role='admin', age_declared=1, terms_accepted=1, age_verified_real=2, gender_verified=1, creator_verified=2 WHERE user_id=?", (ADMIN_ID,))
    conn.execute("INSERT OR IGNORE INTO creators (user_id, display_name, bio, created_at) VALUES (?, 'Admin Principal', 'Creador principal', ?)", (ADMIN_ID, now))
    # Planes por defecto del admin
    if not conn.execute("SELECT 1 FROM creator_plans WHERE creator_id=?", (ADMIN_ID,)).fetchone():
        for ptype, info in PLAN_TYPES.items():
            if ptype == "custom": continue
            conn.execute("INSERT INTO creator_plans (creator_id, plan_type, name, price, days, credits, description) VALUES (?,?,?,?,?,?,?)",
                         (ADMIN_ID, ptype, info["name"], info["default_price"], info["days"], info["credits"], info["name"]))
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
    row = conn.execute("""SELECT 1 FROM subscriptions WHERE user_id=? AND status='active'
        AND (end_date > ? OR credits_left > 0)""", (uid, datetime.now().isoformat())).fetchone()
    conn.close()
    return bool(row)
def format_price(p): return f"${p:.2f}"

def has_access(user_id, creator_id):
    """Tiene acceso ilimitado o créditos de pack"""
    if is_admin(user_id): return True
    conn = get_db()
    row = conn.execute("""SELECT * FROM subscriptions WHERE user_id=? AND creator_id=? AND status='active'
        AND (end_date > ? OR credits_left > 0) ORDER BY id DESC LIMIT 1""",
                       (user_id, creator_id, datetime.now().isoformat())).fetchone()
    conn.close()
    return bool(row)

def consume_credit(user_id, creator_id):
    """Gasta 1 crédito de pack si aplica. Devuelve True si podía ver."""
    if is_admin(user_id): return True
    conn = get_db()
    row = conn.execute("""SELECT * FROM subscriptions WHERE user_id=? AND creator_id=? AND status='active'
        AND (end_date > ? OR credits_left > 0) ORDER BY id DESC LIMIT 1""",
                       (user_id, creator_id, datetime.now().isoformat())).fetchone()
    if not row:
        conn.close()
        return False
    if row["credits_left"] and row["credits_left"] > 0:
        conn.execute("UPDATE subscriptions SET credits_left = credits_left - 1 WHERE id=?", (row["id"],))
        conn.commit()
    conn.close()
    return True

def get_badges(user):
    if not user: return ""
    badges = []
    if user["age_verified_real"] == 2: badges.append("🔞✅")
    if user["gender_verified"] and user["gender"]:
        badges.append("♂️" if user["gender"] == "male" else "♀️")
    if is_vip(user["user_id"]): badges.append("👑")
    if is_creator(user["user_id"]): badges.append("🎨")
    return " ".join(badges)

def get_gender_text(user, lang="es"):
    if not user or not user["gender_verified"]: return "No verificado"
    return "Masculino" if user["gender"] == "male" else "Femenino"

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
    kb.add(types.InlineKeyboardButton(t("menu_explore", lang), callback_data="menu_explore"),
           types.InlineKeyboardButton(t("menu_search", lang), callback_data="menu_search"))
    kb.add(types.InlineKeyboardButton(t("menu_subs", lang), callback_data="menu_subs"),
           types.InlineKeyboardButton(t("menu_account", lang), callback_data="menu_account"))
    kb.add(types.InlineKeyboardButton(t("menu_help", lang), callback_data="menu_help"))
    if is_creator(user_id):
        kb.add(types.InlineKeyboardButton(t("menu_creator", lang), callback_data="creator_panel"))
    if is_admin(user_id):
        kb.add(types.InlineKeyboardButton(t("menu_admin", lang), callback_data="admin_panel"))
    return kb

def send_main_menu(chat_id, user_id, message_id=None, lang=None):
    user = get_user(user_id)
    lang = lang or (user["language"] if user else "es")
    text = t("welcome", lang, name=user["first_name"] if user else "User")
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
    if message.text and "creator_" in message.text:
        try:
            cid = int(message.text.split("creator_")[1].split()[0])
            upsert_user(message.from_user)
            show_profile(message.chat.id, message.from_user.id, cid)
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

# ==================== BUSCADOR (TODOS LOS PERFILES) ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_search")
def cb_search(call):
    lang = get_lang(call.from_user.id)
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, t("search_prompt", lang))
    bot.register_next_step_handler(msg, process_search)

def process_search(message):
    if not is_private_chat(message): return
    lang = get_lang(message.from_user.id, message.from_user)
    q = (message.text or "").strip().lstrip("@").lower()
    if len(q) < 2:
        bot.send_message(message.chat.id, "Mínimo 2 caracteres.")
        return
    conn = get_db()
    results = conn.execute("""
        SELECT u.user_id, u.username, u.first_name, u.role, u.gender, u.gender_verified,
               u.age_verified_real, u.bio, c.display_name
        FROM users u LEFT JOIN creators c ON u.user_id = c.user_id
        WHERE u.banned=0 AND (LOWER(IFNULL(u.username,'')) LIKE ? OR LOWER(IFNULL(u.first_name,'')) LIKE ?
            OR LOWER(IFNULL(c.display_name,'')) LIKE ? OR LOWER(IFNULL(u.bio,'')) LIKE ?)
        LIMIT 15""", (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    conn.close()
    if not results:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
        bot.send_message(message.chat.id, t("search_empty", lang), reply_markup=kb)
        return
    text = f"🔎 <b>Resultados</b> ({len(results)}):\n\n"
    kb = types.InlineKeyboardMarkup()
    for r in results:
        name = r["display_name"] or r["first_name"] or r["username"] or str(r["user_id"])
        badges = get_badges(r)
        icon = "🎨" if is_creator(r["user_id"]) else "👤"
        text += f"• {icon} {name} {badges}\n"
        kb.add(types.InlineKeyboardButton(f"{icon} {name} {badges}"[:60], callback_data=f"profile_{r['user_id']}"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("profile_"))
def cb_profile(call):
    show_profile(call.message.chat.id, call.from_user.id, int(call.data.split("_")[1]), call.message.message_id)
    bot.answer_callback_query(call.id)

def show_profile(chat_id, viewer_id, target_id, message_id=None):
    lang = get_lang(viewer_id)
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (target_id,)).fetchone()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (target_id,)).fetchone()
    content_count = conn.execute("SELECT COUNT(*) FROM content WHERE creator_id=?", (target_id,)).fetchone()[0]
    plans = conn.execute("SELECT * FROM creator_plans WHERE creator_id=? AND active=1", (target_id,)).fetchall()
    conn.close()
    if not u:
        bot.send_message(chat_id, "Usuario no encontrado.")
        return

    badges = get_badges(u)
    name = (c["display_name"] if c else None) or u["first_name"] or "Usuario"
    is_cre = is_creator(target_id)

    text = f"{'\ud83c\udfa8' if is_cre else '\ud83d\udc64'} <b>{name}</b> {badges}\n"
    if u["username"]: text += f"@{u['username']}\n"
    text += f"Género: {get_gender_text(u, lang)}\n"
    bio = (c["bio"] if c and c["bio"] else u["bio"]) or ""
    if bio: text += f"\n{bio}\n"

    kb = types.InlineKeyboardMarkup()
    if is_cre:
        text += f"\n📸 Contenidos: {content_count}\n👥 Suscriptores: {c['total_subscribers'] if c else 0}\n"
        if plans:
            text += "\n<b>Planes disponibles:</b>\n"
            for p in plans:
                text += f"• {p['name']} — {format_price(p['price'])}\n"
                kb.add(types.InlineKeyboardButton(
                    f"💳 {p['name']} {format_price(p['price'])}",
                    callback_data=f"buyplan_{p['id']}"
                ))
        if has_access(viewer_id, target_id):
            text += f"\n{t('has_sub', lang)}"
            kb.add(types.InlineKeyboardButton(t("view_content", lang), callback_data=f"viewcontent_{target_id}_0"))
        else:
            text += f"\n{t('must_pay', lang)}"
        kb.add(types.InlineKeyboardButton(t("report", lang), callback_data=f"report_{target_id}"))
    else:
        text += "\n<i>Perfil de usuario (no es creador).</i>"

    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except: pass
    bot.send_message(chat_id, text, reply_markup=kb)

# ==================== COMPRAR PLAN ====================
@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("buyplan_"))
def cb_buy_plan(call):
    plan_id = int(call.data.split("_")[1])
    lang = get_lang(call.from_user.id)
    conn = get_db()
    p = conn.execute("SELECT * FROM creator_plans WHERE id=? AND active=1", (plan_id,)).fetchone()
    conn.close()
    if not p:
        bot.answer_callback_query(call.id, "Plan no disponible", show_alert=True)
        return
    text = (f"💳 <b>{p['name']}</b>\n\n"
            f"Precio: {format_price(p['price'])}\n"
            f"{p['description'] or ''}\n\n"
            f"{get_setting('payment_methods')}\n\nEnvía la captura tras pagar.")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Ya pagué", callback_data=f"proofplan_{plan_id}"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data=f"profile_{p['creator_id']}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("proofplan_"))
def cb_proof_plan(call):
    plan_id = int(call.data.split("_")[1])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📸 Envía la <b>captura del pago</b>.")
    bot.register_next_step_handler(msg, lambda m: process_plan_proof(m, plan_id))

def process_plan_proof(message, plan_id):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Envía una foto.")
        return
    file_id = message.photo[-1].file_id
    conn = get_db()
    p = conn.execute("SELECT * FROM creator_plans WHERE id=?", (plan_id,)).fetchone()
    if not p:
        conn.close()
        bot.send_message(message.chat.id, "Plan no encontrado.")
        return
    cur = conn.cursor()
    cur.execute("""INSERT INTO transactions (user_id, creator_id, type, amount, status, payment_method, screenshot_file_id, plan_id, created_at)
        VALUES (?,?,?,?, 'pending','manual',?,?,?)""",
                (message.from_user.id, p["creator_id"], f"plan_{p['plan_type']}", p["price"], file_id, plan_id, datetime.now().isoformat()))
    tx_id = cur.lastrowid
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Captura recibida. Esperando al admin.")
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_tx_{tx_id}"),
           types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_tx_{tx_id}"))
    bot.send_photo(ADMIN_ID, file_id,
        caption=f"💳 PLAN\nUser: {message.from_user.id}\nCreator: {p['creator_id']}\n{p['name']} {format_price(p['price'])}\nTX #{tx_id}",
        reply_markup=kb)

# ==================== VER CONTENIDO + LIKES/COMENTARIOS ====================
@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("viewcontent_"))
def cb_view_content(call):
    parts = call.data.split("_")
    creator_id, offset = int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
    lang = get_lang(call.from_user.id)
    if not has_access(call.from_user.id, creator_id):
        bot.answer_callback_query(call.id, t("must_pay", lang), show_alert=True)
        return
    conn = get_db()
    items = conn.execute("SELECT * FROM content WHERE creator_id=? ORDER BY id DESC LIMIT 1 OFFSET ?",
                         (creator_id, offset)).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM content WHERE creator_id=?", (creator_id,)).fetchone()[0]
    conn.close()
    if not items:
        bot.answer_callback_query(call.id, t("no_content", lang), show_alert=True)
        return
    item = items[0]
    # Consumir crédito si es pack
    if not consume_credit(call.from_user.id, creator_id):
        bot.answer_callback_query(call.id, "Sin créditos restantes.", show_alert=True)
        return
    bot.answer_callback_query(call.id)

    caption = (f"📸 {item['title'] or 'Contenido'}\n{item['description'] or ''}\n\n"
               f"❤️ {item['likes']}  💔 {item['dislikes']}  👁 {item['views']}\n"
               f"<i>🔒 Protegido · No reenviar</i>")
    try:
        if item["media_type"] == "video":
            sent = bot.send_video(call.message.chat.id, item["file_id"], caption=caption, protect_content=True)
        else:
            sent = bot.send_photo(call.message.chat.id, item["file_id"], caption=caption, protect_content=True)
    except:
        bot.send_message(call.message.chat.id, "Error al cargar.")
        return

    conn = get_db()
    conn.execute("UPDATE content SET views = views + 1 WHERE id=?", (item["id"],))
    conn.commit()
    conn.close()

    # Botones de reacción y navegación
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.row(
        types.InlineKeyboardButton(f"❤️ {item['likes']}", callback_data=f"like_{item['id']}"),
        types.InlineKeyboardButton(f"💔 {item['dislikes']}", callback_data=f"dislike_{item['id']}"),
        types.InlineKeyboardButton("💬 Comentar", callback_data=f"comment_{item['id']}")
    )
    nav = []
    if offset > 0:
        nav.append(types.InlineKeyboardButton("◀", callback_data=f"viewcontent_{creator_id}_{offset-1}"))
    if offset + 1 < total:
        nav.append(types.InlineKeyboardButton("▶", callback_data=f"viewcontent_{creator_id}_{offset+1}"))
    if nav: kb.row(*nav)
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data=f"profile_{creator_id}"))
    bot.send_message(call.message.chat.id, f"{offset+1}/{total}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("like_"))
def cb_like(call):
    cid = int(call.data.split("_")[1])
    uid = call.from_user.id
    conn = get_db()
    prev = conn.execute("SELECT reaction FROM reactions WHERE user_id=? AND content_id=?", (uid, cid)).fetchone()
    if prev and prev["reaction"] == "like":
        bot.answer_callback_query(call.id, "Ya diste like")
        conn.close()
        return
    if prev and prev["reaction"] == "dislike":
        conn.execute("UPDATE content SET dislikes = dislikes - 1, likes = likes + 1 WHERE id=?", (cid,))
        conn.execute("UPDATE reactions SET reaction='like' WHERE user_id=? AND content_id=?", (uid, cid))
    else:
        conn.execute("UPDATE content SET likes = likes + 1 WHERE id=?", (cid,))
        conn.execute("INSERT OR REPLACE INTO reactions (user_id, content_id, reaction) VALUES (?,?,'like')", (uid, cid))
    conn.commit()
    row = conn.execute("SELECT likes, dislikes FROM content WHERE id=?", (cid,)).fetchone()
    conn.close()
    bot.answer_callback_query(call.id, f"❤️ {row['likes']}  💔 {row['dislikes']}")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("dislike_"))
def cb_dislike(call):
    cid = int(call.data.split("_")[1])
    uid = call.from_user.id
    conn = get_db()
    prev = conn.execute("SELECT reaction FROM reactions WHERE user_id=? AND content_id=?", (uid, cid)).fetchone()
    if prev and prev["reaction"] == "dislike":
        bot.answer_callback_query(call.id, "Ya diste dislike")
        conn.close()
        return
    if prev and prev["reaction"] == "like":
        conn.execute("UPDATE content SET likes = likes - 1, dislikes = dislikes + 1 WHERE id=?", (cid,))
        conn.execute("UPDATE reactions SET reaction='dislike' WHERE user_id=? AND content_id=?", (uid, cid))
    else:
        conn.execute("UPDATE content SET dislikes = dislikes + 1 WHERE id=?", (cid,))
        conn.execute("INSERT OR REPLACE INTO reactions (user_id, content_id, reaction) VALUES (?,?,'dislike')", (uid, cid))
    conn.commit()
    row = conn.execute("SELECT likes, dislikes FROM content WHERE id=?", (cid,)).fetchone()
    conn.close()
    bot.answer_callback_query(call.id, f"❤️ {row['likes']}  💔 {row['dislikes']}")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("comment_"))
def cb_comment(call):
    cid = int(call.data.split("_")[1])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "💬 Escribe tu comentario:")
    bot.register_next_step_handler(msg, lambda m: save_comment(m, cid))

def save_comment(message, content_id):
    if not message.text: return
    text = message.text[:300]
    conn = get_db()
    conn.execute("INSERT INTO comments (content_id, user_id, text, created_at) VALUES (?,?,?,?)",
                 (content_id, message.from_user.id, text, datetime.now().isoformat()))
    # Notificar al creador
    item = conn.execute("SELECT creator_id, title FROM content WHERE id=?", (content_id,)).fetchone()
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Comentario publicado.")
    if item:
        try:
            bot.send_message(item["creator_id"],
                f"💬 Nuevo comentario en «{item['title'] or 'contenido'}»\n"
                f"De: {message.from_user.first_name}\n{text}")
        except: pass

# ==================== EXPLORAR ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_explore")
def cb_explore(call):
    lang = get_lang(call.from_user.id)
    conn = get_db()
    creators = conn.execute("""SELECT c.*, u.first_name, u.username, u.gender, u.gender_verified, u.age_verified_real
        FROM creators c JOIN users u ON c.user_id=u.user_id
        WHERE u.creator_verified=2 AND u.banned=0 ORDER BY c.total_subscribers DESC LIMIT 20""").fetchall()
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
        name = c["display_name"] or c["first_name"]
        text += f"• {name} {badges}\n"
        kb.add(types.InlineKeyboardButton(f"{name} {badges}", callback_data=f"profile_{c['user_id']}"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

# ==================== PANEL CREADOR ====================
@bot.callback_query_handler(func=lambda c: c.data == "creator_panel")
def cb_creator_panel(call):
    if not is_creator(call.from_user.id):
        bot.answer_callback_query(call.id, "No eres creador", show_alert=True)
        return
    lang = get_lang(call.from_user.id)
    conn = get_db()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (call.from_user.id,)).fetchone()
    count = conn.execute("SELECT COUNT(*) FROM content WHERE creator_id=?", (call.from_user.id,)).fetchone()[0]
    plans = conn.execute("SELECT COUNT(*) FROM creator_plans WHERE creator_id=? AND active=1", (call.from_user.id,)).fetchone()[0]
    conn.close()
    text = (f"🎨 <b>Panel Creador</b>\n\n"
            f"Suscriptores: {c['total_subscribers']}\n"
            f"Ganancias: {format_price(c['total_earnings'])}\n"
            f"Contenidos: {count}\nPlanes activos: {plans}\n\n"
            f"El contenido se protege automáticamente (no reenviar).")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Subir foto/vídeo", callback_data="upload_content"))
    kb.add(types.InlineKeyboardButton("📋 Mis contenidos", callback_data="my_contents"))
    kb.add(types.InlineKeyboardButton("💰 Gestionar planes", callback_data="manage_plans"))
    kb.add(types.InlineKeyboardButton("✏️ Editar bio/nombre", callback_data="edit_creator_profile"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "upload_content")
def cb_upload(call):
    if not is_creator(call.from_user.id): return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        "📸 Envía la <b>foto o vídeo</b>.\nSe publicará protegido (protect_content).\nLuego podrás poner título.")
    bot.register_next_step_handler(msg, process_upload_media)

def process_upload_media(message):
    if not is_private_chat(message) or not is_creator(message.from_user.id): return
    file_id, media_type = None, "photo"
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
    else:
        bot.send_message(message.chat.id, "❌ Envía foto o vídeo.")
        return
    bot.send_message(message.chat.id, "Escribe un <b>título</b> (o /skip):")
    bot.register_next_step_handler(message, lambda m: save_content(m, file_id, media_type))

def save_content(message, file_id, media_type):
    title = None if message.text == "/skip" else (message.text or "")[:100]
    conn = get_db()
    conn.execute("""INSERT INTO content (creator_id, title, file_id, media_type, is_premium, created_at)
        VALUES (?,?,?,?,1,?)""", (message.from_user.id, title, file_id, media_type, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ Publicado ({media_type}).\nTítulo: {title or '(sin)'}\n🔒 Protegido contra reenvío.")

@bot.callback_query_handler(func=lambda c: c.data == "my_contents")
def cb_my_contents(call):
    if not is_creator(call.from_user.id): return
    conn = get_db()
    items = conn.execute("SELECT id, title, media_type, views, likes, dislikes FROM content WHERE creator_id=? ORDER BY id DESC LIMIT 20",
                         (call.from_user.id,)).fetchall()
    conn.close()
    if not items:
        bot.answer_callback_query(call.id, "Sin contenidos", show_alert=True)
        return
    text = "📋 <b>Tus contenidos</b>\n\n"
    for i in items:
        text += f"#{i['id']} [{i['media_type']}] {i['title'] or '-'} — 👁{i['views']} ❤️{i['likes']} 💔{i['dislikes']}\n"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Panel", callback_data="creator_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "manage_plans")
def cb_manage_plans(call):
    if not is_creator(call.from_user.id): return
    conn = get_db()
    plans = conn.execute("SELECT * FROM creator_plans WHERE creator_id=?", (call.from_user.id,)).fetchall()
    conn.close()
    text = "💰 <b>Tus planes</b>\n\n"
    kb = types.InlineKeyboardMarkup()
    for p in plans:
        status = "✅" if p["active"] else "❌"
        text += f"{status} {p['name']} — {format_price(p['price'])}\n"
    kb.add(types.InlineKeyboardButton("➕ Añadir plan", callback_data="add_plan"))
    kb.add(types.InlineKeyboardButton("« Panel", callback_data="creator_panel"))
    bot.edit_message_text(text or "Sin planes.", call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "add_plan")
def cb_add_plan(call):
    if not is_creator(call.from_user.id): return
    kb = types.InlineKeyboardMarkup()
    for ptype, info in PLAN_TYPES.items():
        if ptype == "custom": continue
        kb.add(types.InlineKeyboardButton(f"{info['name']} ({format_price(info['default_price'])})",
                                          callback_data=f"newplan_{ptype}"))
    kb.add(types.InlineKeyboardButton("« Volver", callback_data="manage_plans"))
    bot.edit_message_text("Elige tipo de plan:", call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("newplan_"))
def cb_new_plan(call):
    if not is_creator(call.from_user.id): return
    ptype = call.data.split("_")[1]
    info = PLAN_TYPES.get(ptype)
    if not info: return
    conn = get_db()
    conn.execute("""INSERT INTO creator_plans (creator_id, plan_type, name, price, days, credits, description)
        VALUES (?,?,?,?,?,?,?)""",
                 (call.from_user.id, ptype, info["name"], info["default_price"], info["days"], info["credits"], info["name"]))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, f"Plan {info['name']} añadido")
    # Volver a manage
    call.data = "manage_plans"
    cb_manage_plans(call)

@bot.callback_query_handler(func=lambda c: c.data == "edit_creator_profile")
def cb_edit_creator(call):
    if not is_creator(call.from_user.id): return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Escribe tu nueva <b>bio</b> (máx 200 caracteres):")
    bot.register_next_step_handler(msg, save_creator_bio)

def save_creator_bio(message):
    if not is_creator(message.from_user.id): return
    bio = (message.text or "")[:200]
    conn = get_db()
    conn.execute("UPDATE creators SET bio=? WHERE user_id=?", (bio, message.from_user.id))
    conn.execute("UPDATE users SET bio=? WHERE user_id=?", (bio, message.from_user.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Bio actualizada.")

# ==================== APROBAR / RECHAZAR PAGOS ====================
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
        # Planes por defecto
        for ptype, info in PLAN_TYPES.items():
            if ptype == "custom": continue
            conn.execute("INSERT INTO creator_plans (creator_id, plan_type, name, price, days, credits, description) VALUES (?,?,?,?,?,?,?)",
                         (tx["user_id"], ptype, info["name"], info["default_price"], info["days"], info["credits"], info["name"]))
        conn.execute("UPDATE transactions SET status='approved', reviewed_at=? WHERE id=?", (now.isoformat(), tx_id))
        conn.commit()
        conn.close()
        bot.send_message(tx["user_id"], "✅ ¡Eres <b>Creador</b>! Ya puedes subir contenido y gestionar planes.")
        bot.answer_callback_query(call.id, "Creador aprobado")
        return

    # Plan normal
    plan = None
    if tx["plan_id"]:
        plan = conn.execute("SELECT * FROM creator_plans WHERE id=?", (tx["plan_id"],)).fetchone()
    days = plan["days"] if plan else 30
    credits = plan["credits"] if plan else 0
    end = (now + timedelta(days=days)).isoformat() if days > 0 else now.isoformat()
    conn.execute("""INSERT INTO subscriptions
        (user_id, creator_id, plan_id, plan_type, amount, status, start_date, end_date, credits_left, payment_method, created_at)
        VALUES (?,?,?,?,?,'active',?,?,?,?,?)""",
                 (tx["user_id"], tx["creator_id"], tx["plan_id"], tx["type"], tx["amount"],
                  now.isoformat(), end, credits, "manual", now.isoformat()))
    conn.execute("UPDATE creators SET total_subscribers=total_subscribers+1, total_earnings=total_earnings+? WHERE user_id=?",
                 (tx["amount"], tx["creator_id"]))
    conn.execute("UPDATE transactions SET status='approved', reviewed_at=? WHERE id=?", (now.isoformat(), tx_id))
    conn.commit()
    conn.close()
    extra = f"Créditos: {credits}" if credits else f"Hasta: {end[:10]}"
    bot.send_message(tx["user_id"], f"✅ <b>Pago aprobado</b>\n{extra}\nYa puedes ver el contenido dentro del bot.")
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

# ==================== CUENTA / OTROS ====================
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
    text = (f"👤 <b>Mi perfil</b> {badges}\n\n"
            f"ID: <code>{call.from_user.id}</code>\n"
            f"Rol: {user['role'] if user else 'user'}\n"
            f"VIP: {'Sí 👑' if is_vip(call.from_user.id) else 'No'}\n"
            f"Género: {get_gender_text(user, lang)}\n"
            f"Verificado: {'Sí' if user and user['age_verified_real']==2 else 'No'}\n")
    kb = types.InlineKeyboardMarkup()
    if not (user and user["age_verified_real"] == 2):
        kb.add(types.InlineKeyboardButton(t("request_verif", lang), web_app=types.WebAppInfo(url=WEBAPP_VERIFICATION_URL)))
    if user and user["creator_verified"] != 2:
        kb.add(types.InlineKeyboardButton("🎨 Ser Creador ($50)", callback_data="become_creator"))
    kb.add(types.InlineKeyboardButton("Ver mi perfil público", callback_data=f"profile_{call.from_user.id}"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "menu_subs")
def cb_subs(call):
    lang = get_lang(call.from_user.id)
    conn = get_db()
    subs = conn.execute("""SELECT s.*, c.display_name FROM subscriptions s
        JOIN creators c ON s.creator_id=c.user_id
        WHERE s.user_id=? AND s.status='active' AND (s.end_date>? OR s.credits_left>0)""",
                        (call.from_user.id, datetime.now().isoformat())).fetchall()
    conn.close()
    text = "No tienes planes activos." if not subs else "📋 <b>Mis planes</b>\n\n"
    kb = types.InlineKeyboardMarkup()
    for s in (subs or []):
        extra = f"({s['credits_left']} créditos)" if s["credits_left"] else f"hasta {s['end_date'][:10]}"
        text += f"• {s['display_name']} {extra}\n"
        kb.add(types.InlineKeyboardButton(f"Ver {s['display_name']}", callback_data=f"viewcontent_{s['creator_id']}_0"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "become_creator")
def cb_become_creator(call):
    lang = get_lang(call.from_user.id)
    text = f"🎨 Ser Creador — {format_price(CREATOR_FEE)}\n\nPodrás publicar fotos/vídeos y crear planes.\n\n{get_setting('payment_methods')}"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💸 Ya pagué", callback_data="pay_creator_fee"))
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
    text = (f"🔧 <b>Admin</b>\n\nPagos: {pending_tx}\nVerificaciones: {pending_ver}\n"
            f"Contenidos: {contents}\nGrupo: {GROUP_INVITE}")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Menú", callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

# ==================== VERIFICACIÓN ====================
@bot.message_handler(content_types=["web_app_data"])
def handle_webapp(message):
    conn = get_db()
    conn.execute("INSERT INTO verifications (user_id, status, source, created_at) VALUES (?,'pending','webapp',?)",
                 (message.from_user.id, datetime.now().isoformat()))
    conn.execute("UPDATE users SET age_verified_real=1 WHERE user_id=?", (message.from_user.id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "📸 Envía ahora documento + selfie.")
    bot.send_message(ADMIN_ID, f"Verificación Mini App — {message.from_user.id}")

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
        bot.send_message(message.chat.id, "Documento OK. Envía <b>selfie</b>.")
        return
    if not ver["doc_photo_id"]:
        conn.execute("UPDATE verifications SET doc_photo_id=? WHERE id=?", (file_id, ver["id"]))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "Documento OK. Envía <b>selfie</b>.")
        return
    if not ver["selfie_photo_id"]:
        conn.execute("UPDATE verifications SET selfie_photo_id=? WHERE id=?", (file_id, ver["id"]))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ Fotos recibidas.")
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("♂️ Hombre", callback_data=f"verif_male_{ver['id']}"),
               types.InlineKeyboardButton("♀️ Mujer", callback_data=f"verif_female_{ver['id']}"))
        kb.add(types.InlineKeyboardButton("❌ Rechazar", callback_data=f"verif_reject_{ver['id']}"))
        bot.send_message(ADMIN_ID, f"Verificación — {message.from_user.id}")
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
        conn.execute("UPDATE verifications SET status='rejected', reviewed_at=?, reviewed_by=? WHERE id=?", (now, call.from_user.id, ver_id))
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
    bot.send_message(ver["user_id"], f"✅ Verificado. Badges: 🔞✅ {badge}")
    bot.answer_callback_query(call.id, "Aprobado")

# ==================== GRUPO ====================
@bot.message_handler(content_types=["new_chat_members"])
def on_new_member(message):
    if GROUP_ID and message.chat.id != GROUP_ID: return
    for m in message.new_chat_members:
        if m.id == bot.get_me().id:
            bot.send_message(message.chat.id, f"✅ Bot añadido.\n<code>GROUP_ID = {message.chat.id}</code>")
            continue
        if m.is_bot: continue
        upsert_user(m)
        bot.send_message(message.chat.id, t("group_welcome", get_lang(tg_user=m), name=m.first_name or "Usuario"))

@bot.message_handler(commands=["ayuda", "help"])
def cmd_help_g(message):
    if is_private_chat(message):
        bot.send_message(message.chat.id, t("help_text", get_lang(tg_user=message.from_user)))
        return
    if GROUP_ID and message.chat.id != GROUP_ID: return
    text = "/ayuda /reglas /soporte /yo /anuncio\n"
    if is_vip(message.from_user.id): text += "👑 /promo /invitar /vip\n"
    if is_admin(message.from_user.id): text += "🔧 /silenciar /activar /broadcast /stats\n"
    bot.reply_to(message, text)

@bot.message_handler(commands=["reglas"])
def cmd_rules(message):
    if is_private_chat(message) or (GROUP_ID and message.chat.id != GROUP_ID): return
    bot.reply_to(message, get_setting("group_rules"))

@bot.message_handler(commands=["soporte"])
def cmd_support(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "/soporte mensaje")
        return
    bot.reply_to(message, "✅ Enviado.")
    bot.send_message(ADMIN_ID, f"Soporte {message.from_user.id}: {parts[1]}")

@bot.message_handler(commands=["yo"])
def cmd_me(message):
    upsert_user(message.from_user)
    u = get_user(message.from_user.id)
    bot.reply_to(message, f"{message.from_user.first_name} {get_badges(u)}\nVIP: {'Sí' if is_vip(message.from_user.id) else 'No'}")

@bot.message_handler(commands=["anuncio"])
def cmd_anuncio(message):
    bot.reply_to(message, get_setting("announcement") or "Sin anuncios.")

@bot.message_handler(commands=["promo"])
def cmd_promo(message):
    if is_private_chat(message):
        bot.reply_to(message, "Usa /promo en el grupo.")
        return
    if GROUP_ID and message.chat.id != GROUP_ID: return
    uid = message.from_user.id
    if not is_vip(uid) or not is_creator(uid):
        bot.reply_to(message, t("only_vip", get_lang(tg_user=message.from_user)))
        return
    ok, wait = check_cooldown(uid, "promo")
    if not ok:
        bot.reply_to(message, f"Espera {wait} min.")
        return
    conn = get_db()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    if not c: return
    set_cooldown(uid, "promo")
    bot.send_message(message.chat.id,
        f"🔥 <b>PROMO</b>\n🎨 {c['display_name']} {get_badges(get_user(uid))}\n{c['bio'] or ''}\n➡️ /start en el bot")

@bot.message_handler(commands=["invitar"])
def cmd_invite(message):
    if not is_creator(message.from_user.id):
        bot.reply_to(message, t("only_creator", get_lang(tg_user=message.from_user)))
        return
    me = bot.get_me()
    bot.reply_to(message, f"https://t.me/{me.username}?start=creator_{message.from_user.id}")

@bot.message_handler(commands=["silenciar"])
def cmd_mute(message):
    if not is_admin(message.from_user.id) or is_private_chat(message): return
    set_group_setting("muted", "1")
    global group_muted
    group_muted = True
    bot.reply_to(message, "🔇 Silenciado.")

@bot.message_handler(commands=["activar"])
def cmd_unmute(message):
    if not is_admin(message.from_user.id) or is_private_chat(message): return
    set_group_setting("muted", "0")
    global group_muted
    group_muted = False
    bot.reply_to(message, "🔉 Activado.")

@bot.message_handler(commands=["broadcast"])
def cmd_broadcast(message):
    if not is_admin(message.from_user.id) or is_private_chat(message): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return
    bot.send_message(message.chat.id, f"📢 {parts[1]}")

@bot.message_handler(commands=["stats"])
def cmd_stats(message):
    if not is_admin(message.from_user.id): return
    conn = get_db()
    u = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    c = conn.execute("SELECT COUNT(*) FROM content").fetchone()[0]
    conn.close()
    bot.reply_to(message, f"Usuarios: {u}\nContenidos: {c}")

@bot.message_handler(func=lambda m: m.chat.type in ("group", "supergroup") and is_group_muted() and not is_admin(m.from_user.id),
                     content_types=["text", "photo", "video", "sticker", "animation", "voice", "document"])
def filter_muted(message):
    if GROUP_ID and message.chat.id != GROUP_ID: return
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

if __name__ == "__main__":
    init_db()
    global group_muted
    group_muted = is_group_muted()
    print("OnlyFans_ManagerBot V8 started")
    print("Contenido: protect_content | Planes flexibles | Likes/Comentarios")
    bot.infinity_polling()
