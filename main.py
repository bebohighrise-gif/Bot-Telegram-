#!/usr/bin/env python3
"""
Bot Telegram tipo OnlyFans
- Catálogo de contenido
- Pagos manuales (el dueño actualiza las formas de pago)
- Usuario envía captura → admin recibe notificación + botones de verificación
- Al aprobar se entrega el contenido automáticamente
"""

import telebot
from telebot import types
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

# ==================== CONFIGURACIÓN ====================
TELEGRAM_TOKEN = "PON_AQUI_TU_TOKEN"          # Token de @BotFather
ADMIN_ID = 7653419875                        # Tu ID de Telegram (usa @userinfobot)

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
            joined_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS packs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            file_ids TEXT NOT NULL,          -- JSON list of file_id
            media_types TEXT NOT NULL,       -- JSON list of 'photo'/'video'/'document'
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            pack_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending',   -- pending / approved / rejected
            screenshot_file_id TEXT,
            created_at TEXT,
            reviewed_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(pack_id) REFERENCES packs(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            pack_id INTEGER,
            purchased_at TEXT,
            UNIQUE(user_id, pack_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Formas de pago por defecto
    c.execute("SELECT value FROM settings WHERE key = 'payment_methods'")
    if not c.fetchone():
        default_payments = (
            "💳 <b>Formas de pago disponibles:</b>\n\n"
            "• Transferencia bancaria\n"
            "• Bizum\n"
            "• Crypto (USDT / BTC)\n\n"
            "<i>El dueño actualizará los datos exactos.</i>"
        )
        c.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("payment_methods", default_payments))

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

def register_user(user):
    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at)
        VALUES (?, ?, ?, ?)
    """, (user.id, user.username, user.first_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ==================== HELPERS ====================
def format_price(price: float) -> str:
    return f"{price:.2f} €" if price == int(price) else f"{price:.2f} €"

def user_has_pack(user_id: int, pack_id: int) -> bool:
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM purchases WHERE user_id = ? AND pack_id = ?",
        (user_id, pack_id)
    ).fetchone()
    conn.close()
    return bool(row)

def get_pack(pack_id: int):
    conn = get_db()
    pack = conn.execute("SELECT * FROM packs WHERE id = ? AND active = 1", (pack_id,)).fetchone()
    conn.close()
    return pack

def send_pack_content(chat_id: int, pack):
    """Envía todo el contenido del pack al usuario"""
    file_ids = json.loads(pack["file_ids"])
    media_types = json.loads(pack["media_types"])

    bot.send_message(chat_id, f"🎁 <b>Contenido desbloqueado:</b> {pack['title']}")

    for fid, mtype in zip(file_ids, media_types):
        try:
            if mtype == "photo":
                bot.send_photo(chat_id, fid)
            elif mtype == "video":
                bot.send_video(chat_id, fid)
            else:
                bot.send_document(chat_id, fid)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Error enviando un archivo: {e}")

# ==================== COMANDOS USUARIO ====================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    register_user(message.from_user)
    name = message.from_user.first_name or "usuario"

    text = (
        f"💖 Hola <b>{name}</b>\n\n"
        "Bienvenido a mi contenido exclusivo.\n\n"
        "Usa el menú para explorar los packs disponibles."
    )

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📦 Catálogo", "💰 Mis compras")
    markup.row("❓ Ayuda")

    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=["catalogo"])
@bot.message_handler(func=lambda m: m.text == "📦 Catálogo")
def cmd_catalogo(message):
    register_user(message.from_user)
    conn = get_db()
    packs = conn.execute("SELECT * FROM packs WHERE active = 1 ORDER BY id DESC").fetchall()
    conn.close()

    if not packs:
        bot.send_message(message.chat.id, "Todavía no hay packs disponibles.")
        return

    text = "📦 <b>Catálogo de contenido</b>\n\nSelecciona un pack:"
    markup = types.InlineKeyboardMarkup()

    for p in packs:
        btn_text = f"{p['title']} — {format_price(p['price'])}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"pack_{p['id']}"))

    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=["mis_compras"])
@bot.message_handler(func=lambda m: m.text == "💰 Mis compras")
def cmd_mis_compras(message):
    register_user(message.from_user)
    conn = get_db()
    rows = conn.execute("""
        SELECT p.id, p.title, p.price, pu.purchased_at
        FROM purchases pu
        JOIN packs p ON p.id = pu.pack_id
        WHERE pu.user_id = ?
        ORDER BY pu.purchased_at DESC
    """, (message.from_user.id,)).fetchall()
    conn.close()

    if not rows:
        bot.send_message(message.chat.id, "Aún no has comprado ningún pack.")
        return

    text = "💰 <b>Tus compras:</b>\n\n"
    markup = types.InlineKeyboardMarkup()

    for r in rows:
        text += f"• <b>{r['title']}</b> — {format_price(r['price'])}\n"
        markup.add(types.InlineKeyboardButton(
            f"📥 Volver a descargar: {r['title']}",
            callback_data=f"redownload_{r['id']}"
        ))

    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=["ayuda"])
@bot.message_handler(func=lambda m: m.text == "❓ Ayuda")
def cmd_ayuda(message):
    text = (
        "❓ <b>Ayuda</b>\n\n"
        "1. Entra al <b>Catálogo</b> y elige el pack que te interese.\n"
        "2. Verás el precio y las formas de pago actuales.\n"
        "3. Realiza el pago y <b>envía la captura</b> aquí mismo.\n"
        "4. El dueño verificará el pago y te entregará el contenido.\n\n"
        "Si tienes problemas, escribe directamente al dueño."
    )
    bot.send_message(message.chat.id, text)

# ==================== CALLBACKS ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("pack_"))
def cb_pack(call):
    pack_id = int(call.data.split("_")[1])
    pack = get_pack(pack_id)

    if not pack:
        bot.answer_callback_query(call.id, "Pack no disponible", show_alert=True)
        return

    user_id = call.from_user.id

    if user_has_pack(user_id, pack_id):
        bot.answer_callback_query(call.id, "Ya tienes este pack")
        send_pack_content(call.message.chat.id, pack)
        return

    payment_methods = get_setting("payment_methods")

    text = (
        f"📦 <b>{pack['title']}</b>\n\n"
        f"{pack['description'] or ''}\n\n"
        f"💰 Precio: <b>{format_price(pack['price'])}</b>\n\n"
        f"{payment_methods}\n\n"
        "Cuando hayas realizado el pago, pulsa el botón de abajo y envía la <b>captura</b>."
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "💸 Ya pagué — Enviar captura",
        callback_data=f"pay_{pack_id}"
    ))
    markup.add(types.InlineKeyboardButton("« Volver", callback_data="back_catalog"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_catalog")
def cb_back_catalog(call):
    conn = get_db()
    packs = conn.execute("SELECT * FROM packs WHERE active = 1 ORDER BY id DESC").fetchall()
    conn.close()

    text = "📦 <b>Catálogo de contenido</b>\n\nSelecciona un pack:"
    markup = types.InlineKeyboardMarkup()
    for p in packs:
        btn_text = f"{p['title']} — {format_price(p['price'])}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"pack_{p['id']}"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def cb_pay(call):
    pack_id = int(call.data.split("_")[1])
    pack = get_pack(pack_id)

    if not pack:
        bot.answer_callback_query(call.id, "Pack no disponible", show_alert=True)
        return

    # Guardamos el estado de espera de captura
    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.message.chat.id,
        f"📸 Envía ahora la <b>captura del pago</b> para el pack:\n\n"
        f"<b>{pack['title']}</b> — {format_price(pack['price'])}\n\n"
        "Solo se acepta una foto."
    )

    bot.register_next_step_handler(msg, process_screenshot, pack_id)

def process_screenshot(message, pack_id):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Debes enviar una <b>foto</b> (captura). Intenta de nuevo con /catalogo")
        return

    pack = get_pack(pack_id)
    if not pack:
        bot.send_message(message.chat.id, "El pack ya no está disponible.")
        return

    # Guardamos el pago pendiente
    file_id = message.photo[-1].file_id  # mejor calidad

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO payments (user_id, pack_id, amount, status, screenshot_file_id, created_at)
        VALUES (?, ?, ?, 'pending', ?, ?)
    """, (message.from_user.id, pack_id, pack["price"], file_id, datetime.now().isoformat()))
    payment_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Confirmación al usuario
    bot.send_message(
        message.chat.id,
        "✅ Captura recibida.\n\n"
        "El dueño la revisará pronto. Te avisaré cuando sea aprobada."
    )

    # Notificación al admin
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name

    admin_text = (
        f"💰 <b>NUEVO PAGO PENDIENTE</b>\n\n"
        f"Usuario: {username} (ID: <code>{message.from_user.id}</code>)\n"
        f"Pack: <b>{pack['title']}</b>\n"
        f"Monto: <b>{format_price(pack['price'])}</b>\n"
        f"ID pago: #{payment_id}"
    )

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_{payment_id}"),
        types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_{payment_id}")
    )

    bot.send_photo(ADMIN_ID, file_id, caption=admin_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def cb_review_payment(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "No autorizado", show_alert=True)
        return

    action, payment_id = call.data.split("_")
    payment_id = int(payment_id)

    conn = get_db()
    payment = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()

    if not payment:
        bot.answer_callback_query(call.id, "Pago no encontrado", show_alert=True)
        conn.close()
        return

    if payment["status"] != "pending":
        bot.answer_callback_query(call.id, f"Ya estaba {payment['status']}", show_alert=True)
        conn.close()
        return

    pack = conn.execute("SELECT * FROM packs WHERE id = ?", (payment["pack_id"],)).fetchone()

    if action == "approve":
        # Marcar como aprobado
        conn.execute(
            "UPDATE payments SET status = 'approved', reviewed_at = ? WHERE id = ?",
            (datetime.now().isoformat(), payment_id)
        )
        # Registrar compra
        conn.execute("""
            INSERT OR IGNORE INTO purchases (user_id, pack_id, purchased_at)
            VALUES (?, ?, ?)
        """, (payment["user_id"], payment["pack_id"], datetime.now().isoformat()))
        conn.commit()

        # Entregar contenido
        try:
            send_pack_content(payment["user_id"], pack)
            bot.send_message(
                payment["user_id"],
                f"✅ <b>Pago aprobado</b>\n\nTu pack <b>{pack['title']}</b> ha sido desbloqueado."
            )
        except Exception as e:
            bot.send_message(ADMIN_ID, f"Error entregando contenido al usuario {payment['user_id']}: {e}")

        # Actualizar mensaje del admin
        bot.edit_message_caption(
            caption=call.message.caption + "\n\n✅ <b>APROBADO</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        bot.answer_callback_query(call.id, "Pago aprobado y contenido entregado")

    else:  # reject
        conn.execute(
            "UPDATE payments SET status = 'rejected', reviewed_at = ? WHERE id = ?",
            (datetime.now().isoformat(), payment_id)
        )
        conn.commit()

        try:
            bot.send_message(
                payment["user_id"],
                f"❌ Tu pago por el pack <b>{pack['title']}</b> fue rechazado.\n"
                "Si crees que es un error, contacta al dueño."
            )
        except:
            pass

        bot.edit_message_caption(
            caption=call.message.caption + "\n\n❌ <b>RECHAZADO</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        bot.answer_callback_query(call.id, "Pago rechazado")

    conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith("redownload_"))
def cb_redownload(call):
    pack_id = int(call.data.split("_")[1])
    pack = get_pack(pack_id)

    if not pack:
        bot.answer_callback_query(call.id, "Pack no disponible", show_alert=True)
        return

    if not user_has_pack(call.from_user.id, pack_id):
        bot.answer_callback_query(call.id, "No tienes este pack", show_alert=True)
        return

    bot.answer_callback_query(call.id, "Enviando contenido...")
    send_pack_content(call.message.chat.id, pack)

# ==================== PANEL ADMIN ====================
@bot.message_handler(commands=["admin"])
def cmd_admin(message):
    if not is_admin(message.from_user.id):
        return

    text = (
        "🔧 <b>Panel de Administración</b>\n\n"
        "/set_pagos → Actualizar formas de pago\n"
        "/add_pack → Agregar nuevo pack\n"
        "/pendientes → Ver pagos pendientes\n"
        "/stats → Estadísticas\n"
        "/list_packs → Listar packs"
    )
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["set_pagos"])
def cmd_set_pagos(message):
    if not is_admin(message.from_user.id):
        return

    current = get_setting("payment_methods")
    bot.send_message(
        message.chat.id,
        f"Formas de pago actuales:\n\n{current}\n\n"
        "Envía el <b>nuevo texto</b> con las formas de pago (puedes usar HTML básico).\n"
        "Escribe /cancelar para abortar."
    )
    bot.register_next_step_handler(message, save_payment_methods)

def save_payment_methods(message):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.lower() == "/cancelar":
        bot.send_message(message.chat.id, "Cancelado.")
        return

    set_setting("payment_methods", message.text)
    bot.send_message(message.chat.id, "✅ Formas de pago actualizadas correctamente.")

@bot.message_handler(commands=["add_pack"])
def cmd_add_pack(message):
    if not is_admin(message.from_user.id):
        return

    bot.send_message(
        message.chat.id,
        "📦 <b>Nuevo pack</b>\n\n"
        "Envía el título del pack:\n"
        "(o /cancelar)"
    )
    bot.register_next_step_handler(message, add_pack_title)

def add_pack_title(message):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.lower() == "/cancelar":
        bot.send_message(message.chat.id, "Cancelado.")
        return

    title = message.text.strip()
    bot.send_message(message.chat.id, "Ahora envía la <b>descripción</b> (o - para omitir):")
    bot.register_next_step_handler(message, add_pack_description, title)

def add_pack_description(message, title):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.lower() == "/cancelar":
        bot.send_message(message.chat.id, "Cancelado.")
        return

    description = "" if message.text.strip() == "-" else message.text.strip()
    bot.send_message(message.chat.id, "Precio del pack (número, ej: 9.99):")
    bot.register_next_step_handler(message, add_pack_price, title, description)

def add_pack_price(message, title, description):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.lower() == "/cancelar":
        bot.send_message(message.chat.id, "Cancelado.")
        return

    try:
        price = float(message.text.replace(",", ".").strip())
    except:
        bot.send_message(message.chat.id, "Precio inválido. Cancela e intenta de nuevo.")
        return

    bot.send_message(
        message.chat.id,
        "Ahora envía los archivos del pack (fotos/videos).\n"
        "Cuando termines, escribe <b>/listo</b>"
    )
    bot.register_next_step_handler(message, add_pack_files, title, description, price, [], [])

def add_pack_files(message, title, description, price, file_ids, media_types):
    if not is_admin(message.from_user.id):
        return

    if message.text and message.text.lower() == "/cancelar":
        bot.send_message(message.chat.id, "Cancelado.")
        return

    if message.text and message.text.lower() == "/listo":
        if not file_ids:
            bot.send_message(message.chat.id, "No has enviado ningún archivo. Cancela e intenta de nuevo.")
            return

        conn = get_db()
        conn.execute("""
            INSERT INTO packs (title, description, price, file_ids, media_types, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            title,
            description,
            price,
            json.dumps(file_ids),
            json.dumps(media_types),
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

        bot.send_message(
            message.chat.id,
            f"✅ Pack creado:\n\n"
            f"<b>{title}</b>\n"
            f"Precio: {format_price(price)}\n"
            f"Archivos: {len(file_ids)}"
        )
        return

    # Recibir archivo
    if message.photo:
        file_ids.append(message.photo[-1].file_id)
        media_types.append("photo")
        bot.send_message(message.chat.id, f"Foto añadida ({len(file_ids)}). Envía más o /listo")
    elif message.video:
        file_ids.append(message.video.file_id)
        media_types.append("video")
        bot.send_message(message.chat.id, f"Video añadido ({len(file_ids)}). Envía más o /listo")
    elif message.document:
        file_ids.append(message.document.file_id)
        media_types.append("document")
        bot.send_message(message.chat.id, f"Documento añadido ({len(file_ids)}). Envía más o /listo")
    else:
        bot.send_message(message.chat.id, "Envía foto, video o documento. O escribe /listo")

    bot.register_next_step_handler(message, add_pack_files, title, description, price, file_ids, media_types)

@bot.message_handler(commands=["pendientes"])
def cmd_pendientes(message):
    if not is_admin(message.from_user.id):
        return

    conn = get_db()
    rows = conn.execute("""
        SELECT pay.id, pay.user_id, pay.amount, pay.created_at, p.title, u.username, u.first_name
        FROM payments pay
        JOIN packs p ON p.id = pay.pack_id
        LEFT JOIN users u ON u.user_id = pay.user_id
        WHERE pay.status = 'pending'
        ORDER BY pay.created_at ASC
    """).fetchall()
    conn.close()

    if not rows:
        bot.send_message(message.chat.id, "No hay pagos pendientes.")
        return

    text = f"📋 <b>Pagos pendientes ({len(rows)})</b>\n\n"
    for r in rows:
        uname = f"@{r['username']}" if r["username"] else r["first_name"]
        text += (
            f"#{r['id']} — {uname} (ID {r['user_id']})\n"
            f"Pack: {r['title']} — {format_price(r['amount'])}\n"
            f"Fecha: {r['created_at'][:16]}\n\n"
        )

    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["list_packs"])
def cmd_list_packs(message):
    if not is_admin(message.from_user.id):
        return

    conn = get_db()
    packs = conn.execute("SELECT * FROM packs ORDER BY id DESC").fetchall()
    conn.close()

    if not packs:
        bot.send_message(message.chat.id, "No hay packs.")
        return

    text = "📦 <b>Packs:</b>\n\n"
    for p in packs:
        status = "✅" if p["active"] else "❌"
        text += f"{status} #{p['id']} <b>{p['title']}</b> — {format_price(p['price'])}\n"

    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["stats"])
def cmd_stats(message):
    if not is_admin(message.from_user.id):
        return

    conn = get_db()
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    packs = conn.execute("SELECT COUNT(*) FROM packs WHERE active = 1").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'").fetchone()[0]
    approved = conn.execute("SELECT COUNT(*) FROM payments WHERE status = 'approved'").fetchone()[0]
    revenue = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'approved'").fetchone()[0]
    conn.close()

    text = (
        f"📊 <b>Estadísticas</b>\n\n"
        f"Usuarios: {users}\n"
        f"Packs activos: {packs}\n"
        f"Pagos pendientes: {pending}\n"
        f"Pagos aprobados: {approved}\n"
        f"Ingresos: {format_price(revenue)}"
    )
    bot.send_message(message.chat.id, text)

# ==================== ARRANQUE ====================
if __name__ == "__main__":
    init_db()
    print("Bot tipo OnlyFans iniciado...")
    bot.infinity_polling()
