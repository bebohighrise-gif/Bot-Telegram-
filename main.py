#!/usr/bin/env python3
"""
Bot Telegram tipo OnlyFans - V2 Avanzado
- Verificación de edad + términos
- Roles: Usuario / Creador / Admin
- Pago de 50 USD para convertirse en Creador
- Suscripciones (mensual/trimestral) + canal privado
- Paneles de Creador y Admin
- Menús inline que se editan
- Seguridad: bans, reportes, protect_content, logs
"""

import telebot
from telebot import types
import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

# ==================== CONFIGURACIÓN ====================
TELEGRAM_TOKEN = "PON_AQUI_TU_TOKEN"
ADMIN_ID = 7653419875                    # Tu ID de Telegram
CREATOR_FEE = 50.0                       # USD para convertirse en creador
PRIVATE_CHANNEL_ID = None                # Ej: -1001234567890 (canal privado principal, opcional)

DB_FILE = "bot.db"

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")

# ==================== BASE DE DATOS ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Usuarios
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            role TEXT DEFAULT 'user',          -- user / creator / admin
            language TEXT DEFAULT 'es',
            age_verified INTEGER DEFAULT 0,
            terms_accepted INTEGER DEFAULT 0,
            creator_verified INTEGER DEFAULT 0, -- 0=no, 1=pendiente, 2=aprobado
            banned INTEGER DEFAULT 0,
            ban_reason TEXT,
            joined_at TEXT,
            last_active TEXT
        )
    """)

    # Perfiles de creadores
    c.execute("""
        CREATE TABLE IF NOT EXISTS creators (
            user_id INTEGER PRIMARY KEY,
            display_name TEXT,
            bio TEXT,
            monthly_price REAL DEFAULT 9.99,
            quarterly_price REAL DEFAULT 24.99,
            private_channel_id INTEGER,
            total_subscribers INTEGER DEFAULT 0,
            total_earnings REAL DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)

    # Suscripciones
    c.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            creator_id INTEGER,
            plan TEXT,                         -- monthly / quarterly
            amount REAL,
            status TEXT DEFAULT 'active',      -- active / cancelled / expired
            start_date TEXT,
            end_date TEXT,
            payment_method TEXT,
            created_at TEXT,
            UNIQUE(user_id, creator_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(creator_id) REFERENCES creators(user_id)
        )
    """)

    # Contenido de creadores
    c.execute("""
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER,
            title TEXT,
            description TEXT,
            file_ids TEXT,                     -- JSON
            media_types TEXT,                  -- JSON
            is_premium INTEGER DEFAULT 1,
            views INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY(creator_id) REFERENCES creators(user_id)
        )
    """)

    # Transacciones
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            creator_id INTEGER,
            type TEXT,                         -- subscription / creator_fee / tip
            amount REAL,
            currency TEXT DEFAULT 'USD',
            status TEXT DEFAULT 'pending',     -- pending / completed / rejected / refunded
            payment_method TEXT,               -- manual / stars / external
            screenshot_file_id TEXT,
            reference TEXT,
            created_at TEXT,
            reviewed_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)

    # Reportes
    c.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER,
            reported_id INTEGER,
            reason TEXT,
            details TEXT,
            status TEXT DEFAULT 'open',        -- open / resolved / dismissed
            created_at TEXT
        )
    """)

    # Logs de admin
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

    # Settings
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Formas de pago por defecto
    c.execute("SELECT value FROM settings WHERE key = 'payment_methods'")
    if not c.fetchone():
        default = (
            "💳 <b>Formas de pago:</b>\n\n"
            "• Transferencia / Bizum\n"
            "• Crypto (USDT TRC20 / BTC)\n"
            "• Telegram Stars (próximamente)\n\n"
            "<i>El administrador actualizará los datos exactos.</i>"
        )
        c.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("payment_methods", default))

    # Términos por defecto
    c.execute("SELECT value FROM settings WHERE key = 'terms'")
    if not c.fetchone():
        terms = (
            "📜 <b>Términos y Condiciones</b>\n\n"
            "1. Debes ser mayor de 18 años.\n"
            "2. El contenido es solo para uso personal.\n"
            "3. Está prohibida la redistribución.\n"
            "4. El incumplimiento puede resultar en ban permanente.\n"
            "5. Al continuar aceptas estos términos."
        )
        c.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("terms", terms))

    conn.commit()
    conn.close()

    # Asegurar que el admin existe y tiene rol admin
    ensure_admin()

def ensure_admin():
    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO users (user_id, role, age_verified, terms_accepted, joined_at, last_active)
        VALUES (?, 'admin', 1, 1, ?, ?)
    """, (ADMIN_ID, datetime.now().isoformat(), datetime.now().isoformat()))
    conn.execute("UPDATE users SET role = 'admin', age_verified = 1, terms_accepted = 1 WHERE user_id = ?", (ADMIN_ID,))
    # Crear perfil de creador para el admin si no existe
    conn.execute("""
        INSERT OR IGNORE INTO creators (user_id, display_name, bio, created_at)
        VALUES (?, 'Admin Principal', 'Creador principal de la plataforma', ?)
    """, (ADMIN_ID, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_setting(key: str) -> str:
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else ""

def set_setting(key: str, value: str):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def log_admin(admin_id: int, action: str, target_id: int = None, details: str = ""):
    conn = get_db()
    conn.execute("""
        INSERT INTO admin_logs (admin_id, action, target_id, details, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (admin_id, action, target_id, details, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ==================== HELPERS DE USUARIO ====================
def get_user(user_id: int):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def upsert_user(tg_user):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO users (user_id, username, first_name, joined_at, last_active)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_active = excluded.last_active
    """, (tg_user.id, tg_user.username, tg_user.first_name, now, now))
    conn.commit()
    conn.close()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def is_banned(user_id: int) -> bool:
    user = get_user(user_id)
    return user and user["banned"] == 1

def is_creator(user_id: int) -> bool:
    user = get_user(user_id)
    return user and user["role"] in ("creator", "admin") and user["creator_verified"] == 2

def format_price(price: float, currency: str = "USD") -> str:
    symbol = "$" if currency == "USD" else "€"
    return f"{symbol}{price:.2f}"

def has_active_subscription(user_id: int, creator_id: int) -> bool:
    conn = get_db()
    row = conn.execute("""
        SELECT 1 FROM subscriptions
        WHERE user_id = ? AND creator_id = ? AND status = 'active'
        AND end_date > ?
    """, (user_id, creator_id, datetime.now().isoformat())).fetchone()
    conn.close()
    return bool(row)

# ==================== MENÚS PRINCIPALES ====================
def main_menu_keyboard(user_id: int):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔍 Explorar Creadores", callback_data="menu_explore"),
        types.InlineKeyboardButton("📋 Mis Suscripciones", callback_data="menu_subs")
    )
    markup.add(
        types.InlineKeyboardButton("👤 Mi Cuenta", callback_data="menu_account"),
        types.InlineKeyboardButton("❓ Ayuda", callback_data="menu_help")
    )
    if is_creator(user_id):
        markup.add(types.InlineKeyboardButton("🎨 Panel Creador", callback_data="creator_panel"))
    if is_admin(user_id):
        markup.add(types.InlineKeyboardButton("🔧 Panel Admin", callback_data="admin_panel"))
    return markup

def send_main_menu(chat_id: int, user_id: int, message_id: int = None):
    user = get_user(user_id)
    name = user["first_name"] if user else "Usuario"

    text = (
        f"💖 <b>Bienvenido/a, {name}</b>\n\n"
        "Plataforma de contenido exclusivo.\n"
        "Elige una opción:"
    )
    markup = main_menu_keyboard(user_id)

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
            return
        except:
            pass
    bot.send_message(chat_id, text, reply_markup=markup)

# ==================== REGISTRO + VERIFICACIÓN DE EDAD ====================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 Tu cuenta está baneada.")
        return

    upsert_user(message.from_user)
    user = get_user(message.from_user.id)

    # Flujo de verificación
    if not user["age_verified"]:
        ask_age_verification(message.chat.id)
        return

    if not user["terms_accepted"]:
        ask_terms(message.chat.id)
        return

    send_main_menu(message.chat.id, message.from_user.id)

def ask_age_verification(chat_id: int):
    text = (
        "🔒 <b>Verificación de Edad</b>\n\n"
        "Este bot contiene contenido exclusivo para adultos.\n\n"
        "¿Confirmas que eres <b>mayor de 18 años</b>?"
    )
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Sí, soy mayor de 18", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Soy menor", callback_data="age_no")
    )
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ("age_yes", "age_no"))
def cb_age(call):
    if call.data == "age_no":
        bot.edit_message_text(
            "🚫 Lo siento, este servicio es solo para mayores de 18 años.\n"
            "Puedes volver cuando cumplas la edad legal.",
            call.message.chat.id, call.message.message_id
        )
        bot.answer_callback_query(call.id)
        return

    # Marcar edad verificada
    conn = get_db()
    conn.execute("UPDATE users SET age_verified = 1 WHERE user_id = ?", (call.from_user.id,))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "Edad confirmada")
    ask_terms(call.message.chat.id, call.message.message_id)

def ask_terms(chat_id: int, message_id: int = None):
    terms = get_setting("terms")
    text = terms + "\n\n¿Aceptas los términos y condiciones?"
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Acepto", callback_data="terms_yes"),
        types.InlineKeyboardButton("❌ No acepto", callback_data="terms_no")
    )

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ("terms_yes", "terms_no"))
def cb_terms(call):
    if call.data == "terms_no":
        bot.edit_message_text(
            "Debes aceptar los términos para usar la plataforma.",
            call.message.chat.id, call.message.message_id
        )
        bot.answer_callback_query(call.id)
        return

    conn = get_db()
    conn.execute("UPDATE users SET terms_accepted = 1 WHERE user_id = ?", (call.from_user.id,))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "Términos aceptados")
    send_main_menu(call.message.chat.id, call.from_user.id, call.message.message_id)

# ==================== MENÚ PRINCIPAL (CALLBACKS) ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_main")
def cb_menu_main(call):
    bot.answer_callback_query(call.id)
    send_main_menu(call.message.chat.id, call.from_user.id, call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "menu_explore")
def cb_explore(call):
    bot.answer_callback_query(call.id)
    show_creators(call.message.chat.id, call.from_user.id, call.message.message_id, page=0)

def show_creators(chat_id: int, user_id: int, message_id: int = None, page: int = 0):
    conn = get_db()
    creators = conn.execute("""
        SELECT c.*, u.username, u.first_name
        FROM creators c
        JOIN users u ON u.user_id = c.user_id
        WHERE u.creator_verified = 2 AND u.banned = 0
        ORDER BY c.total_subscribers DESC
    """).fetchall()
    conn.close()

    if not creators:
        text = "Aún no hay creadores verificados."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("« Volver", callback_data="menu_main"))
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
        else:
            bot.send_message(chat_id, text, reply_markup=markup)
        return

    per_page = 5
    total_pages = (len(creators) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    page_creators = creators[start:start + per_page]

    text = f"🔍 <b>Creadores</b> (página {page+1}/{total_pages})\n\n"
    markup = types.InlineKeyboardMarkup()

    for c in page_creators:
        name = c["display_name"] or c["first_name"] or "Creador"
        btn = f"{name} — {format_price(c['monthly_price'])}/mes"
        markup.add(types.InlineKeyboardButton(btn, callback_data=f"creator_{c['user_id']}"))

    # Paginación
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("« Anterior", callback_data=f"explore_page_{page-1}"))
    if page < total_pages - 1:
        nav.append(types.InlineKeyboardButton("Siguiente »", callback_data=f"explore_page_{page+1}"))
    if nav:
        markup.row(*nav)

    markup.add(types.InlineKeyboardButton("« Menú principal", callback_data="menu_main"))

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("explore_page_"))
def cb_explore_page(call):
    page = int(call.data.split("_")[-1])
    bot.answer_callback_query(call.id)
    show_creators(call.message.chat.id, call.from_user.id, call.message.message_id, page)

@bot.callback_query_handler(func=lambda c: c.data.startswith("creator_"))
def cb_creator_profile(call):
    creator_id = int(call.data.split("_")[1])
    bot.answer_callback_query(call.id)

    conn = get_db()
    creator = conn.execute("""
        SELECT c.*, u.username, u.first_name
        FROM creators c JOIN users u ON u.user_id = c.user_id
        WHERE c.user_id = ? AND u.creator_verified = 2
    """, (creator_id,)).fetchone()
    conn.close()

    if not creator:
        bot.answer_callback_query(call.id, "Creador no encontrado", show_alert=True)
        return

    name = creator["display_name"] or creator["first_name"]
    subscribed = has_active_subscription(call.from_user.id, creator_id)

    text = (
        f"🎨 <b>{name}</b>\n\n"
        f"{creator['bio'] or 'Sin biografía'}\n\n"
        f"💰 Mensual: <b>{format_price(creator['monthly_price'])}</b>\n"
        f"💰 Trimestral: <b>{format_price(creator['quarterly_price'])}</b>\n"
        f"👥 Suscriptores: {creator['total_subscribers']}\n"
    )

    markup = types.InlineKeyboardMarkup()
    if subscribed:
        text += "\n✅ <b>Ya estás suscrito</b>"
        markup.add(types.InlineKeyboardButton("📥 Ver contenido", callback_data=f"content_{creator_id}"))
    else:
        markup.add(
            types.InlineKeyboardButton(f"Suscribirse Mensual ({format_price(creator['monthly_price'])})",
                                       callback_data=f"sub_monthly_{creator_id}"),
            types.InlineKeyboardButton(f"Suscribirse Trimestral ({format_price(creator['quarterly_price'])})",
                                       callback_data=f"sub_quarterly_{creator_id}")
        )

    markup.add(types.InlineKeyboardButton("« Volver", callback_data="menu_explore"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ==================== SUSCRIPCIONES ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("sub_"))
def cb_subscribe(call):
    parts = call.data.split("_")
    plan = parts[1]          # monthly / quarterly
    creator_id = int(parts[2])

    if has_active_subscription(call.from_user.id, creator_id):
        bot.answer_callback_query(call.id, "Ya tienes suscripción activa", show_alert=True)
        return

    conn = get_db()
    creator = conn.execute("SELECT * FROM creators WHERE user_id = ?", (creator_id,)).fetchone()
    conn.close()

    if not creator:
        bot.answer_callback_query(call.id, "Creador no encontrado", show_alert=True)
        return

    amount = creator["monthly_price"] if plan == "monthly" else creator["quarterly_price"]
    plan_name = "Mensual" if plan == "monthly" else "Trimestral"

    payment_methods = get_setting("payment_methods")

    text = (
        f"💳 <b>Suscripción {plan_name}</b>\n\n"
        f"Creador: <b>{creator['display_name']}</b>\n"
        f"Precio: <b>{format_price(amount)}</b>\n\n"
        f"{payment_methods}\n\n"
        "Cuando realices el pago, pulsa el botón y envía la <b>captura</b>."
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "💸 Ya pagué — Enviar captura",
        callback_data=f"pay_sub_{plan}_{creator_id}"
    ))
    markup.add(types.InlineKeyboardButton("« Volver", callback_data=f"creator_{creator_id}"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_sub_"))
def cb_pay_sub(call):
    parts = call.data.split("_")
    plan = parts[2]
    creator_id = int(parts[3])

    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.message.chat.id,
        f"📸 Envía ahora la <b>captura del pago</b> de la suscripción.\n\nSolo se acepta una foto."
    )
    bot.register_next_step_handler(msg, process_sub_screenshot, plan, creator_id)

def process_sub_screenshot(message, plan, creator_id):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Debes enviar una <b>foto</b>. Vuelve a intentar desde el menú.")
        return

    conn = get_db()
    creator = conn.execute("SELECT * FROM creators WHERE user_id = ?", (creator_id,)).fetchone()
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

    bot.send_message(message.chat.id, "✅ Captura recibida. El administrador la revisará pronto.")

    # Notificar admin
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    admin_text = (
        f"💰 <b>NUEVA SUSCRIPCIÓN PENDIENTE</b>\n\n"
        f"Usuario: {username} (<code>{message.from_user.id}</code>)\n"
        f"Creador ID: {creator_id}\n"
        f"Plan: {plan}\n"
        f"Monto: {format_price(amount)}\n"
        f"TX: #{tx_id}"
    )
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_tx_{tx_id}"),
        types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_tx_{tx_id}")
    )
    bot.send_photo(ADMIN_ID, file_id, caption=admin_text, reply_markup=markup)

# ==================== APROBAR / RECHAZAR TRANSACCIONES ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith(("approve_tx_", "reject_tx_")))
def cb_review_tx(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "No autorizado", show_alert=True)
        return

    action = "approve" if call.data.startswith("approve_tx_") else "reject"
    tx_id = int(call.data.split("_")[-1])

    conn = get_db()
    tx = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()

    if not tx or tx["status"] != "pending":
        bot.answer_callback_query(call.id, "Transacción no válida o ya procesada", show_alert=True)
        conn.close()
        return

    if action == "approve":
        conn.execute("UPDATE transactions SET status = 'completed', reviewed_at = ? WHERE id = ?",
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
                    plan = excluded.plan,
                    amount = excluded.amount,
                    status = 'active',
                    start_date = excluded.start_date,
                    end_date = excluded.end_date
            """, (tx["user_id"], tx["creator_id"], plan, tx["amount"],
                  start.isoformat(), end.isoformat(), datetime.now().isoformat()))

            # Actualizar contador
            conn.execute("UPDATE creators SET total_subscribers = total_subscribers + 1, total_earnings = total_earnings + ? WHERE user_id = ?",
                         (tx["amount"], tx["creator_id"]))

            # Intentar agregar al canal privado si existe
            creator = conn.execute("SELECT private_channel_id FROM creators WHERE user_id = ?", (tx["creator_id"],)).fetchone()
            if creator and creator["private_channel_id"]:
                try:
                    bot.unban_chat_member(creator["private_channel_id"], tx["user_id"])  # por si estaba baneado
                    # Nota: para invitar realmente se necesita invite link o el usuario debe unirse
                except:
                    pass

            try:
                bot.send_message(
                    tx["user_id"],
                    f"✅ <b>Suscripción activada</b>\n\n"
                    f"Plan: {plan}\n"
                    f"Válida hasta: {end.strftime('%d/%m/%Y')}\n\n"
                    "Ya puedes acceder al contenido."
                )
            except:
                pass

        elif tx["type"] == "creator_fee":
            # Convertir en creador
            conn.execute("UPDATE users SET role = 'creator', creator_verified = 2 WHERE user_id = ?", (tx["user_id"],))
            conn.execute("""
                INSERT OR IGNORE INTO creators (user_id, display_name, created_at)
                VALUES (?, ?, ?)
            """, (tx["user_id"], "Nuevo Creador", datetime.now().isoformat()))

            try:
                bot.send_message(
                    tx["user_id"],
                    "🎉 <b>¡Felicidades!</b>\n\n"
                    "Tu pago de creador ha sido aprobado.\n"
                    "Ya puedes usar el <b>Panel Creador</b>."
                )
            except:
                pass

        conn.commit()
        bot.edit_message_caption(
            caption=(call.message.caption or "") + "\n\n✅ <b>APROBADO</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        bot.answer_callback_query(call.id, "Aprobado")
        log_admin(call.from_user.id, "approve_tx", tx["user_id"], f"TX #{tx_id}")

    else:
        conn.execute("UPDATE transactions SET status = 'rejected', reviewed_at = ? WHERE id = ?",
                     (datetime.now().isoformat(), tx_id))
        conn.commit()

        try:
            bot.send_message(tx["user_id"], "❌ Tu pago fue rechazado. Contacta al administrador si crees que es un error.")
        except:
            pass

        bot.edit_message_caption(
            caption=(call.message.caption or "") + "\n\n❌ <b>RECHAZADO</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        bot.answer_callback_query(call.id, "Rechazado")
        log_admin(call.from_user.id, "reject_tx", tx["user_id"], f"TX #{tx_id}")

    conn.close()

# ==================== CONVERTIRSE EN CREADOR (50 USD) ====================
@bot.callback_query_handler(func=lambda c: c.data == "become_creator")
def cb_become_creator(call):
    user = get_user(call.from_user.id)
    if user["role"] in ("creator", "admin") and user["creator_verified"] == 2:
        bot.answer_callback_query(call.id, "Ya eres creador", show_alert=True)
        return

    if user["creator_verified"] == 1:
        bot.answer_callback_query(call.id, "Tu solicitud ya está en revisión", show_alert=True)
        return

    payment_methods = get_setting("payment_methods")
    text = (
        f"🎨 <b>Convertirse en Creador</b>\n\n"
        f"Para publicar contenido y ganar dinero necesitas:\n"
        f"1. Pagar la tarifa de registro: <b>{format_price(CREATOR_FEE)}</b>\n"
        f"2. Verificación de identidad (se realiza después del pago)\n\n"
        f"{payment_methods}\n\n"
        "Una vez pagado, envía la captura."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        f"💸 Ya pagué {format_price(CREATOR_FEE)}",
        callback_data="pay_creator_fee"
    ))
    markup.add(types.InlineKeyboardButton("« Volver", callback_data="menu_account"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "pay_creator_fee")
def cb_pay_creator_fee(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📸 Envía la <b>captura del pago</b> de 50 USD.")
    bot.register_next_step_handler(msg, process_creator_fee_screenshot)

def process_creator_fee_screenshot(message):
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

    # Marcar como pendiente de verificación
    conn.execute("UPDATE users SET creator_verified = 1 WHERE user_id = ?", (message.from_user.id,))
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, "✅ Captura recibida. Tu solicitud de creador está en revisión.")

    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    admin_text = (
        f"🎨 <b>SOLICITUD DE CREADOR</b>\n\n"
        f"Usuario: {username} (<code>{message.from_user.id}</code>)\n"
        f"Monto: {format_price(CREATOR_FEE)}\n"
        f"TX: #{tx_id}\n\n"
        "Tras aprobar el pago, el usuario pasará a ser Creador verificado."
    )
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Aprobar Creador", callback_data=f"approve_tx_{tx_id}"),
        types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_tx_{tx_id}")
    )
    bot.send_photo(ADMIN_ID, file_id, caption=admin_text, reply_markup=markup)

# ==================== MI CUENTA ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_account")
def cb_account(call):
    user = get_user(call.from_user.id)
    role_emoji = {"user": "👤", "creator": "🎨", "admin": "🔧"}.get(user["role"], "👤")

    text = (
        f"👤 <b>Mi Cuenta</b>\n\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Nombre: {user['first_name']}\n"
        f"Rol: {role_emoji} {user['role'].capitalize()}\n"
        f"Edad verificada: {'✅' if user['age_verified'] else '❌'}\n"
        f"Términos: {'✅' if user['terms_accepted'] else '❌'}\n"
    )

    markup = types.InlineKeyboardMarkup()
    if user["role"] == "user" and user["creator_verified"] != 2:
        markup.add(types.InlineKeyboardButton("🎨 Quiero ser Creador (50$)", callback_data="become_creator"))
    markup.add(types.InlineKeyboardButton("« Menú principal", callback_data="menu_main"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "menu_subs")
def cb_my_subs(call):
    conn = get_db()
    subs = conn.execute("""
        SELECT s.*, c.display_name
        FROM subscriptions s
        JOIN creators c ON c.user_id = s.creator_id
        WHERE s.user_id = ? AND s.status = 'active' AND s.end_date > ?
        ORDER BY s.end_date DESC
    """, (call.from_user.id, datetime.now().isoformat())).fetchall()
    conn.close()

    if not subs:
        text = "No tienes suscripciones activas."
    else:
        text = "📋 <b>Mis Suscripciones</b>\n\n"
        for s in subs:
            text += f"• <b>{s['display_name']}</b> ({s['plan']})\n  Hasta: {s['end_date'][:10]}\n\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Menú principal", callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "menu_help")
def cb_help(call):
    text = (
        "❓ <b>Ayuda</b>\n\n"
        "• <b>Explorar Creadores</b>: mira perfiles y suscríbete.\n"
        "• <b>Mis Suscripciones</b>: gestiona tus accesos.\n"
        "• <b>Mi Cuenta</b>: datos y opción de convertirte en Creador.\n\n"
        "Para ser Creador debes pagar 50 USD y pasar verificación.\n\n"
        "¿Problemas? Contacta al administrador."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Menú principal", callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

# ==================== PANEL CREADOR ====================
@bot.callback_query_handler(func=lambda c: c.data == "creator_panel")
def cb_creator_panel(call):
    if not is_creator(call.from_user.id):
        bot.answer_callback_query(call.id, "No eres creador verificado", show_alert=True)
        return

    conn = get_db()
    creator = conn.execute("SELECT * FROM creators WHERE user_id = ?", (call.from_user.id,)).fetchone()
    conn.close()

    text = (
        f"🎨 <b>Panel de Creador</b>\n\n"
        f"Suscriptores: {creator['total_subscribers']}\n"
        f"Ingresos totales: {format_price(creator['total_earnings'])}\n"
        f"Precio mensual: {format_price(creator['monthly_price'])}\n"
        f"Precio trimestral: {format_price(creator['quarterly_price'])}\n"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📸 Subir contenido", callback_data="creator_upload"),
        types.InlineKeyboardButton("💰 Cambiar precios", callback_data="creator_prices")
    )
    markup.add(
        types.InlineKeyboardButton("📢 Mensaje masivo", callback_data="creator_broadcast"),
        types.InlineKeyboardButton("📊 Estadísticas", callback_data="creator_stats")
    )
    markup.add(types.InlineKeyboardButton("« Menú principal", callback_data="menu_main"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "creator_upload")
def cb_creator_upload(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Envía el contenido (foto/video) con una descripción opcional.\nCuando termines escribe /listo_contenido")
    bot.register_next_step_handler(msg, creator_collect_content, [], [])

def creator_collect_content(message, file_ids, media_types):
    if message.text and message.text.lower() == "/listo_contenido":
        if not file_ids:
            bot.send_message(message.chat.id, "No enviaste ningún archivo.")
            return

        conn = get_db()
        conn.execute("""
            INSERT INTO content (creator_id, title, file_ids, media_types, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (message.from_user.id, "Contenido", json.dumps(file_ids), json.dumps(media_types), datetime.now().isoformat()))
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, f"✅ Contenido subido ({len(file_ids)} archivos).")
        return

    if message.photo:
        file_ids.append(message.photo[-1].file_id)
        media_types.append("photo")
        bot.send_message(message.chat.id, f"Foto añadida ({len(file_ids)}). Envía más o /listo_contenido")
    elif message.video:
        file_ids.append(message.video.file_id)
        media_types.append("video")
        bot.send_message(message.chat.id, f"Video añadido ({len(file_ids)}). Envía más o /listo_contenido")
    else:
        bot.send_message(message.chat.id, "Envía foto o video, o /listo_contenido")

    bot.register_next_step_handler(message, creator_collect_content, file_ids, media_types)

@bot.callback_query_handler(func=lambda c: c.data == "creator_prices")
def cb_creator_prices(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Envía el nuevo precio <b>mensual</b> (ej: 9.99):")
    bot.register_next_step_handler(msg, set_monthly_price)

def set_monthly_price(message):
    try:
        price = float(message.text.replace(",", "."))
    except:
        bot.send_message(message.chat.id, "Precio inválido.")
        return

    conn = get_db()
    conn.execute("UPDATE creators SET monthly_price = ? WHERE user_id = ?", (price, message.from_user.id))
    conn.commit()
    conn.close()

    msg = bot.send_message(message.chat.id, f"Mensual actualizado a {format_price(price)}.\nAhora envía el precio <b>trimestral</b>:")
    bot.register_next_step_handler(msg, set_quarterly_price)

def set_quarterly_price(message):
    try:
        price = float(message.text.replace(",", "."))
    except:
        bot.send_message(message.chat.id, "Precio inválido.")
        return

    conn = get_db()
    conn.execute("UPDATE creators SET quarterly_price = ? WHERE user_id = ?", (price, message.from_user.id))
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, f"✅ Precios actualizados.")

@bot.callback_query_handler(func=lambda c: c.data == "creator_stats")
def cb_creator_stats(call):
    conn = get_db()
    creator = conn.execute("SELECT * FROM creators WHERE user_id = ?", (call.from_user.id,)).fetchone()
    active_subs = conn.execute("""
        SELECT COUNT(*) FROM subscriptions
        WHERE creator_id = ? AND status = 'active' AND end_date > ?
    """, (call.from_user.id, datetime.now().isoformat())).fetchone()[0]
    conn.close()

    text = (
        f"📊 <b>Estadísticas</b>\n\n"
        f"Suscriptores activos: {active_subs}\n"
        f"Suscriptores totales: {creator['total_subscribers']}\n"
        f"Ingresos: {format_price(creator['total_earnings'])}"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Panel Creador", callback_data="creator_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "creator_broadcast")
def cb_creator_broadcast(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Escribe el mensaje que quieres enviar a todos tus suscriptores activos:")
    bot.register_next_step_handler(msg, do_broadcast)

def do_broadcast(message):
    conn = get_db()
    subs = conn.execute("""
        SELECT user_id FROM subscriptions
        WHERE creator_id = ? AND status = 'active' AND end_date > ?
    """, (message.from_user.id, datetime.now().isoformat())).fetchall()
    conn.close()

    sent = 0
    for s in subs:
        try:
            bot.send_message(s["user_id"], f"📢 <b>Mensaje de tu creador:</b>\n\n{message.text}", protect_content=True)
            sent += 1
        except:
            pass

    bot.send_message(message.chat.id, f"✅ Mensaje enviado a {sent} suscriptores.")

# ==================== PANEL ADMIN ====================
@bot.callback_query_handler(func=lambda c: c.data == "admin_panel")
def cb_admin_panel(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "No autorizado", show_alert=True)
        return

    conn = get_db()
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    creators = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'creator' AND creator_verified = 2").fetchone()[0]
    pending_tx = conn.execute("SELECT COUNT(*) FROM transactions WHERE status = 'pending'").fetchone()[0]
    open_reports = conn.execute("SELECT COUNT(*) FROM reports WHERE status = 'open'").fetchone()[0]
    conn.close()

    text = (
        f"🔧 <b>Panel de Administración</b>\n\n"
        f"Usuarios: {users}\n"
        f"Creadores: {creators}\n"
        f"TX pendientes: {pending_tx}\n"
        f"Reportes abiertos: {open_reports}\n"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💰 TX Pendientes", callback_data="admin_pending_tx"),
        types.InlineKeyboardButton("🚫 Banear usuario", callback_data="admin_ban")
    )
    markup.add(
        types.InlineKeyboardButton("📋 Reportes", callback_data="admin_reports"),
        types.InlineKeyboardButton("⚙️ Formas de pago", callback_data="admin_payments")
    )
    markup.add(
        types.InlineKeyboardButton("📜 Editar Términos", callback_data="admin_terms"),
        types.InlineKeyboardButton("📊 Logs", callback_data="admin_logs")
    )
    markup.add(types.InlineKeyboardButton("« Menú principal", callback_data="menu_main"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_pending_tx")
def cb_admin_pending_tx(call):
    conn = get_db()
    txs = conn.execute("""
        SELECT t.*, u.username, u.first_name
        FROM transactions t
        LEFT JOIN users u ON u.user_id = t.user_id
        WHERE t.status = 'pending'
        ORDER BY t.created_at ASC LIMIT 10
    """).fetchall()
    conn.close()

    if not txs:
        text = "No hay transacciones pendientes."
    else:
        text = "💰 <b>Transacciones pendientes</b>\n\n"
        for t in txs:
            uname = f"@{t['username']}" if t["username"] else t["first_name"]
            text += f"#{t['id']} {uname} — {t['type']} — {format_price(t['amount'])}\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Panel Admin", callback_data="admin_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_ban")
def cb_admin_ban(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Envía el <b>ID del usuario</b> a banear:")
    bot.register_next_step_handler(msg, process_ban)

def process_ban(message):
    try:
        target_id = int(message.text.strip())
    except:
        bot.send_message(message.chat.id, "ID inválido.")
        return

    conn = get_db()
    conn.execute("UPDATE users SET banned = 1, ban_reason = 'Ban por admin' WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()

    log_admin(message.from_user.id, "ban", target_id)
    bot.send_message(message.chat.id, f"✅ Usuario {target_id} baneado.")
    try:
        bot.send_message(target_id, "🚫 Has sido baneado de la plataforma.")
    except:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "admin_payments")
def cb_admin_payments(call):
    bot.answer_callback_query(call.id)
    current = get_setting("payment_methods")
    msg = bot.send_message(call.message.chat.id, f"Formas de pago actuales:\n\n{current}\n\nEnvía el nuevo texto:")
    bot.register_next_step_handler(msg, save_payments)

def save_payments(message):
    set_setting("payment_methods", message.text)
    bot.send_message(message.chat.id, "✅ Formas de pago actualizadas.")

@bot.callback_query_handler(func=lambda c: c.data == "admin_terms")
def cb_admin_terms(call):
    bot.answer_callback_query(call.id)
    current = get_setting("terms")
    msg = bot.send_message(call.message.chat.id, f"Términos actuales:\n\n{current}\n\nEnvía el nuevo texto:")
    bot.register_next_step_handler(msg, save_terms)

def save_terms(message):
    set_setting("terms", message.text)
    bot.send_message(message.chat.id, "✅ Términos actualizados.")

@bot.callback_query_handler(func=lambda c: c.data == "admin_logs")
def cb_admin_logs(call):
    conn = get_db()
    logs = conn.execute("SELECT * FROM admin_logs ORDER BY id DESC LIMIT 15").fetchall()
    conn.close()

    text = "📊 <b>Últimos logs</b>\n\n"
    for l in logs:
        text += f"{l['created_at'][:16]} — {l['action']} → {l['target_id']}\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Panel Admin", callback_data="admin_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_reports")
def cb_admin_reports(call):
    conn = get_db()
    reports = conn.execute("SELECT * FROM reports WHERE status = 'open' ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()

    text = "📋 <b>Reportes abiertos</b>\n\n"
    if not reports:
        text += "Ninguno."
    else:
        for r in reports:
            text += f"#{r['id']} — Reporter: {r['reporter_id']} → {r['reported_id']}\nRazón: {r['reason']}\n\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Panel Admin", callback_data="admin_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

# ==================== CONTENIDO (ejemplo básico) ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("content_"))
def cb_content(call):
    creator_id = int(call.data.split("_")[1])
    if not has_active_subscription(call.from_user.id, creator_id) and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Necesitas suscripción activa", show_alert=True)
        return

    conn = get_db()
    items = conn.execute("""
        SELECT * FROM content WHERE creator_id = ? ORDER BY id DESC LIMIT 5
    """, (creator_id,)).fetchall()
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

# ==================== ARRANQUE ====================
if __name__ == "__main__":
    init_db()
    print("Bot OnlyFans V2 iniciado...")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"Tarifa creador: ${CREATOR_FEE}")
    bot.infinity_polling()
