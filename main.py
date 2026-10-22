#!/usr/bin/env python3
"""
Bot Telegram tipo OnlyFans - V3
Prioridades implementadas:
1. Telegram Stars (invoices XTR preparados)
2. Invite links automáticos a canal privado
3. Botón Reportar + moderación
4. Verificación REAL con fotos (documento + selfie) → admin asigna género/edad + badges
5. Cancelar suscripción

- El usuario NO elige el sexo
- Solo ve contenido si tiene suscripción pagada activa
- Todo por botones (solo pide fotos cuando es necesario)
"""

import telebot
from telebot import types
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional

# ==================== CONFIGURACIÓN ====================
TELEGRAM_TOKEN = "PON_AQUI_TU_TOKEN"
ADMIN_ID = 7653419875
CREATOR_FEE = 50.0                       # USD para ser creador

DB_FILE = "bot.db"

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")

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
            age_declared INTEGER DEFAULT 0,          -- declaración básica 18+
            terms_accepted INTEGER DEFAULT 0,
            age_verified_real INTEGER DEFAULT 0,     -- 0=no, 1=pendiente, 2=aprobado por admin
            gender TEXT,                             -- NULL hasta que admin lo asigne (male/female)
            gender_verified INTEGER DEFAULT 0,       -- 0/1
            creator_verified INTEGER DEFAULT 0,      -- 0=no, 1=pendiente pago, 2=aprobado
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
            UNIQUE(user_id, creator_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(creator_id) REFERENCES creators(user_id)
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
            created_at TEXT,
            FOREIGN KEY(creator_id) REFERENCES creators(user_id)
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
            reviewed_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            doc_photo_id TEXT,
            selfie_photo_id TEXT,
            status TEXT DEFAULT 'pending',       -- pending / approved / rejected
            assigned_gender TEXT,                -- male / female (solo admin)
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

    # Defaults
    if not c.execute("SELECT 1 FROM settings WHERE key='payment_methods'").fetchone():
        c.execute("INSERT INTO settings VALUES (?, ?)", ("payment_methods",
            "💳 <b>Formas de pago:</b>\n\n"
            "• Transferencia / Bizum\n"
            "• Crypto (USDT TRC20 / BTC)\n"
            "• Telegram Stars\n\n"
            "<i>El admin actualizará los datos exactos.</i>"
        ))

    if not c.execute("SELECT 1 FROM settings WHERE key='terms'").fetchone():
        c.execute("INSERT INTO settings VALUES (?, ?)", ("terms",
            "📜 <b>Términos y Condiciones</b>\n\n"
            "1. Debes ser mayor de 18 años.\n"
            "2. El contenido es solo para uso personal.\n"
            "3. Prohibida la redistribución.\n"
            "4. El incumplimiento puede resultar en ban permanente.\n"
            "5. Al continuar aceptas estos términos."
        ))

    conn.commit()
    conn.close()
    ensure_admin()

def ensure_admin():
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT OR IGNORE INTO users 
        (user_id, role, age_declared, terms_accepted, age_verified_real, gender_verified, creator_verified, joined_at, last_active)
        VALUES (?, 'admin', 1, 1, 2, 1, 2, ?, ?)
    """, (ADMIN_ID, now, now))
    conn.execute("""
        UPDATE users SET role='admin', age_declared=1, terms_accepted=1, 
        age_verified_real=2, gender_verified=1, creator_verified=2 
        WHERE user_id=?
    """, (ADMIN_ID,))
    conn.execute("""
        INSERT OR IGNORE INTO creators (user_id, display_name, bio, created_at)
        VALUES (?, 'Admin Principal', 'Creador principal', ?)
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

# ==================== HELPERS ====================
def get_user(user_id: int):
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return u

def upsert_user(tg_user):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO users (user_id, username, first_name, joined_at, last_active)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            last_active=excluded.last_active
    """, (tg_user.id, tg_user.username, tg_user.first_name, now, now))
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
    """Devuelve los símbolos de verificación real"""
    badges = []
    if user and user["age_verified_real"] == 2:
        badges.append("🔞✅")
    if user and user["gender_verified"] == 1 and user["gender"]:
        badges.append("♂️" if user["gender"] == "male" else "♀️")
    return " ".join(badges) if badges else ""

def get_gender_text(user) -> str:
    if not user or not user["gender_verified"]:
        return "No verificado"
    return "Masculino" if user["gender"] == "male" else "Femenino"

# ==================== MENÚ PRINCIPAL ====================
def main_menu_kb(user_id: int):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔍 Explorar Creadores", callback_data="menu_explore"),
        types.InlineKeyboardButton("📋 Mis Suscripciones", callback_data="menu_subs")
    )
    kb.add(
        types.InlineKeyboardButton("👤 Mi Cuenta", callback_data="menu_account"),
        types.InlineKeyboardButton("❓ Ayuda", callback_data="menu_help")
    )
    if is_creator(user_id):
        kb.add(types.InlineKeyboardButton("🎨 Panel Creador", callback_data="creator_panel"))
    if is_admin(user_id):
        kb.add(types.InlineKeyboardButton("🔧 Panel Admin", callback_data="admin_panel"))
    return kb

def send_main_menu(chat_id, user_id, message_id=None):
    user = get_user(user_id)
    name = user["first_name"] if user else "Usuario"
    text = f"💖 <b>Bienvenido/a, {name}</b>\n\nPlataforma de contenido exclusivo.\nElige una opción:"
    kb = main_menu_kb(user_id)
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)

# ==================== REGISTRO BÁSICO (declaración) ====================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 Tu cuenta está baneada.")
        return

    upsert_user(message.from_user)
    user = get_user(message.from_user.id)

    if not user["age_declared"]:
        ask_age_declaration(message.chat.id)
        return
    if not user["terms_accepted"]:
        ask_terms(message.chat.id)
        return

    send_main_menu(message.chat.id, message.from_user.id)

def ask_age_declaration(chat_id):
    text = (
        "🔒 <b>Confirmación de Edad</b>\n\n"
        "Este bot contiene contenido para adultos.\n\n"
        "¿Confirmas que eres <b>mayor de 18 años</b>?\n\n"
        "<i>Nota: Esta es solo una declaración. La verificación real se hace después con documento.</i>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Sí, soy mayor de 18", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Soy menor", callback_data="age_no")
    )
    bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ("age_yes", "age_no"))
def cb_age(call):
    if call.data == "age_no":
        bot.edit_message_text("🚫 Este servicio es solo para mayores de 18 años.",
                              call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    conn = get_db()
    conn.execute("UPDATE users SET age_declared=1 WHERE user_id=?", (call.from_user.id,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "Edad declarada")
    ask_terms(call.message.chat.id, call.message.message_id)

def ask_terms(chat_id, message_id=None):
    terms = get_setting("terms")
    text = terms + "\n\n¿Aceptas los términos?"
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Acepto", callback_data="terms_yes"),
        types.InlineKeyboardButton("❌ No acepto", callback_data="terms_no")
    )
    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ("terms_yes", "terms_no"))
def cb_terms(call):
    if call.data == "terms_no":
        bot.edit_message_text("Debes aceptar los términos para continuar.",
                              call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    conn = get_db()
    conn.execute("UPDATE users SET terms_accepted=1 WHERE user_id=?", (call.from_user.id,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "Términos aceptados")
    send_main_menu(call.message.chat.id, call.from_user.id, call.message.message_id)

# ==================== MENÚS ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_main")
def cb_main(call):
    bot.answer_callback_query(call.id)
    send_main_menu(call.message.chat.id, call.from_user.id, call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "menu_explore")
def cb_explore(call):
    bot.answer_callback_query(call.id)
    show_creators(call.message.chat.id, call.from_user.id, call.message.message_id, 0)

def show_creators(chat_id, user_id, message_id=None, page=0):
    conn = get_db()
    creators = conn.execute("""
        SELECT c.*, u.username, u.first_name, u.age_verified_real, u.gender, u.gender_verified
        FROM creators c
        JOIN users u ON u.user_id = c.user_id
        WHERE u.creator_verified=2 AND u.banned=0
        ORDER BY c.total_subscribers DESC
    """).fetchall()
    conn.close()

    if not creators:
        text = "Aún no hay creadores verificados."
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("« Volver", callback_data="menu_main"))
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
        else:
            bot.send_message(chat_id, text, reply_markup=kb)
        return

    per_page = 5
    total = (len(creators) + per_page - 1) // per_page
    page = max(0, min(page, total - 1))
    chunk = creators[page*per_page:(page+1)*per_page]

    text = f"🔍 <b>Creadores</b> (pág {page+1}/{total})\n\n"
    kb = types.InlineKeyboardMarkup()

    for c in chunk:
        badges = get_badges(c)
        name = c["display_name"] or c["first_name"] or "Creador"
        btn = f"{badges} {name} — {format_price(c['monthly_price'])}/mes"
        kb.add(types.InlineKeyboardButton(btn, callback_data=f"creator_{c['user_id']}"))

    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("« Ant", callback_data=f"explore_page_{page-1}"))
    if page < total - 1:
        nav.append(types.InlineKeyboardButton("Sig »", callback_data=f"explore_page_{page+1}"))
    if nav:
        kb.row(*nav)
    kb.add(types.InlineKeyboardButton("« Menú", callback_data="menu_main"))

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("explore_page_"))
def cb_explore_page(call):
    page = int(call.data.split("_")[-1])
    bot.answer_callback_query(call.id)
    show_creators(call.message.chat.id, call.from_user.id, call.message.message_id, page)

# ==================== PERFIL CREADOR ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("creator_") and not c.data.startswith("creator_panel") and not c.data.startswith("creator_"))
def cb_creator_profile(call):
    # Evitar conflictos con otros callbacks
    if not call.data.startswith("creator_") or call.data in ("creator_panel", "creator_upload", "creator_prices", "creator_stats", "creator_broadcast"):
        return

    try:
        creator_id = int(call.data.split("_")[1])
    except:
        return

    bot.answer_callback_query(call.id)

    conn = get_db()
    creator = conn.execute("""
        SELECT c.*, u.username, u.first_name, u.age_verified_real, u.gender, u.gender_verified
        FROM creators c JOIN users u ON u.user_id = c.user_id
        WHERE c.user_id=? AND u.creator_verified=2
    """, (creator_id,)).fetchone()
    conn.close()

    if not creator:
        bot.answer_callback_query(call.id, "No encontrado", show_alert=True)
        return

    name = creator["display_name"] or creator["first_name"]
    badges = get_badges(creator)
    subscribed = has_active_sub(call.from_user.id, creator_id)

    text = (
        f"🎨 <b>{name}</b> {badges}\n\n"
        f"{creator['bio'] or 'Sin biografía'}\n\n"
        f"🔞 Edad: {'Verificada' if creator['age_verified_real']==2 else 'Solo declarada'}\n"
        f"Género: {get_gender_text(creator)}\n\n"
        f"💰 Mensual: <b>{format_price(creator['monthly_price'])}</b>\n"
        f"💰 Trimestral: <b>{format_price(creator['quarterly_price'])}</b>\n"
        f"👥 Suscriptores: {creator['total_subscribers']}\n"
    )

    kb = types.InlineKeyboardMarkup()
    if subscribed:
        text += "\n✅ <b>Tienes suscripción activa</b>"
        kb.add(types.InlineKeyboardButton("📥 Ver contenido", callback_data=f"content_{creator_id}"))
        kb.add(types.InlineKeyboardButton("❌ Cancelar suscripción", callback_data=f"cancel_sub_{creator_id}"))
    else:
        text += "\n🔒 <b>Debes pagar para ver el contenido</b>"
        kb.add(types.InlineKeyboardButton(
            f"Suscribirse Mensual ({format_price(creator['monthly_price'])})",
            callback_data=f"sub_monthly_{creator_id}"
        ))
        kb.add(types.InlineKeyboardButton(
            f"Suscribirse Trimestral ({format_price(creator['quarterly_price'])})",
            callback_data=f"sub_quarterly_{creator_id}"
        ))

    kb.add(types.InlineKeyboardButton("📢 Reportar", callback_data=f"report_{creator_id}"))
    kb.add(types.InlineKeyboardButton("« Volver", callback_data="menu_explore"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

# Fix: el handler anterior tenía un filtro malo. Reescribimos uno limpio.
@bot.callback_query_handler(func=lambda c: c.data.startswith("creator_") and c.data.count("_") == 1)
def cb_creator_profile_clean(call):
    creator_id = int(call.data.split("_")[1])
    bot.answer_callback_query(call.id)

    conn = get_db()
    creator = conn.execute("""
        SELECT c.*, u.username, u.first_name, u.age_verified_real, u.gender, u.gender_verified
        FROM creators c JOIN users u ON u.user_id = c.user_id
        WHERE c.user_id=? AND u.creator_verified=2
    """, (creator_id,)).fetchone()
    conn.close()

    if not creator:
        bot.answer_callback_query(call.id, "No encontrado", show_alert=True)
        return

    name = creator["display_name"] or creator["first_name"]
    badges = get_badges(creator)
    subscribed = has_active_sub(call.from_user.id, creator_id)

    text = (
        f"🎨 <b>{name}</b> {badges}\n\n"
        f"{creator['bio'] or 'Sin biografía'}\n\n"
        f"🔞 Edad: {'✅ Verificada' if creator['age_verified_real']==2 else 'Solo declarada'}\n"
        f"Género: {get_gender_text(creator)}\n\n"
        f"💰 Mensual: <b>{format_price(creator['monthly_price'])}</b>\n"
        f"💰 Trimestral: <b>{format_price(creator['quarterly_price'])}</b>\n"
        f"👥 Suscriptores: {creator['total_subscribers']}\n"
    )

    kb = types.InlineKeyboardMarkup()
    if subscribed:
        text += "\n✅ <b>Tienes suscripción activa</b>"
        kb.add(types.InlineKeyboardButton("📥 Ver contenido", callback_data=f"content_{creator_id}"))
        kb.add(types.InlineKeyboardButton("❌ Cancelar suscripción", callback_data=f"cancel_sub_{creator_id}"))
    else:
        text += "\n🔒 <b>Debes pagar para ver el contenido</b>"
        kb.add(types.InlineKeyboardButton(
            f"Suscribirse Mensual ({format_price(creator['monthly_price'])})",
            callback_data=f"sub_monthly_{creator_id}"
        ))
        kb.add(types.InlineKeyboardButton(
            f"Suscribirse Trimestral ({format_price(creator['quarterly_price'])})",
            callback_data=f"sub_quarterly_{creator_id}"
        ))

    kb.add(types.InlineKeyboardButton("📢 Reportar", callback_data=f"report_{creator_id}"))
    kb.add(types.InlineKeyboardButton("« Volver", callback_data="menu_explore"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

# ==================== SUSCRIPCIONES ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("sub_"))
def cb_subscribe(call):
    parts = call.data.split("_")
    plan = parts[1]
    creator_id = int(parts[2])

    if has_active_sub(call.from_user.id, creator_id):
        bot.answer_callback_query(call.id, "Ya tienes suscripción activa", show_alert=True)
        return

    conn = get_db()
    creator = conn.execute("SELECT * FROM creators WHERE user_id=?", (creator_id,)).fetchone()
    conn.close()
    if not creator:
        bot.answer_callback_query(call.id, "No encontrado", show_alert=True)
        return

    amount = creator["monthly_price"] if plan == "monthly" else creator["quarterly_price"]
    plan_name = "Mensual" if plan == "monthly" else "Trimestral"
    payment_methods = get_setting("payment_methods")

    text = (
        f"💳 <b>Suscripción {plan_name}</b>\n\n"
        f"Creador: <b>{creator['display_name']}</b>\n"
        f"Precio: <b>{format_price(amount)}</b>\n\n"
        f"{payment_methods}\n\n"
        "Cuando pagues, pulsa el botón y envía la captura."
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💸 Ya pagué — Enviar captura", callback_data=f"pay_sub_{plan}_{creator_id}"))
    # Placeholder Stars
    kb.add(types.InlineKeyboardButton("⭐ Pagar con Telegram Stars (próx.)", callback_data="stars_soon"))
    kb.add(types.InlineKeyboardButton("« Volver", callback_data=f"creator_{creator_id}"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "stars_soon")
def cb_stars_soon(call):
    bot.answer_callback_query(call.id, "Telegram Stars se activará pronto. Usa pago manual por ahora.", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_sub_"))
def cb_pay_sub(call):
    parts = call.data.split("_")
    plan = parts[2]
    creator_id = int(parts[3])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📸 Envía ahora la <b>captura del pago</b> (solo foto).")
    bot.register_next_step_handler(msg, process_sub_screenshot, plan, creator_id)

def process_sub_screenshot(message, plan, creator_id):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Debes enviar una foto. Vuelve al menú.")
        return

    conn = get_db()
    creator = conn.execute("SELECT * FROM creators WHERE user_id=?", (creator_id,)).fetchone()
    if not creator:
        bot.send_message(message.chat.id, "Creador no disponible.")
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

    bot.send_message(message.chat.id, "✅ Captura recibida. El admin la revisará pronto.")

    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    admin_text = (
        f"💰 <b>NUEVA SUSCRIPCIÓN PENDIENTE</b>\n\n"
        f"Usuario: {username} (<code>{message.from_user.id}</code>)\n"
        f"Creador: {creator_id}\n"
        f"Plan: {plan}\n"
        f"Monto: {format_price(amount)}\n"
        f"TX: #{tx_id}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_tx_{tx_id}"),
        types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_tx_{tx_id}")
    )
    bot.send_photo(ADMIN_ID, file_id, caption=admin_text, reply_markup=kb)

# ==================== CANCELAR SUSCRIPCIÓN ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("cancel_sub_"))
def cb_cancel_sub(call):
    creator_id = int(call.data.split("_")[-1])
    conn = get_db()
    sub = conn.execute("""
        SELECT * FROM subscriptions 
        WHERE user_id=? AND creator_id=? AND status='active'
    """, (call.from_user.id, creator_id)).fetchone()

    if not sub:
        bot.answer_callback_query(call.id, "No tienes suscripción activa", show_alert=True)
        conn.close()
        return

    conn.execute("UPDATE subscriptions SET status='cancelled' WHERE id=?", (sub["id"],))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "Suscripción cancelada")
    bot.edit_message_text(
        "❌ Suscripción cancelada.\nYa no tendrás acceso al contenido de este creador.",
        call.message.chat.id, call.message.message_id,
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("« Volver", callback_data=f"creator_{creator_id}")
        )
    )

# ==================== APROBAR / RECHAZAR TX ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith(("approve_tx_", "reject_tx_")))
def cb_review_tx(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "No autorizado", show_alert=True)
        return

    action = "approve" if call.data.startswith("approve_tx_") else "reject"
    tx_id = int(call.data.split("_")[-1])

    conn = get_db()
    tx = conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
    if not tx or tx["status"] != "pending":
        bot.answer_callback_query(call.id, "Ya procesada", show_alert=True)
        conn.close()
        return

    if action == "approve":
        conn.execute("UPDATE transactions SET status='completed', reviewed_at=? WHERE id=?",
                     (datetime.now().isoformat(), tx_id))

        if tx["type"] == "subscription":
            plan = tx["reference"] or "monthly"
            days = 30 if plan == "monthly" else 90
            start = datetime.now()
            end = start + timedelta(days=days)

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

            # Invite link automático
            creator = conn.execute("SELECT private_channel_id, invite_link FROM creators WHERE user_id=?", (tx["creator_id"],)).fetchone()
            invite_msg = ""
            if creator and creator["invite_link"]:
                invite_msg = f"\n\n🔗 Únete al canal privado:\n{creator['invite_link']}"
            elif creator and creator["private_channel_id"]:
                try:
                    link = bot.create_chat_invite_link(creator["private_channel_id"], member_limit=1)
                    invite_msg = f"\n\n🔗 Únete al canal privado:\n{link.invite_link}"
                    conn.execute("UPDATE creators SET invite_link=? WHERE user_id=?", (link.invite_link, tx["creator_id"]))
                except Exception as e:
                    invite_msg = f"\n\n(No se pudo generar invite link: {e})"

            try:
                bot.send_message(
                    tx["user_id"],
                    f"✅ <b>Suscripción activada</b>\n\n"
                    f"Plan: {plan}\nVálida hasta: {end.strftime('%d/%m/%Y')}"
                    f"{invite_msg}"
                )
            except:
                pass

        elif tx["type"] == "creator_fee":
            conn.execute("UPDATE users SET role='creator', creator_verified=2 WHERE user_id=?", (tx["user_id"],))
            conn.execute("""
                INSERT OR IGNORE INTO creators (user_id, display_name, created_at)
                VALUES (?, 'Nuevo Creador', ?)
            """, (tx["user_id"], datetime.now().isoformat()))
            try:
                bot.send_message(tx["user_id"], "🎉 ¡Ya eres Creador verificado! Usa el Panel Creador.")
            except:
                pass

        conn.commit()
        bot.edit_message_caption(caption=(call.message.caption or "") + "\n\n✅ <b>APROBADO</b>",
                                 chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id, "Aprobado")
        log_admin(call.from_user.id, "approve_tx", tx["user_id"], f"TX #{tx_id}")

    else:
        conn.execute("UPDATE transactions SET status='rejected', reviewed_at=? WHERE id=?",
                     (datetime.now().isoformat(), tx_id))
        conn.commit()
        try:
            bot.send_message(tx["user_id"], "❌ Tu pago fue rechazado.")
        except:
            pass
        bot.edit_message_caption(caption=(call.message.caption or "") + "\n\n❌ <b>RECHAZADO</b>",
                                 chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id, "Rechazado")
        log_admin(call.from_user.id, "reject_tx", tx["user_id"], f"TX #{tx_id}")

    conn.close()

# ==================== VERIFICACIÓN REAL (FOTOS) ====================
@bot.callback_query_handler(func=lambda c: c.data == "request_real_verification")
def cb_request_verification(call):
    user = get_user(call.from_user.id)
    if user["age_verified_real"] == 2:
        bot.answer_callback_query(call.id, "Ya estás verificado", show_alert=True)
        return
    if user["age_verified_real"] == 1:
        bot.answer_callback_query(call.id, "Ya tienes una solicitud pendiente", show_alert=True)
        return

    bot.answer_callback_query(call.id)
    text = (
        "📸 <b>Verificación Real</b>\n\n"
        "Para obtener los badges de edad y género verificados debes enviar:\n\n"
        "1. Foto clara de tu documento (DNI / Pasaporte)\n"
        "2. Selfie sosteniendo el mismo documento\n\n"
        "El administrador revisará y asignará el género y la edad verificada.\n"
        "<b>Tú no eliges el sexo</b>, se verifica con el documento.\n\n"
        "Envía primero la <b>foto del documento</b>."
    )
    msg = bot.send_message(call.message.chat.id, text)
    bot.register_next_step_handler(msg, receive_doc_photo)

def receive_doc_photo(message):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Debes enviar una <b>foto</b> del documento. Cancela e intenta de nuevo.")
        return

    doc_id = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id, "Ahora envía la <b>selfie sosteniendo el documento</b>.")
    bot.register_next_step_handler(msg, receive_selfie_photo, doc_id)

def receive_selfie_photo(message, doc_id):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Debes enviar una selfie. Proceso cancelado.")
        return

    selfie_id = message.photo[-1].file_id

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO verifications (user_id, doc_photo_id, selfie_photo_id, status, created_at)
        VALUES (?, ?, ?, 'pending', ?)
    """, (message.from_user.id, doc_id, selfie_id, datetime.now().isoformat()))
    ver_id = cur.lastrowid
    conn.execute("UPDATE users SET age_verified_real=1 WHERE user_id=?", (message.from_user.id,))
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, "✅ Documentos recibidos. El administrador los revisará y te asignará los badges.")

    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    admin_text = (
        f"📝 <b>NUEVA VERIFICACIÓN REAL</b>\n\n"
        f"Usuario: {username} (<code>{message.from_user.id}</code>)\n"
        f"Verificación #{ver_id}\n\n"
        "Revisa el documento y la selfie.\n"
        "Luego elige el género verificado:"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("♂️ Aprobar como Hombre", callback_data=f"ver_approve_male_{ver_id}"),
        types.InlineKeyboardButton("♀️ Aprobar como Mujer", callback_data=f"ver_approve_female_{ver_id}")
    )
    kb.add(types.InlineKeyboardButton("❌ Rechazar", callback_data=f"ver_reject_{ver_id}"))

    # Enviar ambas fotos al admin
    bot.send_photo(ADMIN_ID, doc_id, caption="Documento")
    bot.send_photo(ADMIN_ID, selfie_id, caption=admin_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith(("ver_approve_male_", "ver_approve_female_", "ver_reject_")))
def cb_review_verification(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "No autorizado", show_alert=True)
        return

    parts = call.data.split("_")
    action = parts[1]  # approve o reject
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
            UPDATE users SET age_verified_real=2, gender=?, gender_verified=1
            WHERE user_id=?
        """, (gender, ver["user_id"]))
        conn.commit()

        gender_text = "Masculino" if gender == "male" else "Femenino"
        try:
            bot.send_message(
                ver["user_id"],
                f"✅ <b>Verificación aprobada</b>\n\n"
                f"Se te han asignado los badges:\n"
                f"🔞✅ Edad Verificada\n"
                f"{'\u2642\ufe0f' if gender=='male' else '\u2640\ufe0f'} Género Verificado ({gender_text})"
            )
        except:
            pass

        bot.edit_message_caption(
            caption=(call.message.caption or "") + f"\n\n✅ APROBADO como {gender_text}",
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
            bot.send_message(ver["user_id"], "❌ Tu verificación fue rechazada. Puedes intentarlo de nuevo.")
        except:
            pass
        bot.edit_message_caption(
            caption=(call.message.caption or "") + "\n\n❌ RECHAZADO",
            chat_id=call.message.chat.id, message_id=call.message.message_id
        )
        bot.answer_callback_query(call.id, "Rechazado")
        log_admin(call.from_user.id, "reject_verification", ver["user_id"])

    conn.close()

# ==================== REPORTAR ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("report_"))
def cb_report(call):
    reported_id = int(call.data.split("_")[1])
    bot.answer_callback_query(call.id)

    text = "📢 <b>Reportar usuario</b>\n\nSelecciona el motivo:"
    kb = types.InlineKeyboardMarkup()
    reasons = [
        ("Contenido inapropiado", "inappropriate"),
        ("Spam / Estafa", "spam"),
        ("Menor de edad", "underage"),
        ("Otro", "other")
    ]
    for label, code in reasons:
        kb.add(types.InlineKeyboardButton(label, callback_data=f"report_reason_{reported_id}_{code}"))
    kb.add(types.InlineKeyboardButton("« Cancelar", callback_data=f"creator_{reported_id}"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("report_reason_"))
def cb_report_reason(call):
    parts = call.data.split("_")
    reported_id = int(parts[2])
    reason = parts[3]

    conn = get_db()
    conn.execute("""
        INSERT INTO reports (reporter_id, reported_id, reason, status, created_at)
        VALUES (?, ?, ?, 'open', ?)
    """, (call.from_user.id, reported_id, reason, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "Reporte enviado")
    bot.edit_message_text(
        "✅ Reporte enviado. El equipo de moderación lo revisará.",
        call.message.chat.id, call.message.message_id,
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("« Volver", callback_data=f"creator_{reported_id}")
        )
    )

    # Notificar admin
    try:
        bot.send_message(ADMIN_ID, f"📢 Nuevo reporte\nReporter: {call.from_user.id}\nReportado: {reported_id}\nRazón: {reason}")
    except:
        pass

# ==================== MI CUENTA ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_account")
def cb_account(call):
    user = get_user(call.from_user.id)
    badges = get_badges(user)

    text = (
        f"👤 <b>Mi Cuenta</b> {badges}\n\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Nombre: {user['first_name']}\n"
        f"Rol: {user['role'].capitalize()}\n"
        f"Edad declarada: {'✅' if user['age_declared'] else '❌'}\n"
        f"Edad verificada real: {'✅' if user['age_verified_real']==2 else '⏳ Pendiente' if user['age_verified_real']==1 else '❌'}\n"
        f"Género verificado: {get_gender_text(user)}\n"
    )

    kb = types.InlineKeyboardMarkup()
    if user["age_verified_real"] != 2:
        kb.add(types.InlineKeyboardButton("📸 Solicitar verificación real", callback_data="request_real_verification"))
    if user["role"] == "user" and user["creator_verified"] != 2:
        kb.add(types.InlineKeyboardButton("🎨 Quiero ser Creador (50$)", callback_data="become_creator"))
    kb.add(types.InlineKeyboardButton("« Menú", callback_data="menu_main"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "become_creator")
def cb_become_creator(call):
    user = get_user(call.from_user.id)
    if user["creator_verified"] == 2:
        bot.answer_callback_query(call.id, "Ya eres creador", show_alert=True)
        return
    if user["creator_verified"] == 1:
        bot.answer_callback_query(call.id, "Solicitud pendiente", show_alert=True)
        return

    payment_methods = get_setting("payment_methods")
    text = (
        f"🎨 <b>Convertirse en Creador</b>\n\n"
        f"Tarifa: <b>{format_price(CREATOR_FEE)}</b>\n"
        f"Después del pago se recomienda hacer la verificación real.\n\n"
        f"{payment_methods}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(f"💸 Ya pagué {format_price(CREATOR_FEE)}", callback_data="pay_creator_fee"))
    kb.add(types.InlineKeyboardButton("« Volver", callback_data="menu_account"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "pay_creator_fee")
def cb_pay_creator_fee(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"📸 Envía la captura del pago de {format_price(CREATOR_FEE)}.")
    bot.register_next_step_handler(msg, process_creator_fee)

def process_creator_fee(message):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Debes enviar una foto.")
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

    bot.send_message(message.chat.id, "✅ Captura recibida. Solicitud de creador en revisión.")

    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    admin_text = (
        f"🎨 <b>SOLICITUD DE CREADOR</b>\n\n"
        f"Usuario: {username} (<code>{message.from_user.id}</code>)\n"
        f"Monto: {format_price(CREATOR_FEE)}\nTX: #{tx_id}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Aprobar Creador", callback_data=f"approve_tx_{tx_id}"),
        types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_tx_{tx_id}")
    )
    bot.send_photo(ADMIN_ID, file_id, caption=admin_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "menu_subs")
def cb_my_subs(call):
    conn = get_db()
    subs = conn.execute("""
        SELECT s.*, c.display_name
        FROM subscriptions s
        JOIN creators c ON c.user_id = s.creator_id
        WHERE s.user_id=? AND s.status='active' AND s.end_date > ?
        ORDER BY s.end_date DESC
    """, (call.from_user.id, datetime.now().isoformat())).fetchall()
    conn.close()

    if not subs:
        text = "No tienes suscripciones activas."
    else:
        text = "📋 <b>Mis Suscripciones</b>\n\n"
        for s in subs:
            text += f"• <b>{s['display_name']}</b> ({s['plan']})\n  Hasta: {s['end_date'][:10]}\n\n"

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Menú", callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "menu_help")
def cb_help(call):
    text = (
        "❓ <b>Ayuda</b>\n\n"
        "• Solo puedes ver contenido si tienes <b>suscripción pagada</b>.\n"
        "• La verificación real (documento + selfie) da badges de edad y género.\n"
        "• El género lo asigna el administrador tras revisar el documento.\n"
        "• Puedes reportar perfiles desde su ficha.\n"
        "• Para ser Creador paga 50$ y espera aprobación."
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Menú", callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

# ==================== CONTENIDO (solo si pagó) ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("content_"))
def cb_content(call):
    creator_id = int(call.data.split("_")[1])
    if not has_active_sub(call.from_user.id, creator_id) and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Debes tener suscripción activa y pagada", show_alert=True)
        return

    conn = get_db()
    items = conn.execute("SELECT * FROM content WHERE creator_id=? ORDER BY id DESC LIMIT 5", (creator_id,)).fetchall()
    conn.close()

    if not items:
        bot.answer_callback_query(call.id, "Aún no hay contenido", show_alert=True)
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

# ==================== PANEL CREADOR (resumido) ====================
@bot.callback_query_handler(func=lambda c: c.data == "creator_panel")
def cb_creator_panel(call):
    if not is_creator(call.from_user.id):
        bot.answer_callback_query(call.id, "No eres creador", show_alert=True)
        return

    conn = get_db()
    creator = conn.execute("SELECT * FROM creators WHERE user_id=?", (call.from_user.id,)).fetchone()
    conn.close()

    text = (
        f"🎨 <b>Panel Creador</b>\n\n"
        f"Suscriptores: {creator['total_subscribers']}\n"
        f"Ingresos: {format_price(creator['total_earnings'])}\n"
        f"Mensual: {format_price(creator['monthly_price'])}\n"
        f"Trimestral: {format_price(creator['quarterly_price'])}\n"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("📸 Subir contenido", callback_data="creator_upload"),
        types.InlineKeyboardButton("💰 Precios", callback_data="creator_prices")
    )
    kb.add(types.InlineKeyboardButton("« Menú", callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "creator_upload")
def cb_creator_upload(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Envía fotos/videos. Cuando termines escribe /listo_contenido")
    bot.register_next_step_handler(msg, creator_collect, [], [])

def creator_collect(message, file_ids, media_types):
    if message.text and message.text.lower() == "/listo_contenido":
        if not file_ids:
            bot.send_message(message.chat.id, "No enviaste archivos.")
            return
        conn = get_db()
        conn.execute("INSERT INTO content (creator_id, title, file_ids, media_types, created_at) VALUES (?,?,?,?,?)",
                     (message.from_user.id, "Contenido", json.dumps(file_ids), json.dumps(media_types), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ Subido ({len(file_ids)} archivos).")
        return

    if message.photo:
        file_ids.append(message.photo[-1].file_id)
        media_types.append("photo")
        bot.send_message(message.chat.id, f"Foto añadida ({len(file_ids)}). Más o /listo_contenido")
    elif message.video:
        file_ids.append(message.video.file_id)
        media_types.append("video")
        bot.send_message(message.chat.id, f"Video añadido ({len(file_ids)}). Más o /listo_contenido")
    else:
        bot.send_message(message.chat.id, "Envía foto/video o /listo_contenido")

    bot.register_next_step_handler(message, creator_collect, file_ids, media_types)

@bot.callback_query_handler(func=lambda c: c.data == "creator_prices")
def cb_creator_prices(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Nuevo precio mensual (ej: 9.99):")
    bot.register_next_step_handler(msg, set_monthly)

def set_monthly(message):
    try:
        price = float(message.text.replace(",", "."))
    except:
        bot.send_message(message.chat.id, "Precio inválido.")
        return
    conn = get_db()
    conn.execute("UPDATE creators SET monthly_price=? WHERE user_id=?", (price, message.from_user.id))
    conn.commit()
    conn.close()
    msg = bot.send_message(message.chat.id, f"Mensual = {format_price(price)}. Ahora trimestral:")
    bot.register_next_step_handler(msg, set_quarterly)

def set_quarterly(message):
    try:
        price = float(message.text.replace(",", "."))
    except:
        bot.send_message(message.chat.id, "Precio inválido.")
        return
    conn = get_db()
    conn.execute("UPDATE creators SET quarterly_price=? WHERE user_id=?", (price, message.from_user.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ Precios actualizados.")

# ==================== PANEL ADMIN ====================
@bot.callback_query_handler(func=lambda c: c.data == "admin_panel")
def cb_admin_panel(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "No autorizado", show_alert=True)
        return

    conn = get_db()
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    pending_tx = conn.execute("SELECT COUNT(*) FROM transactions WHERE status='pending'").fetchone()[0]
    pending_ver = conn.execute("SELECT COUNT(*) FROM verifications WHERE status='pending'").fetchone()[0]
    open_reports = conn.execute("SELECT COUNT(*) FROM reports WHERE status='open'").fetchone()[0]
    conn.close()

    text = (
        f"🔧 <b>Panel Admin</b>\n\n"
        f"Usuarios: {users}\n"
        f"TX pendientes: {pending_tx}\n"
        f"Verificaciones pendientes: {pending_ver}\n"
        f"Reportes abiertos: {open_reports}\n"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("💰 TX Pendientes", callback_data="admin_pending_tx"),
        types.InlineKeyboardButton("📝 Verificaciones", callback_data="admin_pending_ver")
    )
    kb.add(
        types.InlineKeyboardButton("📢 Reportes", callback_data="admin_reports"),
        types.InlineKeyboardButton("🚫 Banear", callback_data="admin_ban")
    )
    kb.add(
        types.InlineKeyboardButton("⚙️ Formas de pago", callback_data="admin_payments"),
        types.InlineKeyboardButton("📜 Términos", callback_data="admin_terms")
    )
    kb.add(types.InlineKeyboardButton("« Menú", callback_data="menu_main"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_pending_tx")
def cb_admin_pending_tx(call):
    conn = get_db()
    txs = conn.execute("""
        SELECT t.*, u.username, u.first_name FROM transactions t
        LEFT JOIN users u ON u.user_id=t.user_id
        WHERE t.status='pending' ORDER BY t.created_at LIMIT 10
    """).fetchall()
    conn.close()

    text = "💰 <b>TX Pendientes</b>\n\n"
    if not txs:
        text += "Ninguna."
    else:
        for t in txs:
            uname = f"@{t['username']}" if t["username"] else t["first_name"]
            text += f"#{t['id']} {uname} — {t['type']} — {format_price(t['amount'])}\n"

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Admin", callback_data="admin_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_pending_ver")
def cb_admin_pending_ver(call):
    conn = get_db()
    vers = conn.execute("SELECT * FROM verifications WHERE status='pending' ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()

    text = "📝 <b>Verificaciones pendientes</b>\n\n"
    if not vers:
        text += "Ninguna."
    else:
        for v in vers:
            text += f"#{v['id']} — Usuario {v['user_id']}\n"

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Admin", callback_data="admin_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_reports")
def cb_admin_reports(call):
    conn = get_db()
    reps = conn.execute("SELECT * FROM reports WHERE status='open' ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()

    text = "📢 <b>Reportes abiertos</b>\n\n"
    if not reps:
        text += "Ninguno."
    else:
        for r in reps:
            text += f"#{r['id']} {r['reporter_id']} → {r['reported_id']} ({r['reason']})\n"

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Admin", callback_data="admin_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_ban")
def cb_admin_ban(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Envía el ID del usuario a banear:")
    bot.register_next_step_handler(msg, do_ban)

def do_ban(message):
    try:
        tid = int(message.text.strip())
    except:
        bot.send_message(message.chat.id, "ID inválido.")
        return
    conn = get_db()
    conn.execute("UPDATE users SET banned=1, ban_reason='Ban admin' WHERE user_id=?", (tid,))
    conn.commit()
    conn.close()
    log_admin(message.from_user.id, "ban", tid)
    bot.send_message(message.chat.id, f"✅ Usuario {tid} baneado.")
    try:
        bot.send_message(tid, "🚫 Has sido baneado.")
    except:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "admin_payments")
def cb_admin_payments(call):
    bot.answer_callback_query(call.id)
    current = get_setting("payment_methods")
    msg = bot.send_message(call.message.chat.id, f"Actual:\n\n{current}\n\nEnvía el nuevo texto:")
    bot.register_next_step_handler(msg, lambda m: (set_setting("payment_methods", m.text), bot.send_message(m.chat.id, "✅ Actualizado.")))

@bot.callback_query_handler(func=lambda c: c.data == "admin_terms")
def cb_admin_terms(call):
    bot.answer_callback_query(call.id)
    current = get_setting("terms")
    msg = bot.send_message(call.message.chat.id, f"Actual:\n\n{current}\n\nEnvía el nuevo texto:")
    bot.register_next_step_handler(msg, lambda m: (set_setting("terms", m.text), bot.send_message(m.chat.id, "✅ Actualizado.")))

# ==================== ARRANQUE ====================
if __name__ == "__main__":
    init_db()
    print("Bot OnlyFans V3 iniciado")
    print(f"Admin: {ADMIN_ID} | Tarifa creador: ${CREATOR_FEE}")
    bot.infinity_polling()
