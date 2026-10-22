#!/usr/bin/env python3
"""
OnlyFans_ManagerBot - V4
- Mini App de verificación con cámara (documento + selfie)
- Multilingüe (ES / EN según language_code)
- Pago obligatorio para ver contenido
- Badges edad/género verificados por admin
- Suscripciones, panel creador, admin, reportes
"""

import telebot
from telebot import types
import sqlite3
import json
from datetime import datetime, timedelta

# ==================== CONFIGURACIÓN ====================
TELEGRAM_TOKEN = "PON_AQUI_TU_TOKEN"          # Token de @OnlyFans_ManagerBot
ADMIN_ID = 7653419875                         # Tu ID (el del repo)
CREATOR_FEE = 50.0

# URL de la Mini App de verificación (debe ser HTTPS)
# Sube webapp/verification.html a GitHub Pages / Vercel / Cloudflare y pon la URL aquí
WEBAPP_VERIFICATION_URL = "https://TU_DOMINIO.com/verification.html"

# Invite del grupo (añade el bot al grupo para obtener ID numérico si lo necesitas)
GROUP_INVITE = "https://t.me/+oMkBHSWhjf5lNTZh"

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
    """Devuelve 'es' o 'en'"""
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
    terms = get_setting("terms")
    text = terms + ("\n\n¿Aceptas los términos?" if lang == "es" else "\n\nDo you accept the terms?")
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton(t("terms_accept", lang), callback_data="terms_yes"),
        types.InlineKeyboardButton(t("terms_deny", lang), callback_data="terms_no")
    )
    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    else:
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

# ==================== MENÚS ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_main")
def cb_main(call):
    lang = get_lang(call.from_user.id)
    bot.answer_callback_query(call.id)
    send_main_menu(call.message.chat.id, call.from_user.id, call.message.message_id, lang)

@bot.callback_query_handler(func=lambda c: c.data == "menu_explore")
def cb_explore(call):
    bot.answer_callback_query(call.id)
    show_creators(call.message.chat.id, call.from_user.id, call.message.message_id, 0)

def show_creators(chat_id, user_id, message_id=None, page=0):
    lang = get_lang(user_id)
    conn = get_db()
    creators = conn.execute("""
        SELECT c.*, u.username, u.first_name, u.age_verified_real, u.gender, u.gender_verified
        FROM creators c JOIN users u ON u.user_id = c.user_id
        WHERE u.creator_verified=2 AND u.banned=0
        ORDER BY c.total_subscribers DESC
    """).fetchall()
    conn.close()

    if not creators:
        text = t("no_creators", lang)
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="menu_main"))
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
        return

    per_page = 5
    total = max(1, (len(creators) + per_page - 1) // per_page)
    page = max(0, min(page, total - 1))
    chunk = creators[page*per_page:(page+1)*per_page]

    text = f"🔍 <b>{'Creadores' if lang=='es' else 'Creators'}</b> ({page+1}/{total})\n\n"
    kb = types.InlineKeyboardMarkup()
    for c in chunk:
        badges = get_badges(c)
        name = c["display_name"] or c["first_name"] or "Creator"
        btn = f"{badges} {name} — {format_price(c['monthly_price'])}/mo"
        kb.add(types.InlineKeyboardButton(btn, callback_data=f"creator_{c['user_id']}"))

    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("«", callback_data=f"explore_page_{page-1}"))
    if page < total - 1:
        nav.append(types.InlineKeyboardButton("»", callback_data=f"explore_page_{page+1}"))
    if nav:
        kb.row(*nav)
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("explore_page_"))
def cb_explore_page(call):
    page = int(call.data.split("_")[-1])
    bot.answer_callback_query(call.id)
    show_creators(call.message.chat.id, call.from_user.id, call.message.message_id, page)

@bot.callback_query_handler(func=lambda c: c.data.startswith("creator_") and c.data.count("_") == 1)
def cb_creator_profile(call):
    creator_id = int(call.data.split("_")[1])
    lang = get_lang(call.from_user.id)
    bot.answer_callback_query(call.id)

    conn = get_db()
    creator = conn.execute("""
        SELECT c.*, u.first_name, u.age_verified_real, u.gender, u.gender_verified
        FROM creators c JOIN users u ON u.user_id = c.user_id
        WHERE c.user_id=? AND u.creator_verified=2
    """, (creator_id,)).fetchone()
    conn.close()

    if not creator:
        return

    name = creator["display_name"] or creator["first_name"]
    badges = get_badges(creator)
    subscribed = has_active_sub(call.from_user.id, creator_id)

    text = (
        f"🎨 <b>{name}</b> {badges}\n\n"
        f"{creator['bio'] or ''}\n\n"
        f"🔞 {'Edad verificada' if creator['age_verified_real']==2 else 'Solo declarada'}\n"
        f"Género: {get_gender_text(creator, lang)}\n\n"
        f"💰 Monthly: <b>{format_price(creator['monthly_price'])}</b>\n"
        f"💰 Quarterly: <b>{format_price(creator['quarterly_price'])}</b>\n"
        f"👥 {creator['total_subscribers']}\n"
    )

    kb = types.InlineKeyboardMarkup()
    if subscribed:
        text += f"\n{t('has_sub', lang)}"
        kb.add(types.InlineKeyboardButton(t("view_content", lang), callback_data=f"content_{creator_id}"))
        kb.add(types.InlineKeyboardButton(t("cancel_sub", lang), callback_data=f"cancel_sub_{creator_id}"))
    else:
        text += f"\n{t('must_pay', lang)}"
        kb.add(types.InlineKeyboardButton(f"Monthly {format_price(creator['monthly_price'])}", callback_data=f"sub_monthly_{creator_id}"))
        kb.add(types.InlineKeyboardButton(f"Quarterly {format_price(creator['quarterly_price'])}", callback_data=f"sub_quarterly_{creator_id}"))

    kb.add(types.InlineKeyboardButton(t("report", lang), callback_data=f"report_{creator_id}"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="menu_explore"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

# ==================== VERIFICACIÓN CON MINI APP (CÁMARA) ====================
@bot.callback_query_handler(func=lambda c: c.data == "request_real_verification")
def cb_request_verification(call):
    user = get_user(call.from_user.id)
    lang = get_lang(call.from_user.id)

    if user["age_verified_real"] == 2:
        bot.answer_callback_query(call.id, t("verif_done", lang), show_alert=True)
        return
    if user["age_verified_real"] == 1:
        bot.answer_callback_query(call.id, t("verif_pending", lang), show_alert=True)
        return

    bot.answer_callback_query(call.id)

    # Botón que abre la Mini App (Web App)
    # Nota: para sendData completo es mejor KeyboardButton, pero Inline + web_app también abre la app
    kb = types.InlineKeyboardMarkup()
    if WEBAPP_VERIFICATION_URL and "TU_DOMINIO" not in WEBAPP_VERIFICATION_URL:
        kb.add(types.InlineKeyboardButton(
            t("request_verif", lang),
            web_app=types.WebAppInfo(url=WEBAPP_VERIFICATION_URL)
        ))
    else:
        # Fallback manual si aún no hay URL de Mini App
        kb.add(types.InlineKeyboardButton(
            "📸 Enviar fotos manualmente" if lang == "es" else "📸 Send photos manually",
            callback_data="manual_verif_start"
        ))

    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="menu_account"))

    text = (
        "📸 <b>Verificación con cámara</b>\n\n"
        "Se abrirá una Mini App donde podrás usar la cámara para:\n"
        "1. Foto del documento\n"
        "2. Selfie con el documento\n\n"
        "El administrador revisará y asignará edad + género verificados.\n"
        "<b>Tú no eliges el sexo.</b>"
    ) if lang == "es" else (
        "📸 <b>Camera verification</b>\n\n"
        "A Mini App will open so you can use the camera for:\n"
        "1. Document photo\n"
        "2. Selfie with the document\n\n"
        "The admin will review and assign verified age + gender.\n"
        "<b>You do not choose the gender.</b>"
    )

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "manual_verif_start")
def cb_manual_verif(call):
    lang = get_lang(call.from_user.id)
    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.message.chat.id,
        "Envía primero la <b>foto del documento</b>." if lang == "es" else "Send the <b>document photo</b> first."
    )
    bot.register_next_step_handler(msg, receive_doc_manual)

def receive_doc_manual(message):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Debes enviar una foto.")
        return
    doc_id = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id, "Ahora la <b>selfie con el documento</b>.")
    bot.register_next_step_handler(msg, receive_selfie_manual, doc_id)

def receive_selfie_manual(message, doc_id):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Debes enviar una foto.")
        return
    selfie_id = message.photo[-1].file_id

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO verifications (user_id, doc_photo_id, selfie_photo_id, status, source, created_at)
        VALUES (?, ?, ?, 'pending', 'manual', ?)
    """, (message.from_user.id, doc_id, selfie_id, datetime.now().isoformat()))
    ver_id = cur.lastrowid
    conn.execute("UPDATE users SET age_verified_real=1 WHERE user_id=?", (message.from_user.id,))
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, "✅ Fotos recibidas. El admin las revisará.")

    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    admin_text = (
        f"📝 <b>NUEVA VERIFICACIÓN</b>\n\n"
        f"Usuario: {username} (<code>{message.from_user.id}</code>)\n"
        f"Verificación #{ver_id}\n\nElige género:"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("♂️ Hombre", callback_data=f"ver_approve_male_{ver_id}"),
        types.InlineKeyboardButton("♀️ Mujer", callback_data=f"ver_approve_female_{ver_id}")
    )
    kb.add(types.InlineKeyboardButton("❌ Rechazar", callback_data=f"ver_reject_{ver_id}"))
    bot.send_photo(ADMIN_ID, doc_id, caption="Documento")
    bot.send_photo(ADMIN_ID, selfie_id, caption=admin_text, reply_markup=kb)

# Handler cuando la Mini App envía datos con sendData
@bot.message_handler(content_types=["web_app_data"])
def handle_web_app_data(message):
    try:
        data = json.loads(message.web_app_data.data)
    except:
        return

    if data.get("type") != "verification":
        return

    user_id = message.from_user.id
    conn = get_db()
    conn.execute("UPDATE users SET age_verified_real=1 WHERE user_id=?", (user_id,))
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO verifications (user_id, status, source, created_at)
        VALUES (?, 'pending', 'webapp', ?)
    """, (user_id, datetime.now().isoformat()))
    ver_id = cur.lastrowid
    conn.commit()
    conn.close()

    bot.send_message(
        message.chat.id,
        "✅ Verificación recibida desde la Mini App.\n"
        "Por favor envía ahora las dos fotos (documento y selfie) para completar."
    )
    bot.send_message(
        ADMIN_ID,
        f"📱 Mini App verification started\nUser: {user_id}\nVer #{ver_id}\nEsperando fotos..."
    )

# ==================== APROBAR VERIFICACIÓN ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith(("ver_approve_male_", "ver_approve_female_", "ver_reject_")))
def cb_review_verification(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "No autorizado", show_alert=True)
        return

    parts = call.data.split("_")
    action = parts[1]
    gender = parts[2] if action == "approve" else None
    ver_id = int(parts[-1])

    conn = get_db()
    ver = conn.execute("SELECT * FROM verifications WHERE id=?", (ver_id,)).fetchone()
    if not ver or ver["status"] != "pending":
        bot.answer_callback_query(call.id, "Ya procesada", show_alert=True)
        conn.close()
        return

    if action == "approve":
        conn.execute("""
            UPDATE verifications SET status='approved', assigned_gender=?, reviewed_at=?, reviewed_by=?
            WHERE id=?
        """, (gender, datetime.now().isoformat(), call.from_user.id, ver_id))
        conn.execute("""
            UPDATE users SET age_verified_real=2, gender=?, gender_verified=1 WHERE user_id=?
        """, (gender, ver["user_id"]))
        conn.commit()

        gender_text = "Masculino" if gender == "male" else "Femenino"
        try:
            bot.send_message(
                ver["user_id"],
                f"✅ <b>Verificación aprobada</b>\n\n"
                f"Badges asignados:\n🔞✅ Edad Verificada\n"
                f"{'\u2642\ufe0f' if gender=='male' else '\u2640\ufe0f'} Género Verificado ({gender_text})"
            )
        except:
            pass

        bot.edit_message_caption(
            caption=(call.message.caption or "") + f"\n\n✅ APROBADO ({gender_text})",
            chat_id=call.message.chat.id, message_id=call.message.message_id
        )
        bot.answer_callback_query(call.id, f"Aprobado como {gender_text}")
        log_admin(call.from_user.id, "approve_verification", ver["user_id"], f"gender={gender}")
    else:
        conn.execute("UPDATE verifications SET status='rejected', reviewed_at=?, reviewed_by=? WHERE id=?",
                     (datetime.now().isoformat(), call.from_user.id, ver_id))
        conn.execute("UPDATE users SET age_verified_real=0 WHERE user_id=?", (ver["user_id"],))
        conn.commit()
        try:
            bot.send_message(ver["user_id"], "❌ Verificación rechazada. Puedes intentarlo de nuevo.")
        except:
            pass
        bot.edit_message_caption(
            caption=(call.message.caption or "") + "\n\n❌ RECHAZADO",
            chat_id=call.message.chat.id, message_id=call.message.message_id
        )
        bot.answer_callback_query(call.id, "Rechazado")
        log_admin(call.from_user.id, "reject_verification", ver["user_id"])

    conn.close()

# ==================== MI CUENTA ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_account")
def cb_account(call):
    user = get_user(call.from_user.id)
    lang = get_lang(call.from_user.id)
    badges = get_badges(user)

    text = (
        f"👤 <b>Mi Cuenta</b> {badges}\n\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Rol: {user['role']}\n"
        f"Edad verificada: {'✅' if user['age_verified_real']==2 else '⏳' if user['age_verified_real']==1 else '❌'}\n"
        f"Género: {get_gender_text(user, lang)}\n"
    )

    kb = types.InlineKeyboardMarkup()
    if user["age_verified_real"] != 2:
        kb.add(types.InlineKeyboardButton(t("request_verif", lang), callback_data="request_real_verification"))
    if user["role"] == "user" and user["creator_verified"] != 2:
        kb.add(types.InlineKeyboardButton("🎨 Become Creator ($50)", callback_data="become_creator"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "menu_help")
def cb_help(call):
    lang = get_lang(call.from_user.id)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(t("help_text", lang), call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "menu_subs")
def cb_my_subs(call):
    lang = get_lang(call.from_user.id)
    conn = get_db()
    subs = conn.execute("""
        SELECT s.*, c.display_name FROM subscriptions s
        JOIN creators c ON c.user_id = s.creator_id
        WHERE s.user_id=? AND s.status='active' AND s.end_date > ?
    """, (call.from_user.id, datetime.now().isoformat())).fetchall()
    conn.close()

    text = "No active subscriptions." if not subs else "📋 <b>Subscriptions</b>\n\n" + "\n".join(
        [f"• <b>{s['display_name']}</b> ({s['plan']}) → {s['end_date'][:10]}" for s in subs]
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

# ==================== CONTENIDO (solo si pagó) ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("content_"))
def cb_content(call):
    creator_id = int(call.data.split("_")[1])
    if not has_active_sub(call.from_user.id, creator_id) and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Subscription required", show_alert=True)
        return

    conn = get_db()
    items = conn.execute("SELECT * FROM content WHERE creator_id=? ORDER BY id DESC LIMIT 5", (creator_id,)).fetchall()
    conn.close()

    if not items:
        bot.answer_callback_query(call.id, "No content yet", show_alert=True)
        return

    bot.answer_callback_query(call.id)
    for item in items:
        file_ids = json.loads(item["file_ids"])
        media_types = json.loads(item["media_types"])
        for fid, mtype in zip(file_ids, media_types):
            try:
                if mtype == "photo":
                    bot.send_photo(call.message.chat.id, fid, protect_content=True)
                elif mtype == "video":
                    bot.send_video(call.message.chat.id, fid, protect_content=True)
            except:
                pass

# ==================== SUSCRIPCIONES RÁPIDAS (pago manual) ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("sub_"))
def cb_subscribe(call):
    parts = call.data.split("_")
    plan, creator_id = parts[1], int(parts[2])
    lang = get_lang(call.from_user.id)

    if has_active_sub(call.from_user.id, creator_id):
        bot.answer_callback_query(call.id, "Already subscribed", show_alert=True)
        return

    conn = get_db()
    creator = conn.execute("SELECT * FROM creators WHERE user_id=?", (creator_id,)).fetchone()
    conn.close()
    if not creator:
        return

    amount = creator["monthly_price"] if plan == "monthly" else creator["quarterly_price"]
    payment_methods = get_setting("payment_methods")

    text = (
        f"💳 <b>{plan.capitalize()}</b> — {format_price(amount)}\n\n"
        f"{payment_methods}\n\n"
        "When paid, press the button and send the screenshot."
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💸 I paid — Send screenshot", callback_data=f"pay_sub_{plan}_{creator_id}"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data=f"creator_{creator_id}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_sub_"))
def cb_pay_sub(call):
    parts = call.data.split("_")
    plan, creator_id = parts[2], int(parts[3])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📸 Send the payment screenshot now.")
    bot.register_next_step_handler(msg, process_sub_screenshot, plan, creator_id)

def process_sub_screenshot(message, plan, creator_id):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Please send a photo.")
        return

    conn = get_db()
    creator = conn.execute("SELECT * FROM creators WHERE user_id=?", (creator_id,)).fetchone()
    if not creator:
        conn.close()
        return

    amount = creator["monthly_price"] if plan == "monthly" else creator["quarterly_price"]
    file_id = message.photo[-1].file_id
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transactions (user_id, creator_id, type, amount, status, payment_method, screenshot_file_id, reference, created_at)
        VALUES (?, ?, 'subscription', ?, 'pending', 'manual', ?, ?, ?)
    """, (message.from_user.id, creator_id, amount, file_id, plan, datetime.now().isoformat()))
    tx_id = cur.lastrowid
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, "✅ Screenshot received. Waiting for admin approval.")

    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_tx_{tx_id}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_tx_{tx_id}")
    )
    bot.send_photo(ADMIN_ID, file_id, caption=
        f"💰 SUBSCRIPTION\nUser: {username} ({message.from_user.id})\n"
        f"Creator: {creator_id}\nPlan: {plan}\nAmount: {format_price(amount)}\nTX #{tx_id}",
        reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith(("approve_tx_", "reject_tx_")))
def cb_review_tx(call):
    if not is_admin(call.from_user.id):
        return
    action = "approve" if call.data.startswith("approve_tx_") else "reject"
    tx_id = int(call.data.split("_")[-1])

    conn = get_db()
    tx = conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
    if not tx or tx["status"] != "pending":
        bot.answer_callback_query(call.id, "Already processed", show_alert=True)
        conn.close()
        return

    if action == "approve":
        conn.execute("UPDATE transactions SET status='completed', reviewed_at=? WHERE id=?",
                     (datetime.now().isoformat(), tx_id))
        if tx["type"] == "subscription":
            plan = tx["reference"] or "monthly"
            days = 30 if plan == "monthly" else 90
            start, end = datetime.now(), datetime.now() + timedelta(days=days)
            conn.execute("""
                INSERT INTO subscriptions (user_id, creator_id, plan, amount, status, start_date, end_date, payment_method, created_at)
                VALUES (?, ?, ?, ?, 'active', ?, ?, 'manual', ?)
                ON CONFLICT(user_id, creator_id) DO UPDATE SET
                    plan=excluded.plan, amount=excluded.amount, status='active',
                    start_date=excluded.start_date, end_date=excluded.end_date
            """, (tx["user_id"], tx["creator_id"], plan, tx["amount"],
                  start.isoformat(), end.isoformat(), datetime.now().isoformat()))
            conn.execute("UPDATE creators SET total_subscribers=total_subscribers+1, total_earnings=total_earnings+? WHERE user_id=?",
                         (tx["amount"], tx["creator_id"]))
            try:
                bot.send_message(tx["user_id"], f"✅ Subscription activated until {end.strftime('%d/%m/%Y')}")
            except:
                pass
        elif tx["type"] == "creator_fee":
            conn.execute("UPDATE users SET role='creator', creator_verified=2 WHERE user_id=?", (tx["user_id"],))
            conn.execute("INSERT OR IGNORE INTO creators (user_id, display_name, created_at) VALUES (?, 'New Creator', ?)",
                         (tx["user_id"], datetime.now().isoformat()))
            try:
                bot.send_message(tx["user_id"], "🎉 You are now a verified Creator!")
            except:
                pass
        conn.commit()
        bot.edit_message_caption(caption=(call.message.caption or "") + "\n\n✅ APPROVED",
                                 chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id, "Approved")
    else:
        conn.execute("UPDATE transactions SET status='rejected', reviewed_at=? WHERE id=?",
                     (datetime.now().isoformat(), tx_id))
        conn.commit()
        try:
            bot.send_message(tx["user_id"], "❌ Payment rejected.")
        except:
            pass
        bot.edit_message_caption(caption=(call.message.caption or "") + "\n\n❌ REJECTED",
                                 chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id, "Rejected")
    conn.close()

@bot.callback_query_handler(func=lambda c: c.data.startswith("cancel_sub_"))
def cb_cancel_sub(call):
    creator_id = int(call.data.split("_")[-1])
    conn = get_db()
    conn.execute("UPDATE subscriptions SET status='cancelled' WHERE user_id=? AND creator_id=? AND status='active'",
                 (call.from_user.id, creator_id))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "Cancelled")
    bot.edit_message_text("Subscription cancelled.", call.message.chat.id, call.message.message_id,
                          reply_markup=types.InlineKeyboardMarkup().add(
                              types.InlineKeyboardButton("« Back", callback_data=f"creator_{creator_id}")))

@bot.callback_query_handler(func=lambda c: c.data.startswith("report_"))
def cb_report(call):
    reported_id = int(call.data.split("_")[1])
    lang = get_lang(call.from_user.id)
    kb = types.InlineKeyboardMarkup()
    for label, code in [("Inappropriate", "inappropriate"), ("Spam", "spam"), ("Underage", "underage"), ("Other", "other")]:
        kb.add(types.InlineKeyboardButton(label, callback_data=f"report_reason_{reported_id}_{code}"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data=f"creator_{reported_id}"))
    bot.edit_message_text("Select reason:", call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("report_reason_"))
def cb_report_reason(call):
    parts = call.data.split("_")
    reported_id, reason = int(parts[2]), parts[3]
    conn = get_db()
    conn.execute("INSERT INTO reports (reporter_id, reported_id, reason, status, created_at) VALUES (?,?,?,'open',?)",
                 (call.from_user.id, reported_id, reason, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "Report sent")
    bot.edit_message_text("✅ Report sent.", call.message.chat.id, call.message.message_id,
                          reply_markup=types.InlineKeyboardMarkup().add(
                              types.InlineKeyboardButton("« Back", callback_data=f"creator_{reported_id}")))
    try:
        bot.send_message(ADMIN_ID, f"📢 Report\nFrom: {call.from_user.id}\nTarget: {reported_id}\nReason: {reason}")
    except:
        pass

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

# ==================== PANEL ADMIN BÁSICO ====================
@bot.callback_query_handler(func=lambda c: c.data == "admin_panel")
def cb_admin_panel(call):
    if not is_admin(call.from_user.id):
        return
    conn = get_db()
    pending_tx = conn.execute("SELECT COUNT(*) FROM transactions WHERE status='pending'").fetchone()[0]
    pending_ver = conn.execute("SELECT COUNT(*) FROM verifications WHERE status='pending'").fetchone()[0]
    conn.close()
    text = f"🔧 <b>Admin Panel</b>\n\nPending TX: {pending_tx}\nPending verifications: {pending_ver}\nGroup: {GROUP_INVITE}"
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
    print("OnlyFans_ManagerBot V4 started")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"WebApp URL: {WEBAPP_VERIFICATION_URL}")
    print(f"Group: {GROUP_INVITE}")
    bot.infinity_polling()
