#!/usr/bin/env python3
"""
OnlyFans_ManagerBot - V5
- Funciona en chat privado + grupo privado
- Mini App de verificación con cámara
- Multilingüe (ES / EN)
- Pago obligatorio para ver contenido
- Badges edad/género verificados por admin
- Suscripciones + acceso a canal/grupo privado
"""

import telebot
from telebot import types
import sqlite3
import json
from datetime import datetime, timedelta

# ==================== CONFIGURACIÓN ====================
TELEGRAM_TOKEN = "PON_AQUI_TU_TOKEN"          # Token de @OnlyFans_ManagerBot
ADMIN_ID = 7653419875                         # Tu ID

# --- GRUPO PRIVADO PRINCIPAL ---
# 1. Crea un grupo privado o usa el que ya tienes
# 2. Añade el bot como ADMINISTRADOR
# 3. Obtén el ID numérico (con @userinfobot o reenviando mensaje)
#    El ID de grupos privados empieza por -100
GROUP_ID = None                               # Ejemplo: -1001234567890
GROUP_INVITE = "https://t.me/+oMkBHSWhjf5lNTZh"

# --- CANAL PRIVADO DE CONTENIDO (recomendado) ---
# Crea un canal privado, añade el bot como admin y pon el ID aquí
# El bot generará invite links automáticos cuando alguien pague
PRIVATE_CHANNEL_ID = None                     # Ejemplo: -1009876543210

CREATOR_FEE = 50.0
WEBAPP_VERIFICATION_URL = "https://TU_DOMINIO.com/verification.html"

DB_FILE = "bot.db"
bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")

# ==================== MULTILINGÜE ====================
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
        "group_welcome": "👋 Bienvenido/a al grupo privado, {name}!\n\nUsa /start en el chat privado conmigo para registrarte y verificar tu cuenta.",
        "use_private": "⚠️ Usa este bot en <b>chat privado</b> conmigo.\nEscribe /start aquí o ábreme en privado.",
        "help_text": (
            "❓ <b>Ayuda</b>\n\n"
            "• Solo puedes ver contenido si tienes <b>suscripción pagada</b>.\n"
            "• Usa la <b>verificación con cámara</b> para obtener badges de edad y género.\n"
            "• El género lo asigna el administrador tras revisar el documento.\n"
            "• Puedes reportar perfiles desde su ficha.\n"
            "• Para ser Creador paga 50$ y espera aprobación."
        ),
    },
    "en": {
        "welcome": "💖 <b>Welcome, {name}</b>\n\nExclusive content platform.\nChoose an option:",
        "age_title": "🔒 <b>Age Confirmation</b>",
        "age_text": "This bot contains adult content.\n\nDo you confirm you are <b>over 18 years old</b>?\n\n<i>Real verification is done later with the camera.</i>",
        "age_yes": "✅ Yes, I am over 18",
        "age_no": "❌ I am underage",
        "age_denied": "🚫 This service is only for users over 18.",
        "terms_accept": "✅ I accept",
        "terms_deny": "❌ I do not accept",
        "terms_must": "You must accept the terms to continue.",
        "menu_explore": "🔍 Explore Creators",
        "menu_subs": "📋 My Subscriptions",
        "menu_account": "👤 My Account",
        "menu_help": "❓ Help",
        "menu_creator": "🎨 Creator Panel",
        "menu_admin": "🔧 Admin Panel",
        "back": "« Back",
        "back_menu": "« Menu",
        "must_pay": "🔒 <b>You must pay to view the content</b>",
        "has_sub": "✅ <b>You have an active subscription</b>",
        "view_content": "📥 View content",
        "cancel_sub": "❌ Cancel subscription",
        "report": "📢 Report",
        "request_verif": "📸 Camera verification",
        "verif_pending": "You already have a pending verification",
        "verif_done": "You are already verified",
        "banned": "🚫 Your account is banned.",
        "no_creators": "There are no verified creators yet.",
        "group_welcome": "👋 Welcome to the private group, {name}!\n\nUse /start in private chat with me to register and verify your account.",
        "use_private": "⚠️ Please use this bot in <b>private chat</b>.\nSend /start here or open me in private.",
        "help_text": (
            "❓ <b>Help</b>\n\n"
            "• You can only view content with an <b>active paid subscription</b>.\n"
            "• Use <b>camera verification</b> to get age and gender badges.\n"
            "• Gender is assigned by the administrator after reviewing the document.\n"
            "• You can report profiles from their page.\n"
            "• To become a Creator pay $50 and wait for approval."
        ),
    }
}

def get_lang(user_id: int = None, tg_user=None) -> str:
    if tg_user and getattr(tg_user, "language_code", None):
        return "es" if tg_user.language_code.lower().startswith("es") else "en"
    if user_id:
        u = get_user(user_id)
        if u and u["language"]:
            return u["language"] if u["language"] in ("es", "en") else "es"
    return "es"

def t(key: str, lang: str = "es", **kwargs) -> str:
    text = TEXTS.get(lang, TEXTS["es"]).get(key, TEXTS["es"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except:
            return text
    return text

# ==================== BASE DE DATOS ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            role TEXT DEFAULT 'user',
            language TEXT DEFAULT 'es',
            age_declared INTEGER DEFAULT 0,
            terms_accepted INTEGER DEFAULT 0,
            age_verified_real INTEGER DEFAULT 0,
            gender TEXT,
            gender_verified INTEGER DEFAULT 0,
            creator_verified INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            ban_reason TEXT,
            joined_at TEXT,
            last_active TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS creators (
            user_id INTEGER PRIMARY KEY,
            display_name TEXT,
            bio TEXT,
            monthly_price REAL DEFAULT 9.99,
            quarterly_price REAL DEFAULT 24.99,
            private_channel_id INTEGER,
            invite_link TEXT,
            total_subscribers INTEGER DEFAULT 0,
            total_earnings REAL DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            creator_id INTEGER,
            plan TEXT,
            amount REAL,
            status TEXT DEFAULT 'active',
            start_date TEXT,
            end_date TEXT,
            payment_method TEXT,
            created_at TEXT,
            UNIQUE(user_id, creator_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER,
            title TEXT,
            description TEXT,
            file_ids TEXT,
            media_types TEXT,
            is_premium INTEGER DEFAULT 1,
            views INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            creator_id INTEGER,
            type TEXT,
            amount REAL,
            currency TEXT DEFAULT 'USD',
            status TEXT DEFAULT 'pending',
            payment_method TEXT,
            screenshot_file_id TEXT,
            reference TEXT,
            created_at TEXT,
            reviewed_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            doc_photo_id TEXT,
            selfie_photo_id TEXT,
            status TEXT DEFAULT 'pending',
            assigned_gender TEXT,
            source TEXT DEFAULT 'manual',
            created_at TEXT,
            reviewed_at TEXT,
            reviewed_by INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER,
            reported_id INTEGER,
            reason TEXT,
            details TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            target_id INTEGER,
            details TEXT,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    if not c.execute("SELECT 1 FROM settings WHERE key='payment_methods'").fetchone():
        c.execute("INSERT INTO settings VALUES (?, ?)", ("payment_methods",
            "💳 <b>Payment methods / Formas de pago:</b>\n\n"
            "• Transfer / Bizum\n"
            "• Crypto (USDT TRC20 / BTC)\n"
            "• Telegram Stars\n\n"
            "<i>Admin will update the exact details.</i>"
        ))

    if not c.execute("SELECT 1 FROM settings WHERE key='terms'").fetchone():
        c.execute("INSERT INTO settings VALUES (?, ?)", ("terms",
            "📜 <b>Terms & Conditions / Términos</b>\n\n"
            "1. You must be 18+ / Debes ser mayor de 18.\n"
            "2. Personal use only / Solo uso personal.\n"
            "3. No redistribution / Prohibida la redistribución.\n"
            "4. Ban for violations / Ban por incumplimientos.\n"
            "5. By continuing you accept these terms."
        ))

    conn.commit()
    conn.close()
    ensure_admin()

def ensure_admin():
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT OR IGNORE INTO users 
        (user_id, role, age_declared, terms_accepted, age_verified_real, gender_verified, creator_verified, language, joined_at, last_active)
        VALUES (?, 'admin', 1, 1, 2, 1, 2, 'es', ?, ?)
    """, (ADMIN_ID, now, now))
    conn.execute("""
        UPDATE users SET role='admin', age_declared=1, terms_accepted=1, 
        age_verified_real=2, gender_verified=1, creator_verified=2 
        WHERE user_id=?
    """, (ADMIN_ID,))
    conn.execute("""
        INSERT OR IGNORE INTO creators (user_id, display_name, bio, created_at)
        VALUES (?, 'Admin Principal', 'Main creator', ?)
    """, (ADMIN_ID, now))
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_setting(key: str) -> str:
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else ""

def set_setting(key: str, value: str):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def log_admin(admin_id: int, action: str, target_id: int = None, details: str = ""):
    conn = get_db()
    conn.execute("INSERT INTO admin_logs (admin_id, action, target_id, details, created_at) VALUES (?,?,?,?,?)",
                 (admin_id, action, target_id, details, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_user(user_id: int):
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return u

def upsert_user(tg_user):
    conn = get_db()
    now = datetime.now().isoformat()
    lang = "es" if (tg_user.language_code or "").lower().startswith("es") else "en"
    conn.execute("""
        INSERT INTO users (user_id, username, first_name, language, joined_at, last_active)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            language=excluded.language,
            last_active=excluded.last_active
    """, (tg_user.id, tg_user.username, tg_user.first_name, lang, now, now))
    conn.commit()
    conn.close()

def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID

def is_banned(uid: int) -> bool:
    u = get_user(uid)
    return u and u["banned"] == 1

def is_creator(uid: int) -> bool:
    u = get_user(uid)
    return u and u["role"] in ("creator", "admin") and u["creator_verified"] == 2

def format_price(price: float) -> str:
    return f"${price:.2f}"

def has_active_sub(user_id: int, creator_id: int) -> bool:
    conn = get_db()
    row = conn.execute("""
        SELECT 1 FROM subscriptions
        WHERE user_id=? AND creator_id=? AND status='active' AND end_date > ?
    """, (user_id, creator_id, datetime.now().isoformat())).fetchone()
    conn.close()
    return bool(row)

def get_badges(user) -> str:
    badges = []
    if user and user["age_verified_real"] == 2:
        badges.append("🔞✅")
    if user and user["gender_verified"] == 1 and user["gender"]:
        badges.append("♂️" if user["gender"] == "male" else "♀️")
    return " ".join(badges) if badges else ""

def get_gender_text(user, lang="es") -> str:
    if not user or not user["gender_verified"]:
        return "No verificado" if lang == "es" else "Not verified"
    if user["gender"] == "male":
        return "Masculino" if lang == "es" else "Male"
    return "Femenino" if lang == "es" else "Female"

def is_private_chat(message):
    return message.chat.type == "private"

def is_our_group(message):
    if GROUP_ID is None:
        return False
    return message.chat.id == GROUP_ID

# ==================== MENÚ PRINCIPAL ====================
def main_menu_kb(user_id: int, lang: str):
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

# ==================== START + EDAD + TÉRMINOS ====================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    # Si está en grupo, redirigir a privado
    if not is_private_chat(message):
        lang = get_lang(tg_user=message.from_user)
        bot.reply_to(message, t("use_private", lang))
        return

    if is_banned(message.from_user.id):
        lang = get_lang(tg_user=message.from_user)
        bot.send_message(message.chat.id, t("banned", lang))
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

# ==================== BIENVENIDA EN GRUPO PRIVADO ====================
@bot.message_handler(content_types=["new_chat_members"])
def on_new_member(message):
    if GROUP_ID and message.chat.id != GROUP_ID:
        return
    for member in message.new_chat_members:
        if member.id == bot.get_me().id:
            # El bot fue añadido al grupo
            bot.send_message(message.chat.id,
                "✅ Bot añadido correctamente.\n\n"
                "Configura <code>GROUP_ID</code> en main.py con este ID:\n"
                f"<code>{message.chat.id}</code>"
            )
            continue
        if member.is_bot:
            continue
        lang = get_lang(tg_user=member)
        name = member.first_name or "Usuario"
        bot.send_message(message.chat.id, t("group_welcome", lang, name=name))

# ==================== MENÚS PRINCIPALES ====================
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

    text = (
        f"👤 <b>Mi Cuenta</b> {badges}\n\n"
        f"ID: <code>{call.from_user.id}</code>\n"
        f"Rol: {role}\n"
        f"Género: {gender}\n"
        f"Edad verificada: {'Sí 🔞✅' if user and user['age_verified_real'] == 2 else 'No'}\n"
    )

    kb = types.InlineKeyboardMarkup()
    if not (user and user["age_verified_real"] == 2):
        # Botón de Mini App para verificación con cámara
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
        FROM creators c
        JOIN users u ON c.user_id = u.user_id
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
        kb.add(types.InlineKeyboardButton(
            f"{name} {badges}",
            callback_data=f"creator_{c['user_id']}"
        ))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("creator_"))
def cb_creator_profile(call):
    lang = get_lang(call.from_user.id)
    creator_id = int(call.data.split("_")[1])
    conn = get_db()
    c = conn.execute("""
        SELECT c.*, u.first_name, u.gender, u.gender_verified, u.age_verified_real
        FROM creators c JOIN users u ON c.user_id = u.user_id
        WHERE c.user_id=?
    """, (creator_id,)).fetchone()
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
        kb.add(types.InlineKeyboardButton(t("cancel_sub", lang), callback_data=f"cancel_sub_{creator_id}"))
    else:
        text += f"\n{t('must_pay', lang)}"
        kb.add(types.InlineKeyboardButton(
            f"💳 Mensual {format_price(c['monthly_price'])}",
            callback_data=f"sub_monthly_{creator_id}"
        ))
        kb.add(types.InlineKeyboardButton(
            f"💳 Trimestral {format_price(c['quarterly_price'])}",
            callback_data=f"sub_quarterly_{creator_id}"
        ))
    kb.add(types.InlineKeyboardButton(t("report", lang), callback_data=f"report_{creator_id}"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="menu_explore"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

# ==================== SUSCRIPCIONES Y PAGOS ====================
@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("sub_"))
def cb_subscribe(call):
    parts = call.data.split("_")
    plan = parts[1]  # monthly / quarterly
    creator_id = int(parts[2])
    lang = get_lang(call.from_user.id)

    conn = get_db()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (creator_id,)).fetchone()
    conn.close()
    if not c:
        bot.answer_callback_query(call.id, "Error", show_alert=True)
        return

    price = c["monthly_price"] if plan == "monthly" else c["quarterly_price"]
    text = (
        f"💳 <b>Suscripción {plan}</b>\n\n"
        f"Precio: {format_price(price)}\n\n"
        f"{get_setting('payment_methods')}\n\n"
        f"Después de pagar, envía la <b>captura</b> del pago."
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Ya pagué - Enviar captura", callback_data=f"send_proof_{plan}_{creator_id}"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data=f"creator_{creator_id}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("send_proof_"))
def cb_send_proof(call):
    parts = call.data.split("_")
    plan = parts[2]
    creator_id = int(parts[3])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📸 Envía ahora la <b>captura del pago</b> (foto).")
    bot.register_next_step_handler(msg, lambda m: process_payment_proof(m, plan, creator_id))

def process_payment_proof(message, plan, creator_id):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Envía una foto de la captura.")
        return

    file_id = message.photo[-1].file_id
    conn = get_db()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (creator_id,)).fetchone()
    amount = c["monthly_price"] if plan == "monthly" else c["quarterly_price"]

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transactions (user_id, creator_id, type, amount, status, payment_method, screenshot_file_id, created_at)
        VALUES (?, ?, ?, ?, 'pending', 'manual', ?, ?)
    """, (message.from_user.id, creator_id, f"sub_{plan}", amount, file_id, datetime.now().isoformat()))
    tx_id = cur.lastrowid
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, "✅ Captura recibida. Esperando verificación del administrador.")

    # Notificar al admin
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_tx_{tx_id}"),
        types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_tx_{tx_id}")
    )
    caption = (
        f"💳 <b>NUEVO PAGO</b>\n\n"
        f"User: {message.from_user.id} (@{message.from_user.username})\n"
        f"Creator: {creator_id}\n"
        f"Plan: {plan}\n"
        f"Monto: {format_price(amount)}\n"
        f"TX #{tx_id}"
    )
    bot.send_photo(ADMIN_ID, file_id, caption=caption, reply_markup=kb)

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
        conn.execute("""
            INSERT OR IGNORE INTO creators (user_id, display_name, bio, created_at)
            VALUES (?, ?, 'Nuevo creador', ?)
        """, (tx["user_id"], f"Creator {tx['user_id']}", now.isoformat()))
        conn.execute("UPDATE transactions SET status='approved', reviewed_at=? WHERE id=?", (now.isoformat(), tx_id))
        conn.commit()
        conn.close()
        bot.send_message(tx["user_id"], "✅ ¡Has sido aprobado como <b>Creador</b>!")
        bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=call.message.caption + "\n\n✅ APROBADO")
        bot.answer_callback_query(call.id, "Creador aprobado")
        return

    # Suscripción
    days = 30 if "monthly" in tx["type"] else 90
    end = (now + timedelta(days=days)).isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO subscriptions
        (user_id, creator_id, plan, amount, status, start_date, end_date, payment_method, created_at)
        VALUES (?, ?, ?, ?, 'active', ?, ?, 'manual', ?)
    """, (tx["user_id"], tx["creator_id"], tx["type"], tx["amount"], now.isoformat(), end, now.isoformat()))
    conn.execute("UPDATE creators SET total_subscribers = total_subscribers + 1, total_earnings = total_earnings + ? WHERE user_id=?",
                 (tx["amount"], tx["creator_id"]))
    conn.execute("UPDATE transactions SET status='approved', reviewed_at=? WHERE id=?", (now.isoformat(), tx_id))
    conn.commit()
    conn.close()

    # Generar invite link al canal privado si está configurado
    invite_msg = ""
    if PRIVATE_CHANNEL_ID:
        try:
            link = bot.create_chat_invite_link(
                PRIVATE_CHANNEL_ID,
                member_limit=1,
                name=f"Sub user {tx['user_id']}"
            )
            invite_msg = f"\n\n🔗 Acceso al contenido privado:\n{link.invite_link}"
        except Exception as e:
            invite_msg = f"\n\n⚠️ No se pudo generar invite automático. Contacta al admin."

    bot.send_message(tx["user_id"],
        f"✅ <b>Pago aprobado</b>\n\n"
        f"Tu suscripción está activa hasta {end[:10]}."
        f"{invite_msg}"
    )
    bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=call.message.caption + "\n\n✅ APROBADO")
    bot.answer_callback_query(call.id, "Pago aprobado")

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
    conn.execute("UPDATE transactions SET status='rejected', reviewed_at=? WHERE id=?",
                 (datetime.now().isoformat(), tx_id))
    if tx["type"] == "creator_fee":
        conn.execute("UPDATE users SET creator_verified=0 WHERE user_id=?", (tx["user_id"],))
    conn.commit()
    conn.close()
    bot.send_message(tx["user_id"], "❌ Tu pago fue rechazado. Contacta al administrador.")
    bot.edit_message_caption(call.message.chat.id, call.message.message_id, caption=call.message.caption + "\n\n❌ RECHAZADO")
    bot.answer_callback_query(call.id, "Rechazado")

# ==================== VERIFICACIÓN (Mini App + fotos) ====================
@bot.message_handler(content_types=["web_app_data"])
def handle_webapp(message):
    """Recibe datos de la Mini App de verificación"""
    try:
        data = json.loads(message.web_app_data.data)
    except:
        bot.send_message(message.chat.id, "Error al procesar verificación.")
        return

    user_id = message.from_user.id
    conn = get_db()
    # Marcar como pendiente de revisión
    conn.execute("""
        INSERT INTO verifications (user_id, status, source, created_at)
        VALUES (?, 'pending', 'webapp', ?)
    """, (user_id, datetime.now().isoformat()))
    conn.execute("UPDATE users SET age_verified_real=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id,
        "📸 Datos de verificación recibidos.\n"
        "Ahora envía las <b>fotos</b> (documento + selfie) para que el admin las revise."
    )
    bot.send_message(ADMIN_ID,
        f"📸 Nueva solicitud de verificación (Mini App)\nUsuario: {user_id}\nEsperando fotos..."
    )

@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    """Recibe fotos de verificación"""
    if not is_private_chat(message):
        return
    user = get_user(message.from_user.id)
    if not user or user["age_verified_real"] == 2:
        return  # Ya verificado o no en proceso

    file_id = message.photo[-1].file_id
    conn = get_db()
    ver = conn.execute("""
        SELECT * FROM verifications WHERE user_id=? AND status='pending'
        ORDER BY id DESC LIMIT 1
    """, (message.from_user.id,)).fetchone()

    if not ver:
        # Crear nueva si no existe
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO verifications (user_id, doc_photo_id, status, source, created_at)
            VALUES (?, ?, 'pending', 'manual', ?)
        """, (message.from_user.id, file_id, datetime.now().isoformat()))
        conn.execute("UPDATE users SET age_verified_real=1 WHERE user_id=?", (message.from_user.id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "📸 Foto de documento recibida. Ahora envía tu <b>selfie</b> (cara + documento).")
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
        bot.send_message(message.chat.id, "✅ Fotos recibidas. Esperando revisión del administrador.")

        # Enviar al admin
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
    action = parts[1]  # male / female / reject
    ver_id = int(parts[2])

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
        bot.send_message(ver["user_id"], "❌ Tu verificación fue rechazada.")
        bot.answer_callback_query(call.id, "Rechazado")
        return

    gender = "male" if action == "male" else "female"
    conn.execute("""
        UPDATE verifications SET status='approved', assigned_gender=?, reviewed_at=?, reviewed_by=?
        WHERE id=?
    """, (gender, now, call.from_user.id, ver_id))
    conn.execute("""
        UPDATE users SET age_verified_real=2, gender=?, gender_verified=1
        WHERE user_id=?
    """, (gender, ver["user_id"]))
    conn.commit()
    conn.close()

    badge = "♂️" if gender == "male" else "♀️"
    bot.send_message(ver["user_id"],
        f"✅ <b>Verificación aprobada</b>\n\n"
        f"Has recibido los badges: 🔞✅ {badge}"
    )
    bot.answer_callback_query(call.id, f"Aprobado como {gender}")

# ==================== OTRAS FUNCIONES ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_subs")
def cb_subs(call):
    lang = get_lang(call.from_user.id)
    conn = get_db()
    subs = conn.execute("""
        SELECT s.*, c.display_name FROM subscriptions s
        JOIN creators c ON s.creator_id = c.user_id
        WHERE s.user_id=? AND s.status='active' AND s.end_date > ?
    """, (call.from_user.id, datetime.now().isoformat())).fetchall()
    conn.close()

    if not subs:
        text = "No tienes suscripciones activas." if lang == "es" else "You have no active subscriptions."
    else:
        text = "📋 <b>Mis Suscripciones</b>\n\n"
        for s in subs:
            text += f"• {s['display_name']} — hasta {s['end_date'][:10]}\n"

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "become_creator")
def cb_become_creator(call):
    lang = get_lang(call.from_user.id)
    user = get_user(call.from_user.id)
    if user["creator_verified"] == 2:
        bot.answer_callback_query(call.id, "Already creator", show_alert=True)
        return
    text = f"🎨 Become Creator — {format_price(CREATOR_FEE)}\n\n{get_setting('payment_methods')}"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(f"💸 I paid {format_price(CREATOR_FEE)}", callback_data="pay_creator_fee"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="menu_account"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "pay_creator_fee")
def cb_pay_creator_fee(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"📸 Send screenshot of ${CREATOR_FEE} payment.")
    bot.register_next_step_handler(msg, process_creator_fee)

def process_creator_fee(message):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Send a photo.")
        return
    file_id = message.photo[-1].file_id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transactions (user_id, type, amount, status, payment_method, screenshot_file_id, created_at)
        VALUES (?, 'creator_fee', ?, 'pending', 'manual', ?, ?)
    """, (message.from_user.id, CREATOR_FEE, file_id, datetime.now().isoformat()))
    tx_id = cur.lastrowid
    conn.execute("UPDATE users SET creator_verified=1 WHERE user_id=?", (message.from_user.id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Received. Waiting for approval.")
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Approve Creator", callback_data=f"approve_tx_{tx_id}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_tx_{tx_id}")
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
        f"🔧 <b>Admin Panel</b>\n\n"
        f"Pending TX: {pending_tx}\n"
        f"Pending verifications: {pending_ver}\n"
        f"Group: {GROUP_INVITE}\n"
        f"GROUP_ID: {GROUP_ID or 'No configurado'}\n"
        f"PRIVATE_CHANNEL_ID: {PRIVATE_CHANNEL_ID or 'No configurado'}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Menu", callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "creator_panel")
def cb_creator_panel(call):
    if not is_creator(call.from_user.id):
        bot.answer_callback_query(call.id, "Not a creator", show_alert=True)
        return
    conn = get_db()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (call.from_user.id,)).fetchone()
    conn.close()
    text = f"🎨 Creator Panel\nSubscribers: {c['total_subscribers']}\nEarnings: {format_price(c['total_earnings'])}"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Menu", callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

# ==================== ARRANQUE ====================
if __name__ == "__main__":
    init_db()
    print("OnlyFans_ManagerBot V5 started")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"WebApp URL: {WEBAPP_VERIFICATION_URL}")
    print(f"Group Invite: {GROUP_INVITE}")
    print(f"GROUP_ID: {GROUP_ID}")
    print(f"PRIVATE_CHANNEL_ID: {PRIVATE_CHANNEL_ID}")
    bot.infinity_polling()
