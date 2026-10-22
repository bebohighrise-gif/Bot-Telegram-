#!/usr/bin/env python3
"""
OnlyFans_ManagerBot - V9
- Comisión de plataforma: tú ganas un % de CADA pago
- Creador edita precios de sus planes
- Borrar contenidos
- Sistema de videollamadas (solicitar → aceptar → completar)
- Todo lo anterior (perfiles, packs, likes, protect_content, grupo...)
"""

import html
import json
import math
import os
import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
GROUP_ID = int(os.environ["GROUP_ID"]) if os.environ.get("GROUP_ID") else None
GROUP_INVITE = os.environ.get("GROUP_INVITE", "")
CREATOR_FEE = 50.0
PLATFORM_FEE_PERCENT = 20.0
PROMO_COOLDOWN_MINUTES = 30
WEBAPP_VERIFICATION_URL = os.environ.get("WEBAPP_VERIFICATION_URL", "")
DB_FILE = os.environ.get("DB_FILE", "bot.db")
MIN_PLAN_PRICE = 0.50
MAX_PLAN_PRICE = 10000.00

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")
group_muted = False

PLAN_TYPES = {
    "pack3": {"name": "Pack 3 fotos", "default_price": 4.99, "days": 0, "credits": 3},
    "pack10": {"name": "Pack 10 fotos", "default_price": 12.99, "days": 0, "credits": 10},
    "monthly": {"name": "Mensual (ilimitado)", "default_price": 9.99, "days": 30, "credits": 0},
    "quarterly": {"name": "Trimestral (ilimitado)", "default_price": 24.99, "days": 90, "credits": 0},
    "videocall": {"name": "Videollamada", "default_price": 29.99, "days": 0, "credits": 0},
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
        "group_welcome": "👋 Bienvenido/a, {name}! /ayuda · /start en privado",
        "use_private": "⚠️ Usa en <b>chat privado</b>.",
        "only_vip": "👑 Solo VIP.",
        "only_admin": "🔒 Solo admin.",
        "only_creator": "🎨 Solo creadores.",
        "help_text": (
            "❓ <b>Ayuda</b>\n\n"
            "• Todos tienen perfil buscable.\n"
            "• Solo creadores ($50) publican.\n"
            "• Planes: packs, mensual, PPV, videollamada...\n"
            "• Contenido protegido (protect_content).\n"
            "• Likes, dislikes, comentarios y favoritos.\n"
            "• La plataforma retiene un % de cada pago.\n"
            "• Ajustes: idioma, historial, eliminar datos."
        ),
        "menu_favs": "⭐ Favoritos",
        "menu_settings": "⚙️ Ajustes",
        "locked_preview": "🔒 <b>Contenido exclusivo</b>\nSuscríbete o desbloquea PPV para verlo.",
        "fav_added": "⭐ Añadido a favoritos",
        "fav_removed": "☆ Quitado de favoritos",
        "blocked": "🚫 Usuario bloqueado. No verás su contenido.",
        "unblocked": "✅ Usuario desbloqueado.",
        "delete_data_confirm": "⚠️ Esto borra tu cuenta, suscripciones y favoritos. ¿Confirmas?",
        "delete_data_done": "✅ Datos eliminados. Usa /start para volver a registrarte.",
        "msg_creator_prompt": "✉️ Escribe el mensaje para el creador (máx. 500 caracteres):",
        "msg_sent": "✅ Mensaje enviado al creador.",
        "payment_test_mode": "🧪 <b>Modo prueba de pagos</b>: los accesos solo se activan tras aprobación manual del admin.",
        "no_favs": "Sin favoritos aún. Márcalos desde el perfil del creador.",
        "settings_title": "⚙️ <b>Ajustes</b>",
        "lang_set": "✅ Idioma actualizado.",
        "pay_history": "💳 <b>Historial de pagos</b>",
        "empty_history": "Sin pagos registrados.",
        "login_title": "👋 <b>Bienvenido</b>",
        "login_text": "Plataforma de creadores y suscripciones <b>dentro de Telegram</b>.\n\nPara continuar inicia tu cuenta. Telegram ya te autentica; solo configuramos tu perfil.",
        "login_btn": "🚀 Iniciar / Entrar",
        "onboard_name": "📝 <b>Paso 1/6 — Nombre visible</b>\nEscribe el nombre que verán los demás (2-40 caracteres):",
        "onboard_bio": "📄 <b>Paso 2/6 — Biografía</b>\nCuéntanos algo sobre ti (o escribe <code>skip</code> para omitir):",
        "onboard_photo": "📷 <b>Paso 3/3 — Foto de perfil</b>\nEnvía una <b>foto</b> o pulsa omitir.",
        "onboard_skip_photo": "Omitir foto",
        "onboard_done": "✅ <b>Perfil listo</b>\nYa puedes explorar creadores, suscribirte y gestionar tu cuenta.",
        "profile_incomplete": "Completa tu perfil antes de continuar.",
        "edit_profile": "✏️ Editar perfil",
        "set_name": "📝 Cambiar nombre",
        "set_bio": "📄 Cambiar bio",
        "set_photo": "📷 Cambiar foto",
        "name_saved": "✅ Nombre guardado.",
        "bio_saved": "✅ Bio guardada.",
        "photo_saved": "✅ Foto de perfil guardada.",
        "onboard_location": "📍 <b>Paso 3/6 — Ubicación</b>\nCiudad/país (o escribe <code>skip</code>):",
        "onboard_links": "🔗 <b>Paso 4/6 — Enlaces</b>\nEnvía tu web o redes en una línea.\nEjemplo: <code>https://site.com | @instagram | @x | @tiktok</code>\nO escribe <code>skip</code>.",
        "onboard_photo_req": "📷 <b>Paso 5/6 — Foto de perfil (obligatoria)</b>\nEnvía una <b>foto</b>. Sin foto no puedes continuar.",
        "onboard_cats": "🏷️ <b>Paso 6/6 — Categorías</b>\nElige hasta 3 (puedes cambiar después):",
        "location_saved": "✅ Ubicación guardada.",
        "links_saved": "✅ Enlaces guardados.",
        "cats_saved": "✅ Categorías guardadas.",
        "photo_required": "📷 La foto de perfil es obligatoria. Envía una imagen.",
        "set_location": "📍 Ubicación",
        "set_links": "🔗 Enlaces / redes",
        "set_cats": "🏷️ Categorías",
    },
    "en": {
        "welcome": "💖 <b>Welcome, {name}</b>\n\nExclusive content only inside the bot.",
        "age_title": "🔒 Age Confirmation",
        "age_text": "Adult content. Over 18?",
        "age_yes": "✅ Yes",
        "age_no": "❌ No",
        "age_denied": "🚫 Adults only.",
        "terms_accept": "✅ Accept",
        "terms_deny": "❌ Deny",
        "terms_must": "Accept terms.",
        "menu_explore": "🔍 Explore",
        "menu_search": "🔎 Search",
        "menu_subs": "📋 My plans",
        "menu_account": "👤 My profile",
        "menu_help": "❓ Help",
        "menu_creator": "🎨 Creator Panel",
        "menu_admin": "🔧 Admin",
        "back": "« Back",
        "back_menu": "« Menu",
        "must_pay": "🔒 Need an active plan.",
        "has_sub": "✅ You have access",
        "view_content": "📸 View content",
        "no_content": "No content.",
        "report": "📢 Report",
        "request_verif": "📸 Verify",
        "banned": "🚫 Banned.",
        "no_creators": "No creators.",
        "search_prompt": "🔎 Name or @username:",
        "search_empty": "No results.",
        "group_welcome": "👋 Welcome, {name}!",
        "use_private": "⚠️ Private chat only.",
        "only_vip": "👑 VIP only.",
        "only_admin": "🔒 Admin only.",
        "only_creator": "🎨 Creators only.",
        "help_text": "Help: profiles, creators, plans, PPV, protected content, favorites, settings.",
        "menu_favs": "⭐ Favorites",
        "menu_settings": "⚙️ Settings",
        "locked_preview": "🔒 <b>Exclusive content</b>\nSubscribe or unlock PPV to view.",
        "fav_added": "⭐ Added to favorites",
        "fav_removed": "☆ Removed from favorites",
        "blocked": "🚫 User blocked.",
        "unblocked": "✅ User unblocked.",
        "delete_data_confirm": "⚠️ This deletes your account, subscriptions and favorites. Confirm?",
        "delete_data_done": "✅ Data deleted. Use /start to register again.",
        "msg_creator_prompt": "✉️ Message for the creator (max 500 chars):",
        "msg_sent": "✅ Message sent to creator.",
        "payment_test_mode": "🧪 <b>Payment test mode</b>: access only after manual admin approval.",
        "no_favs": "No favorites yet.",
        "settings_title": "⚙️ <b>Settings</b>",
        "lang_set": "✅ Language updated.",
        "pay_history": "💳 <b>Payment history</b>",
        "empty_history": "No payments yet.",
        "login_title": "👋 <b>Welcome</b>",
        "login_text": "Creator subscription platform <b>inside Telegram</b>.\n\nContinue to set up your account. Telegram already authenticates you.",
        "login_btn": "🚀 Sign in",
        "onboard_name": "📝 <b>Step 1/6 — Display name</b>\nType the name others will see (2-40 chars):",
        "onboard_bio": "📄 <b>Step 2/6 — Bio</b>\nTell something about you (or type <code>skip</code>):",
        "onboard_photo": "📷 <b>Step 3/3 — Profile photo</b>\nSend a <b>photo</b> or skip.",
        "onboard_skip_photo": "Skip photo",
        "onboard_done": "✅ <b>Profile ready</b>\nYou can explore creators and manage your account.",
        "profile_incomplete": "Complete your profile first.",
        "edit_profile": "✏️ Edit profile",
        "set_name": "📝 Change name",
        "set_bio": "📄 Change bio",
        "set_photo": "📷 Change photo",
        "name_saved": "✅ Name saved.",
        "bio_saved": "✅ Bio saved.",
        "photo_saved": "✅ Profile photo saved.",
        "onboard_location": "📍 <b>Step 3/6 — Location</b>\nCity/country (or type <code>skip</code>):",
        "onboard_links": "🔗 <b>Step 4/6 — Links</b>\nSend website or socials in one line.\nExample: <code>https://site.com | @instagram | @x | @tiktok</code>\nOr type <code>skip</code>.",
        "onboard_photo_req": "📷 <b>Step 5/6 — Profile photo (required)</b>\nSend a <b>photo</b>. You cannot continue without one.",
        "onboard_cats": "🏷️ <b>Step 6/6 — Categories</b>\nPick up to 3 (you can change later):",
        "location_saved": "✅ Location saved.",
        "links_saved": "✅ Links saved.",
        "cats_saved": "✅ Categories saved.",
        "photo_required": "📷 Profile photo is required. Send an image.",
        "set_location": "📍 Location",
        "set_links": "🔗 Links / socials",
        "set_cats": "🏷️ Categories",
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
    conn.row_factory = sqlite3.Row
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
    c.execute("""CREATE TABLE IF NOT EXISTS creator_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id INTEGER,
        plan_type TEXT, name TEXT, price REAL, days INTEGER DEFAULT 0,
        credits INTEGER DEFAULT 0, description TEXT, active INTEGER DEFAULT 1)""")
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
        type TEXT, amount REAL, platform_fee REAL DEFAULT 0, creator_net REAL DEFAULT 0,
        status TEXT DEFAULT 'pending', payment_method TEXT, screenshot_file_id TEXT,
        plan_id INTEGER, created_at TEXT, reviewed_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS videocalls (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, creator_id INTEGER,
        amount REAL, status TEXT DEFAULT 'requested',
        requested_at TEXT, scheduled_at TEXT, completed_at TEXT, notes TEXT)""")
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
    c.execute("""CREATE TABLE IF NOT EXISTS favorites (
        user_id INTEGER, creator_id INTEGER, created_at TEXT,
        PRIMARY KEY (user_id, creator_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS unlocked_content (
        user_id INTEGER, content_id INTEGER, subscription_id INTEGER,
        unlocked_at TEXT, PRIMARY KEY (user_id, content_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS blocks (
        user_id INTEGER, blocked_id INTEGER, created_at TEXT,
        PRIMARY KEY (user_id, blocked_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, emoji TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS creator_categories (
        creator_id INTEGER, category_id INTEGER,
        PRIMARY KEY (creator_id, category_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS creator_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, from_id INTEGER, to_id INTEGER,
        text TEXT, created_at TEXT)""")

    # The bot has been deployed with earlier schemas. Add new columns in-place
    # before handlers use them; never delete or recreate a user's database.
    migrations = {
        "users": {
            "bio": "TEXT DEFAULT ''", "notify_enabled": "INTEGER DEFAULT 1",
            "display_name": "TEXT", "profile_photo_id": "TEXT",
            "profile_complete": "INTEGER DEFAULT 0", "onboard_step": "TEXT DEFAULT ''",
            "location": "TEXT DEFAULT ''", "website": "TEXT DEFAULT ''",
            "social_ig": "TEXT DEFAULT ''", "social_x": "TEXT DEFAULT ''",
            "social_tiktok": "TEXT DEFAULT ''",
        },
        "subscriptions": {
            "plan_id": "INTEGER", "plan_type": "TEXT", "credits_left": "INTEGER DEFAULT 0",
        },
        "content": {
            "file_id": "TEXT", "media_type": "TEXT DEFAULT 'photo'",
            "likes": "INTEGER DEFAULT 0", "dislikes": "INTEGER DEFAULT 0",
            "ppv_price": "REAL DEFAULT 0", "is_free": "INTEGER DEFAULT 0",
        },
        "transactions": {
            "platform_fee": "REAL DEFAULT 0", "creator_net": "REAL DEFAULT 0",
            "plan_id": "INTEGER",
        },
        "videocalls": {"transaction_id": "INTEGER"},
    }
    for table, columns in migrations.items():
        existing = {row[1] for row in c.execute(f"PRAGMA table_info({table})")}
        legacy_transaction_fees = table == "transactions" and "creator_net" not in existing
        for column, definition in columns.items():
            if column not in existing:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        if legacy_transaction_fees:
            c.execute("UPDATE transactions SET creator_net=amount WHERE type!='creator_fee' AND creator_net=0")

    # V4 enforced one subscription per user/creator. V9 supports separate
    # packs, so replace only that obsolete uniqueness constraint, preserving
    # every existing subscription and its ID.
    legacy_subscription_unique = False
    for index in c.execute("PRAGMA index_list(subscriptions)").fetchall():
        if index["unique"]:
            index_name = index["name"].replace('"', '""')
            indexed_columns = [r["name"] for r in c.execute(
                f'PRAGMA index_info("{index_name}")').fetchall()]
            if indexed_columns == ["user_id", "creator_id"]:
                legacy_subscription_unique = True
                break
    if legacy_subscription_unique:
        old_subscriptions = c.execute("SELECT * FROM subscriptions").fetchall()
        c.execute("""CREATE TABLE subscriptions_v9 (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, creator_id INTEGER,
            plan_id INTEGER, plan_type TEXT, amount REAL, status TEXT DEFAULT 'active',
            start_date TEXT, end_date TEXT, credits_left INTEGER DEFAULT 0,
            payment_method TEXT, created_at TEXT)""")
        old_columns = set(old_subscriptions[0].keys()) if old_subscriptions else set()
        for sub in old_subscriptions:
            plan_type = (sub["plan_type"] if "plan_type" in old_columns else None)
            if not plan_type and "plan" in old_columns:
                plan_type = sub["plan"]
            c.execute("""INSERT INTO subscriptions_v9
                (id,user_id,creator_id,plan_id,plan_type,amount,status,start_date,end_date,credits_left,payment_method,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sub["id"], sub["user_id"], sub["creator_id"], sub["plan_id"], plan_type,
                 sub["amount"], sub["status"], sub["start_date"], sub["end_date"],
                 sub["credits_left"] or 0, sub["payment_method"], sub["created_at"]))
        c.execute("DROP TABLE subscriptions")
        c.execute("ALTER TABLE subscriptions_v9 RENAME TO subscriptions")

    # Preserve legacy V4 media when converting its JSON file-id arrays to V9's
    # one-file-per-row representation. Re-running init_db is idempotent.
    legacy_columns = {row[1] for row in c.execute("PRAGMA table_info(content)")}
    if {"file_ids", "media_types"}.issubset(legacy_columns):
        legacy_rows = c.execute(
            "SELECT id, creator_id, title, description, file_ids, media_types, is_premium, views, created_at "
            "FROM content WHERE file_id IS NULL AND file_ids IS NOT NULL"
        ).fetchall()
        for row in legacy_rows:
            try:
                file_ids = json.loads(row["file_ids"])
                media_types = json.loads(row["media_types"] or "[]")
            except (TypeError, ValueError):
                continue
            if not isinstance(file_ids, list) or not file_ids:
                continue
            for index, file_id in enumerate(file_ids):
                if not isinstance(file_id, str) or not file_id:
                    continue
                media_type = media_types[index] if index < len(media_types) else "photo"
                if media_type not in ("photo", "video"):
                    media_type = "photo"
                if index == 0:
                    c.execute("UPDATE content SET file_id=?, media_type=? WHERE id=?",
                              (file_id, media_type, row["id"]))
                else:
                    c.execute("""INSERT INTO content
                        (creator_id,title,description,file_id,media_type,is_premium,views,created_at)
                        VALUES (?,?,?,?,?,?,?,?)""",
                              (row["creator_id"], row["title"], row["description"], file_id,
                               media_type, row["is_premium"], row["views"], row["created_at"]))

    defaults = {
        "payment_methods": "💳 <b>Formas de pago:</b>\n\n• Transferencia / Bizum\n• Crypto (USDT/BTC)\n• Telegram Stars\n\n<i>El admin actualiza los datos.</i>",
        "terms": "📜 <b>Términos</b>\n1. +18.\n2. Uso personal.\n3. Prohibida redistribución.\n4. La plataforma retiene un % de cada pago.",
        "group_rules": "📜 <b>Reglas</b>\n1. Respeta.\n2. No spam.\n3. /promo cada 30 min (VIP).\n4. /soporte.\n5. Admin puede silenciar.",
        "announcement": "📢 Contenido solo dentro del bot. Usa /ayuda.",
        "platform_fee": str(PLATFORM_FEE_PERCENT),
    }
    for k, v in defaults.items():
        if not c.execute("SELECT 1 FROM settings WHERE key=?", (k,)).fetchone():
            c.execute("INSERT INTO settings VALUES (?,?)", (k, v))

    for pay_key in ("pay_zelle", "pay_mexico", "pay_oxxo", "pay_euros", "pay_mobile", "pay_other"):
        if not c.execute("SELECT 1 FROM settings WHERE key=?", (pay_key,)).fetchone():
            c.execute("INSERT INTO settings VALUES (?,?)", (pay_key, "—"))

    if not c.execute("SELECT 1 FROM group_settings WHERE key='muted'").fetchone():
        c.execute("INSERT INTO group_settings VALUES ('muted','0')")
    for cat_name, cat_emoji in [("Fitness", "💪"), ("Lifestyle", "✨"), ("Arte", "🎨"), ("Gaming", "🎮"), ("Adulto", "🔥")]:
        if not c.execute("SELECT 1 FROM categories WHERE name=?", (cat_name,)).fetchone():
            c.execute("INSERT INTO categories (name, emoji) VALUES (?,?)", (cat_name, cat_emoji))
    conn.commit()
    conn.close()
    ensure_admin()
    ensure_existing_creator_plans()

def ensure_existing_creator_plans():
    """Seed V9 plans for already-approved V4 creators without overwriting data."""
    conn = get_db()
    creator_columns = {row[1] for row in conn.execute("PRAGMA table_info(creators)")}
    creators = conn.execute("""SELECT c.* FROM creators c JOIN users u ON u.user_id=c.user_id
        WHERE u.creator_verified=2 AND u.banned=0""").fetchall()
    for creator in creators:
        if conn.execute("SELECT 1 FROM creator_plans WHERE creator_id=? LIMIT 1",
                        (creator["user_id"],)).fetchone():
            continue
        for plan_type, info in PLAN_TYPES.items():
            price = info["default_price"]
            legacy_price_column = {"monthly": "monthly_price", "quarterly": "quarterly_price"}.get(plan_type)
            if legacy_price_column in creator_columns:
                try:
                    price = validate_plan_price(creator[legacy_price_column])
                except (TypeError, ValueError):
                    pass
            conn.execute("""INSERT INTO creator_plans
                (creator_id,plan_type,name,price,days,credits,description)
                VALUES (?,?,?,?,?,?,?)""",
                (creator["user_id"], plan_type, info["name"], price,
                 info["days"], info["credits"], info["name"]))
    conn.commit()
    conn.close()

def ensure_admin():
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("""INSERT OR IGNORE INTO users
        (user_id, role, age_declared, terms_accepted, age_verified_real, gender_verified, creator_verified, language, profile_complete, joined_at, last_active)
        VALUES (?, 'admin', 1, 1, 2, 1, 2, 'es', 1, ?, ?)""", (ADMIN_ID, now, now))
    conn.execute("UPDATE users SET role='admin', age_declared=1, terms_accepted=1, age_verified_real=2, gender_verified=1, creator_verified=2, profile_complete=1 WHERE user_id=?", (ADMIN_ID,))
    conn.execute("INSERT OR IGNORE INTO creators (user_id, display_name, bio, created_at) VALUES (?, 'Admin Principal', 'Creador principal', ?)", (ADMIN_ID, now))
    if not conn.execute("SELECT 1 FROM creator_plans WHERE creator_id=?", (ADMIN_ID,)).fetchone():
        for ptype, info in PLAN_TYPES.items():
            conn.execute("INSERT INTO creator_plans (creator_id, plan_type, name, price, days, credits, description) VALUES (?,?,?,?,?,?,?)",
                         (ADMIN_ID, ptype, info["name"], info["default_price"], info["days"], info["credits"], info["name"]))
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
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

def get_platform_fee_percent():
    try:
        value = float(get_setting("platform_fee") or PLATFORM_FEE_PERCENT)
        if math.isfinite(value) and 0 <= value <= 100:
            return value
    except (sqlite3.Error, TypeError, ValueError):
        pass
    return PLATFORM_FEE_PERCENT

def validate_plan_price(value):
    """Return a bounded finite price or raise ValueError."""
    try:
        price = float(value)
    except (TypeError, ValueError):
        raise ValueError("Precio inválido")
    if not math.isfinite(price) or not MIN_PLAN_PRICE <= price <= MAX_PLAN_PRICE:
        raise ValueError("El precio debe estar entre $0.50 y $10,000")
    return round(price, 2)

def escape_html(value):
    return html.escape(str(value or ""), quote=False)

def calc_fee(amount):
    amount = validate_plan_price(amount)
    pct = get_platform_fee_percent()
    fee = round(amount * pct / 100, 2)
    return fee, round(amount - fee, 2)

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
    return u and not u["banned"] and u["role"] in ("creator", "admin") and u["creator_verified"] == 2
def is_vip(uid):
    if is_admin(uid) or is_creator(uid): return True
    conn = get_db()
    row = conn.execute("""SELECT 1 FROM subscriptions WHERE user_id=? AND status='active'
        AND (end_date > ? OR credits_left > 0)""", (uid, datetime.now().isoformat())).fetchone()
    conn.close()
    return bool(row)
def format_price(p): return f"${p:.2f}"

def get_active_subscriptions(user_id, creator_id):
    """Todas las suscripciones activas usuario→creador (packs + tiempo)."""
    if is_banned(user_id):
        return []
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM subscriptions WHERE user_id=? AND creator_id=? AND status='active'
           AND (end_date > ? OR IFNULL(credits_left,0) > 0) ORDER BY id DESC""",
        (user_id, creator_id, datetime.now().isoformat()),
    ).fetchall()
    conn.close()
    return list(rows)

def has_unlimited_access(user_id, creator_id):
    """Plan mensual/trimestral o admin: acceso a TODO el feed."""
    if is_admin(user_id):
        return True
    for sub in get_active_subscriptions(user_id, creator_id):
        ptype = (sub["plan_type"] or "") if "plan_type" in sub.keys() else ""
        # Unlimited if time-based plan still valid (days > 0 plans)
        if ptype in ("monthly", "quarterly") or (
            sub["end_date"] and sub["end_date"] > datetime.now().isoformat()
            and not (sub["credits_left"] and sub["credits_left"] > 0 and ptype.startswith("pack"))
        ):
            # Time window active and not a pure credit pack
            if ptype in ("monthly", "quarterly"):
                return True
            if sub["end_date"] and sub["end_date"] > datetime.now().isoformat() and ptype not in (
                "pack3", "pack10", "videocall"
            ) and not (ptype or "").startswith("pack"):
                return True
    return False

def get_pack_credits(user_id, creator_id):
    """Créditos restantes de packs (solo packs, no mensuales)."""
    total = 0
    for sub in get_active_subscriptions(user_id, creator_id):
        ptype = (sub["plan_type"] or "") if "plan_type" in sub.keys() else ""
        if ptype.startswith("pack") or ptype in ("pack3", "pack10"):
            total += int(sub["credits_left"] or 0)
    return total

def has_access(user_id, creator_id):
    if is_admin(user_id):
        return True
    if is_banned(user_id):
        return False
    if has_unlimited_access(user_id, creator_id):
        return True
    return get_pack_credits(user_id, creator_id) > 0 or _has_any_unlocked(user_id, creator_id)

def _has_any_unlocked(user_id, creator_id):
    conn = get_db()
    row = conn.execute(
        """SELECT 1 FROM unlocked_content u
           JOIN content c ON c.id=u.content_id
           WHERE u.user_id=? AND c.creator_id=? LIMIT 1""",
        (user_id, creator_id),
    ).fetchone()
    conn.close()
    return bool(row)

def is_content_unlocked(user_id, content_id):
    if is_admin(user_id):
        return True
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM unlocked_content WHERE user_id=? AND content_id=?",
        (user_id, content_id),
    ).fetchone()
    if row:
        conn.close()
        return True
    # Check if content belongs to creator with unlimited sub
    c = conn.execute("SELECT creator_id, is_free FROM content WHERE id=?", (content_id,)).fetchone()
    conn.close()
    if not c:
        return False
    if c["is_free"]:
        return True
    return has_unlimited_access(user_id, c["creator_id"])

def unlock_content_with_credit(user_id, content_id, creator_id):
    """Gasta 1 crédito de pack y marca el post como desbloqueado. Mensual no gasta."""
    if is_admin(user_id) or has_unlimited_access(user_id, creator_id):
        return True, "unlimited"
    if is_content_unlocked(user_id, content_id):
        return True, "already"
    conn = get_db()
    sub = conn.execute(
        """SELECT * FROM subscriptions WHERE user_id=? AND creator_id=? AND status='active'
           AND IFNULL(credits_left,0) > 0
           AND (plan_type LIKE 'pack%' OR plan_type IN ('pack3','pack10'))
           ORDER BY id DESC LIMIT 1""",
        (user_id, creator_id),
    ).fetchone()
    if not sub:
        conn.close()
        return False, "no_credits"
    conn.execute(
        "UPDATE subscriptions SET credits_left = credits_left - 1 WHERE id=? AND credits_left > 0",
        (sub["id"],),
    )
    conn.execute(
        "INSERT OR IGNORE INTO unlocked_content (user_id, content_id, subscription_id, unlocked_at) VALUES (?,?,?,?)",
        (user_id, content_id, sub["id"], datetime.now().isoformat()),
    )
    conn.commit()
    left = conn.execute("SELECT credits_left FROM subscriptions WHERE id=?", (sub["id"],)).fetchone()
    conn.close()
    return True, f"credits:{(left['credits_left'] if left else 0)}"

def consume_credit(user_id, creator_id):
    """Compat: True si puede ver algo (ilimitado o tiene créditos)."""
    if is_admin(user_id) or has_unlimited_access(user_id, creator_id):
        return True
    return get_pack_credits(user_id, creator_id) > 0

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

def build_payment_methods_text():
    parts = [
        ("🇺🇸 Zelle", get_setting("pay_zelle") or "—"),
        ("🇲🇽 México (banco/CLABE)", get_setting("pay_mexico") or "—"),
        ("🏪 OXXO", get_setting("pay_oxxo") or "—"),
        ("🇪🇺 Euros", get_setting("pay_euros") or "—"),
        ("📱 Saldo móvil", get_setting("pay_mobile") or "—"),
        ("➕ Otro", get_setting("pay_other") or "—"),
    ]
    lines = ["💳 <b>Formas de pago</b> (configuradas por el admin):", ""]
    for label, val in parts:
        lines.append(f"• <b>{label}</b>: {escape_html(val)}")
    lines.append("")
    lines.append("<i>Modo revisión manual: el acceso se activa cuando el admin aprueba la captura.</i>")
    lines.append("<i>Después de pagar, usa «Ya pagué» y envía la captura.</i>")
    return "\n".join(lines)

def refresh_payment_methods_setting():
    set_setting("payment_methods", build_payment_methods_text())

def main_reply_keyboard(lang="es"):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    kb.row(types.KeyboardButton("🔍 Explorar"), types.KeyboardButton("🔎 Buscar"), types.KeyboardButton("⭐ Favoritos"))
    kb.row(types.KeyboardButton("📋 Mis planes"), types.KeyboardButton("👤 Mi perfil"), types.KeyboardButton("⚙️ Ajustes"))
    kb.row(types.KeyboardButton("❓ Ayuda"), types.KeyboardButton("🏠 Menú"))
    return kb



def safe_answer(call, *args, **kwargs):
    try:
        if getattr(call, "id", None) and call.id != "rk":
            bot.answer_callback_query(call.id, *args, **kwargs)
    except Exception:
        pass

def profile_is_complete(user):

    if not user:
        return False
    try:
        return int(user["profile_complete"] or 0) == 1
    except (KeyError, TypeError, ValueError):
        return False


def is_blocked(viewer_id, target_id):
    if not viewer_id or not target_id: return False
    conn = get_db()
    row = conn.execute("SELECT 1 FROM blocks WHERE user_id=? AND blocked_id=?",
                       (viewer_id, target_id)).fetchone()
    conn.close()
    return bool(row)

def is_favorite(user_id, creator_id):
    conn = get_db()
    row = conn.execute("SELECT 1 FROM favorites WHERE user_id=? AND creator_id=?",
                       (user_id, creator_id)).fetchone()
    conn.close()
    return bool(row)

def toggle_favorite(user_id, creator_id):
    conn = get_db()
    if conn.execute("SELECT 1 FROM favorites WHERE user_id=? AND creator_id=?",
                    (user_id, creator_id)).fetchone():
        conn.execute("DELETE FROM favorites WHERE user_id=? AND creator_id=?", (user_id, creator_id))
        conn.commit(); conn.close()
        return False
    conn.execute("INSERT INTO favorites (user_id, creator_id, created_at) VALUES (?,?,?)",
                 (user_id, creator_id, datetime.now().isoformat()))
    conn.commit(); conn.close()
    return True

def get_creator_categories(creator_id):
    conn = get_db()
    rows = conn.execute("""SELECT c.name, c.emoji FROM categories c
        JOIN creator_categories cc ON cc.category_id=c.id WHERE cc.creator_id=?""",
                        (creator_id,)).fetchall()
    conn.close()
    return rows

# ==================== MENÚ ====================
def main_menu_kb(user_id, lang):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton(t("menu_explore", lang), callback_data="menu_explore"),
           types.InlineKeyboardButton(t("menu_search", lang), callback_data="menu_search"))
    kb.add(types.InlineKeyboardButton(t("menu_subs", lang), callback_data="menu_subs"),
           types.InlineKeyboardButton(t("menu_favs", lang), callback_data="menu_favs"))
    kb.add(types.InlineKeyboardButton(t("menu_account", lang), callback_data="menu_account"),
           types.InlineKeyboardButton(t("menu_settings", lang), callback_data="menu_settings"))
    kb.add(types.InlineKeyboardButton(t("menu_help", lang), callback_data="menu_help"))
    if is_creator(user_id):
        kb.add(types.InlineKeyboardButton(t("menu_creator", lang), callback_data="creator_panel"))
    if is_admin(user_id):
        kb.add(types.InlineKeyboardButton(t("menu_admin", lang), callback_data="admin_panel"))
    return kb

def send_main_menu(chat_id, user_id, message_id=None, lang=None):
    user = get_user(user_id)
    lang = lang or (user["language"] if user else "es")
    if user and not is_admin(user_id) and (not user["age_declared"] or not user["terms_accepted"] or not profile_is_complete(user)):
        show_login(chat_id, lang, None)
        return
    dname = (user["display_name"] if user and user["display_name"] else None) or (user["first_name"] if user else "User")
    text = t("welcome", lang, name=escape_html(dname))
    kb = main_menu_kb(user_id, lang)
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            # Keep quick-access reply keyboard visible
            bot.send_message(chat_id, "⌨️ Acceso rápido abajo", reply_markup=main_reply_keyboard(lang))
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)
    bot.send_message(chat_id, "⌨️ Usa el teclado inferior para acceso rápido", reply_markup=main_reply_keyboard(lang))

# ==================== START ====================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    if not is_private_chat(message):
        bot.reply_to(message, t("use_private", get_lang(tg_user=message.from_user)))
        return
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, t("banned", get_lang(tg_user=message.from_user)))
        return
    referral_creator_id = None
    args = (message.text or "").split(maxsplit=1)
    if len(args) == 2 and args[1].startswith("creator_"):
        try:
            referral_creator_id = int(args[1][8:])
        except ValueError:
            referral_creator_id = None
    upsert_user(message.from_user)
    user = get_user(message.from_user.id)
    lang = (user["language"] if user else None) or get_lang(tg_user=message.from_user)
    # Save pending referral until onboarding ends
    if referral_creator_id:
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                     (f"ref_{message.from_user.id}", str(referral_creator_id)))
        conn.commit()
        conn.close()
    # Gate: login → age → terms → profile setup → menu
    if not user or not user["age_declared"] or not user["terms_accepted"] or not profile_is_complete(user):
        show_login(message.chat.id, lang, message.from_user)
        return
    ref = get_setting(f"ref_{message.from_user.id}")
    if ref:
        try:
            show_profile(message.chat.id, message.from_user.id, int(ref))
            set_setting(f"ref_{message.from_user.id}", "")
            return
        except Exception:
            pass
    send_main_menu(message.chat.id, message.from_user.id, lang=lang)

def show_login(chat_id, lang, tg_user=None):
    """Pantalla tipo login: Telegram ya autentica; el usuario confirma y configura perfil."""
    name = escape_html(getattr(tg_user, "first_name", None) or "Usuario")
    text = (
        f"{t('login_title', lang)}\n\n"
        f"{t('login_text', lang)}\n\n"
        f"👤 Sesión: <b>{name}</b>"
    )
    if tg_user and getattr(tg_user, "username", None):
        text += f" (@{escape_html(tg_user.username)})"
    text += f"\n🆔 <code>{getattr(tg_user, 'id', '')}</code>"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(t("login_btn", lang), callback_data="login_continue"))
    bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "login_continue")
def cb_login_continue(call):
    if not is_private_chat(call.message):
        bot.answer_callback_query(call.id, t("use_private", get_lang(tg_user=call.from_user)), show_alert=True)
        return
    upsert_user(call.from_user)
    user = get_user(call.from_user.id)
    lang = (user["language"] if user else None) or get_lang(tg_user=call.from_user)
    bot.answer_callback_query(call.id)
    if not user["age_declared"]:
        ask_age(call.message.chat.id, lang, call.message.message_id)
        return
    if not user["terms_accepted"]:
        ask_terms(call.message.chat.id, lang, call.message.message_id)
        return
    if not profile_is_complete(user):
        start_profile_setup(call.message.chat.id, call.from_user.id, lang, call.message.message_id)
        return
    send_main_menu(call.message.chat.id, call.from_user.id, call.message.message_id, lang)

def ask_age(chat_id, lang="es", message_id=None):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(t("age_yes", lang), callback_data="age_yes"),
           types.InlineKeyboardButton(t("age_no", lang), callback_data="age_no"))
    text = f"{t('age_title', lang)}\n\n{t('age_text', lang)}"
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ("age_yes", "age_no"))
def cb_age(call):
    lang = get_lang(call.from_user.id, call.from_user)
    user = get_user(call.from_user.id)
    if not user or is_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "Sesión no válida", show_alert=True)
        return
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
    user = get_user(call.from_user.id)
    if not user or not user["age_declared"] or is_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "Completa primero la confirmación de edad", show_alert=True)
        return
    if call.data == "terms_no":
        bot.edit_message_text(t("terms_must", lang), call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return
    conn = get_db()
    conn.execute("UPDATE users SET terms_accepted=1 WHERE user_id=?", (call.from_user.id,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id)
    user = get_user(call.from_user.id)
    if not profile_is_complete(user):
        start_profile_setup(call.message.chat.id, call.from_user.id, lang, call.message.message_id)
    else:
        send_main_menu(call.message.chat.id, call.from_user.id, call.message.message_id, lang)


# ==================== ONBOARDING PERFIL ====================
def _parse_links_line(text):
    """Parse 'url | @ig | @x | @tiktok' or free text into fields."""
    website = social_ig = social_x = social_tiktok = ""
    raw = (text or "").strip()
    if not raw or raw.lower() in ("skip", "omitir", "pasar", "-"):
        return website, social_ig, social_x, social_tiktok
    parts = [p.strip() for p in raw.replace(",", "|").split("|") if p.strip()]
    for p in parts:
        low = p.lower()
        if low.startswith("http://") or low.startswith("https://"):
            website = p[:200]
        elif "instagram" in low or low.startswith("@") and "ig" in low:
            social_ig = p.lstrip("@")[:80]
        elif low.startswith("tiktok.com") or "tiktok" in low:
            social_tiktok = p.lstrip("@")[:80]
        elif low.startswith("x.com") or low.startswith("twitter.com") or low.startswith("@"):
            # first bare @ goes to X if IG empty later reassigned heuristically
            if not social_x:
                social_x = p.lstrip("@")[:80]
            elif not social_ig:
                social_ig = p.lstrip("@")[:80]
            else:
                social_tiktok = social_tiktok or p.lstrip("@")[:80]
        else:
            if not website and "." in p:
                website = p[:200]
            elif not social_ig:
                social_ig = p.lstrip("@")[:80]
            elif not social_x:
                social_x = p.lstrip("@")[:80]
            else:
                social_tiktok = p.lstrip("@")[:80]
    return website, social_ig, social_x, social_tiktok


def start_profile_setup(chat_id, user_id, lang="es", message_id=None):
    conn = get_db()
    conn.execute("UPDATE users SET onboard_step='name' WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    text = t("onboard_name", lang)
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id)
        except Exception:
            bot.send_message(chat_id, text)
    else:
        bot.send_message(chat_id, text)
    msg = bot.send_message(chat_id, "👇")
    bot.register_next_step_handler(msg, process_onboard_name)


def process_onboard_name(message):
    if not is_private_chat(message):
        return
    lang = get_lang(message.from_user.id)
    name = (message.text or "").strip()
    if name.startswith("/"):
        bot.send_message(message.chat.id, t("onboard_name", lang))
        bot.register_next_step_handler(message, process_onboard_name)
        return
    if len(name) < 2 or len(name) > 40:
        bot.send_message(message.chat.id, "Nombre entre 2 y 40 caracteres.")
        bot.register_next_step_handler(message, process_onboard_name)
        return
    conn = get_db()
    conn.execute(
        "UPDATE users SET display_name=?, first_name=COALESCE(first_name, ?), onboard_step='bio' WHERE user_id=?",
        (name, name, message.from_user.id),
    )
    conn.execute("UPDATE creators SET display_name=? WHERE user_id=?", (name, message.from_user.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, t("name_saved", lang))
    msg = bot.send_message(message.chat.id, t("onboard_bio", lang))
    bot.register_next_step_handler(msg, process_onboard_bio)


def process_onboard_bio(message):
    if not is_private_chat(message):
        return
    lang = get_lang(message.from_user.id)
    bio = (message.text or "").strip()
    if bio.lower() in ("skip", "omitir", "pasar", "-"):
        bio = ""
    else:
        bio = bio[:300]
    conn = get_db()
    conn.execute("UPDATE users SET bio=?, onboard_step='location' WHERE user_id=?", (bio, message.from_user.id))
    conn.execute("UPDATE creators SET bio=? WHERE user_id=?", (bio, message.from_user.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, t("bio_saved", lang))
    msg = bot.send_message(message.chat.id, t("onboard_location", lang))
    bot.register_next_step_handler(msg, process_onboard_location)


def process_onboard_location(message):
    if not is_private_chat(message):
        return
    lang = get_lang(message.from_user.id)
    loc = (message.text or "").strip()
    if loc.lower() in ("skip", "omitir", "pasar", "-"):
        loc = ""
    else:
        loc = loc[:80]
    conn = get_db()
    conn.execute("UPDATE users SET location=?, onboard_step='links' WHERE user_id=?", (loc, message.from_user.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, t("location_saved", lang))
    msg = bot.send_message(message.chat.id, t("onboard_links", lang))
    bot.register_next_step_handler(msg, process_onboard_links)


def process_onboard_links(message):
    if not is_private_chat(message):
        return
    lang = get_lang(message.from_user.id)
    website, ig, x, tt = _parse_links_line(message.text)
    conn = get_db()
    conn.execute(
        """UPDATE users SET website=?, social_ig=?, social_x=?, social_tiktok=?, onboard_step='photo'
           WHERE user_id=?""",
        (website, ig, x, tt, message.from_user.id),
    )
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, t("links_saved", lang))
    msg = bot.send_message(message.chat.id, t("onboard_photo_req", lang))
    bot.register_next_step_handler(msg, process_onboard_photo)


def process_onboard_photo(message):
    if not is_private_chat(message):
        return
    lang = get_lang(message.from_user.id)
    user = get_user(message.from_user.id)
    if not user:
        return
    step = ""
    try:
        step = user["onboard_step"] or ""
    except Exception:
        step = ""
    if step not in ("photo", "done") and step != "photo":
        # still accept if mid-flow
        pass
    if not message.photo:
        bot.send_message(message.chat.id, t("photo_required", lang))
        bot.register_next_step_handler(message, process_onboard_photo)
        return
    file_id = message.photo[-1].file_id
    conn = get_db()
    conn.execute(
        "UPDATE users SET profile_photo_id=?, onboard_step='cats' WHERE user_id=?",
        (file_id, message.from_user.id),
    )
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, t("photo_saved", lang))
    send_category_picker(message.chat.id, message.from_user.id, lang, onboard=True)


def send_category_picker(chat_id, user_id, lang="es", onboard=False):
    conn = get_db()
    cats = conn.execute("SELECT id, name, emoji FROM categories ORDER BY id").fetchall()
    selected = {
        r[0]
        for r in conn.execute(
            "SELECT category_id FROM creator_categories WHERE creator_id=?", (user_id,)
        ).fetchall()
    }
    # also allow non-creators: store on user via same table keyed by user_id
    conn.close()
    text = t("onboard_cats", lang)
    if selected:
        text += f"\n\nSeleccionadas: {len(selected)}/3"
    kb = types.InlineKeyboardMarkup(row_width=2)
    row = []
    for c in cats:
        mark = "✅ " if c["id"] in selected else ""
        label = f"{mark}{c['emoji']} {c['name']}"
        row.append(types.InlineKeyboardButton(label, callback_data=f"catpick_{c['id']}_{1 if onboard else 0}"))
        if len(row) == 2:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    if onboard:
        kb.add(types.InlineKeyboardButton("✅ Listo / Continuar", callback_data="cats_done_onboard"))
    else:
        kb.add(types.InlineKeyboardButton("✅ Guardar", callback_data="cats_done_edit"))
        kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="edit_profile_menu"))
    bot.send_message(chat_id, text, reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("catpick_"))
def cb_catpick(call):
    lang = get_lang(call.from_user.id)
    parts = call.data.split("_")
    cat_id = int(parts[1])
    onboard = parts[2] == "1" if len(parts) > 2 else False
    uid = call.from_user.id
    conn = get_db()
    exists = conn.execute(
        "SELECT 1 FROM creator_categories WHERE creator_id=? AND category_id=?", (uid, cat_id)
    ).fetchone()
    if exists:
        conn.execute(
            "DELETE FROM creator_categories WHERE creator_id=? AND category_id=?", (uid, cat_id)
        )
    else:
        count = conn.execute(
            "SELECT COUNT(*) FROM creator_categories WHERE creator_id=?", (uid,)
        ).fetchone()[0]
        if count >= 3:
            conn.close()
            bot.answer_callback_query(call.id, "Máximo 3 categorías", show_alert=True)
            return
        conn.execute(
            "INSERT INTO creator_categories (creator_id, category_id) VALUES (?, ?)", (uid, cat_id)
        )
    conn.commit()
    selected = conn.execute(
        "SELECT COUNT(*) FROM creator_categories WHERE creator_id=?", (uid,)
    ).fetchone()[0]
    cats = conn.execute("SELECT id, name, emoji FROM categories ORDER BY id").fetchall()
    sel_ids = {
        r[0]
        for r in conn.execute(
            "SELECT category_id FROM creator_categories WHERE creator_id=?", (uid,)
        ).fetchall()
    }
    conn.close()
    text = t("onboard_cats", lang) + f"\n\nSeleccionadas: {selected}/3"
    kb = types.InlineKeyboardMarkup(row_width=2)
    row = []
    for c in cats:
        mark = "✅ " if c["id"] in sel_ids else ""
        label = f"{mark}{c['emoji']} {c['name']}"
        row.append(types.InlineKeyboardButton(label, callback_data=f"catpick_{c['id']}_{1 if onboard else 0}"))
        if len(row) == 2:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    if onboard:
        kb.add(types.InlineKeyboardButton("✅ Listo / Continuar", callback_data="cats_done_onboard"))
    else:
        kb.add(types.InlineKeyboardButton("✅ Guardar", callback_data="cats_done_edit"))
        kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="edit_profile_menu"))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except Exception:
        pass
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data == "cats_done_onboard")
def cb_cats_done_onboard(call):
    lang = get_lang(call.from_user.id)
    conn = get_db()
    # Photo must exist
    u = conn.execute("SELECT profile_photo_id FROM users WHERE user_id=?", (call.from_user.id,)).fetchone()
    if not u or not u["profile_photo_id"]:
        conn.close()
        bot.answer_callback_query(call.id, t("photo_required", lang), show_alert=True)
        return
    conn.execute(
        "UPDATE users SET profile_complete=1, onboard_step='done' WHERE user_id=?",
        (call.from_user.id,),
    )
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, t("cats_saved", lang))
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except Exception:
        pass
    finish_onboarding(call.message.chat.id, call.from_user.id, lang)


@bot.callback_query_handler(func=lambda c: c.data == "cats_done_edit")
def cb_cats_done_edit(call):
    lang = get_lang(call.from_user.id)
    bot.answer_callback_query(call.id, t("cats_saved", lang))
    cb_edit_profile_menu(call)


def finish_onboarding(chat_id, user_id, lang="es"):
    bot.send_message(chat_id, t("onboard_done", lang))
    ref = get_setting(f"ref_{user_id}")
    if ref:
        try:
            show_profile(chat_id, user_id, int(ref))
            set_setting(f"ref_{user_id}", "")
            return
        except Exception:
            pass
    send_main_menu(chat_id, user_id, lang=lang)


def require_complete_profile(user_id, chat_id=None, lang=None):
    user = get_user(user_id)
    if not user:
        return False
    complete = False
    try:
        complete = int(user["profile_complete"] or 0) == 1 and bool(user["profile_photo_id"])
    except Exception:
        complete = False
    if user["age_declared"] and user["terms_accepted"] and complete:
        return True
    lang = lang or user["language"] or "es"
    if chat_id:
        bot.send_message(chat_id, t("profile_incomplete", lang))
        show_login(chat_id, lang, None)
    return False


# ==================== BUSCADOR ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_search")
def cb_search(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, t("search_prompt", get_lang(call.from_user.id)))
    bot.register_next_step_handler(msg, process_search)

def process_search(message):
    if not is_private_chat(message): return
    lang = get_lang(message.from_user.id)
    q = (message.text or "").strip().lstrip("@").lower()
    if len(q) < 2:
        bot.send_message(message.chat.id, "Mínimo 2 caracteres.")
        return
    conn = get_db()
    results = conn.execute("""SELECT u.user_id, u.username, u.first_name, u.role, u.gender, u.gender_verified,
        u.age_verified_real, u.bio, c.display_name FROM users u
        LEFT JOIN creators c ON u.user_id=c.user_id
        WHERE u.banned=0 AND (LOWER(IFNULL(u.username,'')) LIKE ? OR LOWER(IFNULL(u.first_name,'')) LIKE ?
        OR LOWER(IFNULL(c.display_name,'')) LIKE ?) LIMIT 15""",
        (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    conn.close()
    if not results:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
        bot.send_message(message.chat.id, t("search_empty", lang), reply_markup=kb)
        return
    text = f"🔎 Resultados ({len(results)}):\n\n"
    kb = types.InlineKeyboardMarkup()
    for r in results:
        name = r["display_name"] or r["first_name"] or r["username"] or str(r["user_id"])
        icon = "🎨" if is_creator(r["user_id"]) else "👤"
        text += f"• {icon} {name} {get_badges(r)}\n"
        kb.add(types.InlineKeyboardButton(f"{icon} {name}"[:60], callback_data=f"profile_{r['user_id']}"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("profile_"))
def cb_profile(call):
    show_profile(call.message.chat.id, call.from_user.id, int(call.data.split("_")[1]), call.message.message_id)
    bot.answer_callback_query(call.id)

def show_profile(chat_id, viewer_id, target_id, message_id=None):
    lang = get_lang(viewer_id)
    if is_blocked(viewer_id, target_id):
        bot.send_message(chat_id, t("blocked", lang))
        return
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (target_id,)).fetchone()
    c = conn.execute("SELECT * FROM creators WHERE user_id=?", (target_id,)).fetchone()
    content_count = conn.execute("SELECT COUNT(*) FROM content WHERE creator_id=?", (target_id,)).fetchone()[0]
    free_count = conn.execute(
        "SELECT COUNT(*) FROM content WHERE creator_id=? AND IFNULL(is_free,0)=1", (target_id,)
    ).fetchone()[0]
    plans = conn.execute("SELECT * FROM creator_plans WHERE creator_id=? AND active=1", (target_id,)).fetchall()
    conn.close()
    if not u:
        bot.send_message(chat_id, "No encontrado.")
        return
    display = None
    try:
        display = u["display_name"]
    except (KeyError, IndexError, TypeError):
        display = None
    name = escape_html((c["display_name"] if c else None) or display or u["first_name"] or "Usuario")
    is_cre = is_creator(target_id)
    profile_icon = "🎨" if is_cre else "👤"
    text = f"{profile_icon} <b>{name}</b> {get_badges(u)}\n"
    if u["username"]:
        text += f"@{escape_html(u['username'])}\n"
    text += f"Género: {get_gender_text(u)}\n"
    cats = get_creator_categories(target_id)
    if cats:
        text += " · ".join(f"{row['emoji']} {escape_html(row['name'])}" for row in cats) + "\n"
    bio = (c["bio"] if c and c["bio"] else u["bio"]) or ""
    if bio:
        text += f"\n{escape_html(bio)}\n"
    try:
        loc = u["location"] or ""
    except Exception:
        loc = ""
    if loc:
        text += f"📍 {escape_html(loc)}\n"
    links = []
    try:
        if u["website"]:
            links.append(f"🌐 {escape_html(u['website'])}")
        if u["social_ig"]:
            links.append(f"📸 IG: {escape_html(u['social_ig'])}")
        if u["social_x"]:
            links.append(f"🐦 X: {escape_html(u['social_x'])}")
        if u["social_tiktok"]:
            links.append(f"🎵 TT: {escape_html(u['social_tiktok'])}")
    except Exception:
        pass
    if links:
        text += "\n" + "\n".join(links) + "\n"
    kb = types.InlineKeyboardMarkup()
    if is_cre:
        text += f"\n📸 Contenidos: {content_count} (libres: {free_count}) | 👥 {c['total_subscribers'] if c else 0}\n"
        if plans:
            text += "\n<b>Planes:</b>\n"
            for p in plans:
                text += f"• {escape_html(p['name'])} — {format_price(p['price'])}\n"
                kb.add(types.InlineKeyboardButton(
                    f"💳 {p['name']} {format_price(p['price'])}", callback_data=f"buyplan_{p['id']}"))
        if has_unlimited_access(viewer_id, target_id):
            text += f"\n✅ <b>Plan activo (acceso completo)</b> — ves todas las publicaciones"
            kb.add(types.InlineKeyboardButton("📸 Ver todo el contenido", callback_data=f"viewcontent_{target_id}_0"))
        elif get_pack_credits(viewer_id, target_id) > 0 or _has_any_unlocked(viewer_id, target_id):
            cr = get_pack_credits(viewer_id, target_id)
            text += f"\n📦 <b>Pack activo</b> — créditos: {cr} (solo esas fotos, no el muro entero)"
            kb.add(types.InlineKeyboardButton(f"📦 Abrir pack ({cr} cr)", callback_data=f"viewcontent_{target_id}_0"))
        else:
            text += f"\n{t('locked_preview', lang)}"
            if free_count:
                kb.add(types.InlineKeyboardButton("🆓 Ver muestra gratis", callback_data=f"viewfree_{target_id}_0"))
        vc_plan = next((p for p in plans if p["plan_type"] == "videocall"), None)
        if vc_plan:
            kb.add(types.InlineKeyboardButton(
                f"📞 Videollamada {format_price(vc_plan['price'])}",
                callback_data=f"reqvc_{target_id}_{vc_plan['id']}"))
        fav_label = "★ Quitar favorito" if is_favorite(viewer_id, target_id) else "☆ Favorito"
        kb.add(types.InlineKeyboardButton(fav_label, callback_data=f"togglefav_{target_id}"))
        kb.add(types.InlineKeyboardButton("✉️ Mensaje", callback_data=f"msgcreator_{target_id}"))
        kb.add(
            types.InlineKeyboardButton(t("report", lang), callback_data=f"report_{target_id}"),
            types.InlineKeyboardButton("🚫 Bloquear", callback_data=f"block_{target_id}"),
        )
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    photo_id = None
    try:
        photo_id = u["profile_photo_id"]
    except (KeyError, IndexError, TypeError):
        photo_id = None
    if photo_id:
        try:
            bot.send_photo(chat_id, photo_id, caption=text, reply_markup=kb)
            return
        except Exception:
            pass
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except Exception:
            pass
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
        bot.answer_callback_query(call.id, "No disponible", show_alert=True)
        return
    fee, net = calc_fee(p["price"])
    pay_txt = build_payment_methods_text()
    text = (f"💳 <b>{escape_html(p['name'])}</b>\n\nPrecio: {format_price(p['price'])}\n"
            f"{escape_html(p['description'] or '')}\n\n{pay_txt}")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Ya pagué", callback_data=f"proofplan_{plan_id}"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data=f"profile_{p['creator_id']}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("proofplan_"))
def cb_proof_plan(call):
    plan_id = int(call.data.split("_")[1])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📸 Envía la captura del pago.")
    bot.register_next_step_handler(msg, lambda m: process_plan_proof(m, plan_id))

def process_plan_proof(message, plan_id):
    if not is_private_chat(message) or not message.photo:
        bot.send_message(message.chat.id, "❌ Envía una foto.")
        return
    file_id = message.photo[-1].file_id
    conn = get_db()
    p = conn.execute("SELECT * FROM creator_plans WHERE id=? AND active=1", (plan_id,)).fetchone()
    if not p:
        conn.close()
        return
    fee, net = calc_fee(p["price"])
    cur = conn.cursor()
    cur.execute("""INSERT INTO transactions (user_id, creator_id, type, amount, platform_fee, creator_net,
        status, payment_method, screenshot_file_id, plan_id, created_at)
        VALUES (?,?,?,?,?,?,'pending','manual',?,?,?)""",
                (message.from_user.id, p["creator_id"], f"plan_{p['plan_type']}", p["price"], fee, net,
                 file_id, plan_id, datetime.now().isoformat()))
    tx_id = cur.lastrowid
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Captura recibida. Esperando admin.")
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_tx_{tx_id}"),
           types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_tx_{tx_id}"))
    bot.send_photo(ADMIN_ID, file_id,
        caption=(f"💳 PLAN\nUser: {message.from_user.id}\nCreator: {p['creator_id']}\n"
                 f"{p['name']} {format_price(p['price'])}\n"
                 f"Comisión plataforma ({get_platform_fee_percent()}%): {format_price(fee)}\n"
                 f"Neto creador: {format_price(net)}\nTX #{tx_id}"),
        reply_markup=kb)

# ==================== VIDEOLLAMADAS ====================
@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("reqvc_"))
def cb_req_videocall(call):
    parts = call.data.split("_")
    creator_id, plan_id = int(parts[1]), int(parts[2])
    conn = get_db()
    p = conn.execute("SELECT * FROM creator_plans WHERE id=? AND creator_id=? AND active=1",
                      (plan_id, creator_id)).fetchone()
    conn.close()
    if not p or p["plan_type"] != "videocall":
        bot.answer_callback_query(call.id, "No disponible", show_alert=True)
        return
    text = (f"📞 <b>Solicitar videollamada</b>\n\nPrecio: {format_price(p['price'])}\n\n"
            f"{get_setting('payment_methods')}\n\nEnvía captura tras pagar.")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Ya pagué", callback_data=f"proofvc_{creator_id}_{plan_id}"))
    kb.add(types.InlineKeyboardButton("« Volver", callback_data=f"profile_{creator_id}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("proofvc_"))
def cb_proof_vc(call):
    parts = call.data.split("_")
    creator_id, plan_id = int(parts[1]), int(parts[2])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📸 Envía captura del pago de la videollamada.")
    bot.register_next_step_handler(msg, lambda m: process_vc_proof(m, creator_id, plan_id))

def process_vc_proof(message, creator_id, plan_id):
    if not is_private_chat(message) or not message.photo:
        bot.send_message(message.chat.id, "❌ Envía una foto.")
        return
    file_id = message.photo[-1].file_id
    conn = get_db()
    p = conn.execute("SELECT * FROM creator_plans WHERE id=? AND creator_id=? AND active=1",
                      (plan_id, creator_id)).fetchone()
    if not p or p["plan_type"] != "videocall":
        conn.close()
        bot.send_message(message.chat.id, "❌ El plan de videollamada ya no está disponible.")
        return
    fee, net = calc_fee(p["price"])
    cur = conn.cursor()
    cur.execute("""INSERT INTO transactions (user_id, creator_id, type, amount, platform_fee, creator_net,
        status, payment_method, screenshot_file_id, plan_id, created_at)
        VALUES (?,?, 'videocall',?,?,?,'pending','manual',?,?,?)""",
                (message.from_user.id, creator_id, p["price"], fee, net, file_id, plan_id, datetime.now().isoformat()))
    tx_id = cur.lastrowid
    cur.execute("""INSERT INTO videocalls (user_id, creator_id, amount, status, requested_at, transaction_id)
        VALUES (?,?,?,'pending_payment',?,?)""",
                (message.from_user.id, creator_id, p["price"], datetime.now().isoformat(), tx_id))
    vc_id = cur.lastrowid
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Solicitud enviada. Esperando aprobación del pago.")
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("✅ Aprobar pago VC", callback_data=f"approve_tx_{tx_id}"),
           types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_tx_{tx_id}"))
    bot.send_photo(ADMIN_ID, file_id,
        caption=f"📞 VIDEOLLAMADA\nUser: {message.from_user.id}\nCreator: {creator_id}\n"
                f"{format_price(p['price'])} | Comisión: {format_price(fee)} | Neto: {format_price(net)}\n"
                f"TX #{tx_id} | VC #{vc_id}",
        reply_markup=kb)

# ==================== VER CONTENIDO ====================
@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("viewcontent_"))
def cb_view_content(call):
    """Feed del creador: mensual = todo el perfil; pack = solo posts desbloqueados / desbloquear con créditos."""
    parts = call.data.split("_")
    creator_id = int(parts[1])
    offset = int(parts[2]) if len(parts) > 2 else 0
    lang = get_lang(call.from_user.id)
    uid = call.from_user.id
    unlimited = has_unlimited_access(uid, creator_id)
    credits = get_pack_credits(uid, creator_id)
    if not unlimited and credits <= 0 and not _has_any_unlocked(uid, creator_id):
        bot.answer_callback_query(call.id, t("must_pay", lang), show_alert=True)
        return

    conn = get_db()
    total = conn.execute(
        "SELECT COUNT(*) FROM content WHERE creator_id=? AND IFNULL(is_free,0)=0", (creator_id,)
    ).fetchone()[0]
    # Feed: latest posts
    items = conn.execute(
        """SELECT * FROM content WHERE creator_id=? AND IFNULL(is_free,0)=0
           ORDER BY id DESC LIMIT 5 OFFSET ?""",
        (creator_id, offset),
    ).fetchall()
    cre = conn.execute("SELECT display_name FROM creators WHERE user_id=?", (creator_id,)).fetchone()
    conn.close()

    cname = escape_html((cre["display_name"] if cre else None) or "Creador")
    if unlimited:
        mode = "🔓 <b>Suscripción activa</b> — acceso completo al perfil"
    else:
        mode = f"📦 <b>Pack</b> — créditos restantes: <b>{credits}</b> (solo desbloqueas fotos, no todo el muro)"

    if not items:
        bot.answer_callback_query(call.id, t("no_content", lang), show_alert=True)
        return

    text = f"📸 <b>Feed de {cname}</b>\n{mode}\n\n"
    kb = types.InlineKeyboardMarkup()
    for item in items:
        unlocked = unlimited or is_content_unlocked(uid, item["id"])
        title = escape_html(item["title"] or f"Post #{item['id']}")
        media = "🎬" if item["media_type"] == "video" else "🖼"
        if unlocked:
            text += f"{media} ✅ {title} — ❤️ {item['likes']}\n"
            kb.add(types.InlineKeyboardButton(
                f"{media} Ver {title[:28]}", callback_data=f"openpost_{item['id']}"
            ))
        else:
            text += f"{media} 🔒 {title} — desbloquear (1 crédito)\n"
            kb.add(types.InlineKeyboardButton(
                f"🔓 Desbloquear {title[:24]} (1 cr)", callback_data=f"unlockpost_{item['id']}"
            ))

    nav = []
    if offset > 0:
        nav.append(types.InlineKeyboardButton("◀ Anteriores", callback_data=f"viewcontent_{creator_id}_{max(0, offset-5)}"))
    if offset + 5 < total:
        nav.append(types.InlineKeyboardButton("Siguientes ▶", callback_data=f"viewcontent_{creator_id}_{offset+5}"))
    if nav:
        kb.row(*nav)
    kb.add(types.InlineKeyboardButton("👤 Perfil", callback_data=f"profile_{creator_id}"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=kb)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("unlockpost_"))
def cb_unlock_post(call):
    lang = get_lang(call.from_user.id)
    content_id = int(call.data.split("_")[1])
    conn = get_db()
    item = conn.execute("SELECT * FROM content WHERE id=?", (content_id,)).fetchone()
    conn.close()
    if not item:
        bot.answer_callback_query(call.id, "No existe", show_alert=True)
        return
    ok, reason = unlock_content_with_credit(call.from_user.id, content_id, item["creator_id"])
    if not ok:
        bot.answer_callback_query(call.id, "Sin créditos de pack. Compra un pack o un plan mensual.", show_alert=True)
        return
    bot.answer_callback_query(call.id, "Desbloqueado ✅")
    # Show the media
    _send_post_media(call.message.chat.id, call.from_user.id, item, lang)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("openpost_"))
def cb_open_post(call):
    lang = get_lang(call.from_user.id)
    content_id = int(call.data.split("_")[1])
    conn = get_db()
    item = conn.execute("SELECT * FROM content WHERE id=?", (content_id,)).fetchone()
    conn.close()
    if not item:
        bot.answer_callback_query(call.id, "No existe", show_alert=True)
        return
    if not is_content_unlocked(call.from_user.id, content_id) and not has_unlimited_access(call.from_user.id, item["creator_id"]):
        bot.answer_callback_query(call.id, "Bloqueado", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    _send_post_media(call.message.chat.id, call.from_user.id, item, lang)


def _send_post_media(chat_id, user_id, item, lang="es"):
    conn = get_db()
    conn.execute("UPDATE content SET views=views+1 WHERE id=?", (item["id"],))
    conn.commit()
    conn.close()
    caption = (
        f"📸 {escape_html(item['title'] or 'Contenido')}\\n"
        f"{escape_html(item['description'] or '')}\\n\\n"
        f"❤️ {item['likes']} · 💔 {item['dislikes']} · 👁 {item['views']+1}\\n"
        f"<i>🔒 protect_content — no reenviar / guardar</i>"
    )
    try:
        if item["media_type"] == "video":
            bot.send_video(chat_id, item["file_id"], caption=caption, protect_content=True)
        else:
            bot.send_photo(chat_id, item["file_id"], caption=caption, protect_content=True)
    except Exception:
        bot.send_message(chat_id, "Error al cargar el medio.")
        return
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.row(
        types.InlineKeyboardButton(f"❤️ {item['likes']}", callback_data=f"like_{item['id']}"),
        types.InlineKeyboardButton(f"💔 {item['dislikes']}", callback_data=f"dislike_{item['id']}"),
        types.InlineKeyboardButton("💬", callback_data=f"comment_{item['id']}"),
    )
    kb.add(types.InlineKeyboardButton("📸 Volver al feed", callback_data=f"viewcontent_{item['creator_id']}_0"))
    bot.send_message(chat_id, "Reacciones:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("like_"))
def cb_like(call):
    cid, uid = int(call.data.split("_")[1]), call.from_user.id
    conn = get_db()
    prev = conn.execute("SELECT reaction FROM reactions WHERE user_id=? AND content_id=?", (uid, cid)).fetchone()
    if prev and prev["reaction"] == "like":
        bot.answer_callback_query(call.id, "Ya diste like")
        conn.close()
        return
    if prev and prev["reaction"] == "dislike":
        conn.execute("UPDATE content SET dislikes=dislikes-1, likes=likes+1 WHERE id=?", (cid,))
        conn.execute("UPDATE reactions SET reaction='like' WHERE user_id=? AND content_id=?", (uid, cid))
    else:
        conn.execute("UPDATE content SET likes=likes+1 WHERE id=?", (cid,))
        conn.execute("INSERT OR REPLACE INTO reactions (user_id, content_id, reaction) VALUES (?,?,'like')", (uid, cid))
    conn.commit()
    row = conn.execute("SELECT likes, dislikes FROM content WHERE id=?", (cid,)).fetchone()
    conn.close()
    bot.answer_callback_query(call.id, f"❤️ {row['likes']} 💔 {row['dislikes']}")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("dislike_"))
def cb_dislike(call):
    cid, uid = int(call.data.split("_")[1]), call.from_user.id
    conn = get_db()
    prev = conn.execute("SELECT reaction FROM reactions WHERE user_id=? AND content_id=?", (uid, cid)).fetchone()
    if prev and prev["reaction"] == "dislike":
        bot.answer_callback_query(call.id, "Ya diste dislike")
        conn.close()
        return
    if prev and prev["reaction"] == "like":
        conn.execute("UPDATE content SET likes=likes-1, dislikes=dislikes+1 WHERE id=?", (cid,))
        conn.execute("UPDATE reactions SET reaction='dislike' WHERE user_id=? AND content_id=?", (uid, cid))
    else:
        conn.execute("UPDATE content SET dislikes=dislikes+1 WHERE id=?", (cid,))
        conn.execute("INSERT OR REPLACE INTO reactions (user_id, content_id, reaction) VALUES (?,?,'dislike')", (uid, cid))
    conn.commit()
    row = conn.execute("SELECT likes, dislikes FROM content WHERE id=?", (cid,)).fetchone()
    conn.close()
    bot.answer_callback_query(call.id, f"❤️ {row['likes']} 💔 {row['dislikes']}")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("comment_"))
def cb_comment(call):
    cid = int(call.data.split("_")[1])
    conn = get_db()
    item = conn.execute("SELECT creator_id FROM content WHERE id=?", (cid,)).fetchone()
    conn.close()
    if not item or not has_access(call.from_user.id, item["creator_id"]):
        bot.answer_callback_query(call.id, "Necesitas acceso para comentar", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "💬 Escribe tu comentario:")
    bot.register_next_step_handler(msg, lambda m: save_comment(m, cid))

def save_comment(message, content_id):
    if not is_private_chat(message) or not message.text: return
    text = message.text[:300]
    conn = get_db()
    item = conn.execute("SELECT creator_id, title FROM content WHERE id=?", (content_id,)).fetchone()
    if not item or not has_access(message.from_user.id, item["creator_id"]):
        conn.close()
        bot.send_message(message.chat.id, "Necesitas acceso activo para comentar este contenido.")
        return
    conn.execute("INSERT INTO comments (content_id, user_id, text, created_at) VALUES (?,?,?,?)",
                 (content_id, message.from_user.id, text, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Comentario publicado.")
    if item:
        try:
            bot.send_message(item["creator_id"], f"💬 Comentario en «{escape_html(item['title'] or 'contenido')}»\nDe: {escape_html(message.from_user.first_name)}\n{escape_html(text)}")
        except: pass

# ==================== EXPLORAR ====================
def _list_creators_page(page=0, page_size=8, exclude_viewer=None):
    conn = get_db()
    total = conn.execute("""SELECT COUNT(*) FROM creators c JOIN users u ON c.user_id=u.user_id
        WHERE u.creator_verified=2 AND u.banned=0""").fetchone()[0]
    offset = page * page_size
    creators = conn.execute("""SELECT c.*, u.first_name, u.username, u.gender, u.gender_verified, u.age_verified_real, u.user_id
        FROM creators c JOIN users u ON c.user_id=u.user_id
        WHERE u.creator_verified=2 AND u.banned=0
        ORDER BY c.total_subscribers DESC LIMIT ? OFFSET ?""", (page_size, offset)).fetchall()
    conn.close()
    if exclude_viewer:
        creators = [c for c in creators if not is_blocked(exclude_viewer, c["user_id"])]
    return creators, total

@bot.callback_query_handler(func=lambda c: c.data == "menu_explore" or (c.data and c.data.startswith("explore_page_")))
def cb_explore(call):
    lang = get_lang(call.from_user.id)
    page = 0
    if call.data.startswith("explore_page_"):
        try:
            page = max(0, int(call.data.split("_")[-1]))
        except ValueError:
            page = 0
    page_size = 8
    creators, total = _list_creators_page(page, page_size, exclude_viewer=call.from_user.id)
    if not creators and page == 0:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
        bot.edit_message_text(t("no_creators", lang), call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    pages = max(1, (total + page_size - 1) // page_size)
    text = f"🔍 <b>Creadores</b> (pág. {page+1}/{pages})\n\n"
    kb = types.InlineKeyboardMarkup()
    for c in creators:
        name = c["display_name"] or c["first_name"]
        urow = get_user(c["user_id"])
        badges = get_badges(urow) if urow else ""
        text += f"• {escape_html(name)} {badges}\n"
        kb.add(types.InlineKeyboardButton(f"{name}", callback_data=f"profile_{c['user_id']}"))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("« Ant", callback_data=f"explore_page_{page-1}"))
    if page + 1 < pages:
        nav.append(types.InlineKeyboardButton("Sig »", callback_data=f"explore_page_{page+1}"))
    if nav:
        kb.row(*nav)
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
    pending_vc = conn.execute("SELECT COUNT(*) FROM videocalls WHERE creator_id=? AND status='requested'", (call.from_user.id,)).fetchone()[0]
    conn.close()
    fee_pct = get_platform_fee_percent()
    text = (f"🎨 <b>Panel Creador</b>\n\n"
            f"Suscriptores: {c['total_subscribers']}\n"
            f"Ganancias netas: {format_price(c['total_earnings'])}\n"
            f"Contenidos: {count} | Planes: {plans}\n"
            f"VC pendientes: {pending_vc}\n\n"
            f"⚠️ La plataforma retiene {fee_pct}% de cada pago.")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Subir contenido", callback_data="upload_content"))
    kb.add(types.InlineKeyboardButton("📋 Mis contenidos", callback_data="my_contents"))
    kb.add(types.InlineKeyboardButton("💰 Gestionar planes / precios", callback_data="manage_plans"))
    kb.add(types.InlineKeyboardButton("📞 Videollamadas", callback_data="creator_vcs"))
    kb.add(types.InlineKeyboardButton("✏️ Editar bio", callback_data="edit_creator_profile"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "upload_content")
def cb_upload(call):
    if not is_creator(call.from_user.id): return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📸 Envía foto o vídeo (se protegerá automáticamente):")
    bot.register_next_step_handler(msg, process_upload_media)

def process_upload_media(message):
    if not is_private_chat(message) or not is_creator(message.from_user.id): return
    file_id, media_type = None, "photo"
    if message.photo: file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
    else:
        bot.send_message(message.chat.id, "❌ Envía foto o vídeo.")
        return
    prompt = bot.send_message(message.chat.id, "Título (o /skip):")
    bot.register_next_step_handler(prompt, lambda m: save_content(m, file_id, media_type))

def save_content(message, file_id, media_type):
    if not is_private_chat(message) or not is_creator(message.from_user.id):
        return
    title = None if message.text == "/skip" else (message.text or "")[:100]
    prompt = bot.send_message(message.chat.id, "Descripción (o /skip):")
    bot.register_next_step_handler(prompt, lambda m: persist_content(m, file_id, media_type, title))

def persist_content(message, file_id, media_type, title):
    if not is_private_chat(message) or not is_creator(message.from_user.id):
        return
    description = None if message.text == "/skip" else (message.text or "")[:500]
    conn = get_db()
    conn.execute("INSERT INTO content (creator_id, title, description, file_id, media_type, is_premium, created_at) VALUES (?,?,?,?,?,1,?)",
                 (message.from_user.id, title, description, file_id, media_type, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ Publicado ({media_type}). 🔒 Protegido.")

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
    kb = types.InlineKeyboardMarkup()
    for i in items:
        text += f"#{i['id']} [{i['media_type']}] {i['title'] or '-'} — 👁{i['views']} ❤️{i['likes']}\n"
        kb.add(types.InlineKeyboardButton(f"🗑 Borrar #{i['id']}", callback_data=f"delcontent_{i['id']}"))
    kb.add(types.InlineKeyboardButton("« Panel", callback_data="creator_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("delcontent_"))
def cb_del_content(call):
    if not is_creator(call.from_user.id): return
    cid = int(call.data.split("_")[1])
    conn = get_db()
    item = conn.execute("SELECT * FROM content WHERE id=? AND creator_id=?", (cid, call.from_user.id)).fetchone()
    if not item:
        bot.answer_callback_query(call.id, "No encontrado", show_alert=True)
        conn.close()
        return
    conn.execute("DELETE FROM content WHERE id=?", (cid,))
    conn.execute("DELETE FROM reactions WHERE content_id=?", (cid,))
    conn.execute("DELETE FROM comments WHERE content_id=?", (cid,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, f"Contenido #{cid} borrado")
    call.data = "my_contents"
    cb_my_contents(call)

# --- Gestionar planes y EDITAR PRECIOS ---
@bot.callback_query_handler(func=lambda c: c.data == "manage_plans")
def cb_manage_plans(call):
    if not is_creator(call.from_user.id): return
    conn = get_db()
    plans = conn.execute("SELECT * FROM creator_plans WHERE creator_id=?", (call.from_user.id,)).fetchall()
    conn.close()
    text = "💰 <b>Tus planes</b> (toca para editar precio)\n\n"
    kb = types.InlineKeyboardMarkup()
    for p in plans:
        status = "✅" if p["active"] else "❌"
        text += f"{status} {escape_html(p['name'])} — {format_price(p['price'])}\n"
        kb.add(types.InlineKeyboardButton(f"✏️ {p['name']} {format_price(p['price'])}", callback_data=f"editprice_{p['id']}"))
    kb.add(types.InlineKeyboardButton("➕ Añadir plan", callback_data="add_plan"))
    kb.add(types.InlineKeyboardButton("« Panel", callback_data="creator_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("editprice_"))
def cb_edit_price(call):
    if not is_creator(call.from_user.id): return
    plan_id = int(call.data.split("_")[1])
    conn = get_db()
    p = conn.execute("SELECT * FROM creator_plans WHERE id=? AND creator_id=?", (plan_id, call.from_user.id)).fetchone()
    conn.close()
    if not p:
        bot.answer_callback_query(call.id, "No encontrado", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        f"Precio actual de <b>{escape_html(p['name'])}</b>: {format_price(p['price'])}\n\n"
        f"Escribe el <b>nuevo precio</b> (ej: 15.99):")
    bot.register_next_step_handler(msg, lambda m: save_new_price(m, plan_id))

def save_new_price(message, plan_id):
    if not is_creator(message.from_user.id): return
    try:
        price = validate_plan_price(message.text.replace(",", ".").strip())
    except (AttributeError, TypeError, ValueError) as exc:
        bot.send_message(message.chat.id, f"❌ {escape_html(exc)}. Ejemplo: 9.99")
        return
    conn = get_db()
    conn.execute("UPDATE creator_plans SET price=? WHERE id=? AND creator_id=?",
                 (price, plan_id, message.from_user.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ Precio actualizado a {format_price(price)}.")

@bot.callback_query_handler(func=lambda c: c.data == "add_plan")
def cb_add_plan(call):
    if not is_creator(call.from_user.id): return
    kb = types.InlineKeyboardMarkup()
    for ptype, info in PLAN_TYPES.items():
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
    conn.execute("INSERT INTO creator_plans (creator_id, plan_type, name, price, days, credits, description) VALUES (?,?,?,?,?,?,?)",
                 (call.from_user.id, ptype, info["name"], info["default_price"], info["days"], info["credits"], info["name"]))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, f"Añadido: {info['name']}")
    call.data = "manage_plans"
    cb_manage_plans(call)

@bot.callback_query_handler(func=lambda c: c.data == "edit_creator_profile")
def cb_edit_creator(call):
    if not is_creator(call.from_user.id): return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Nueva bio (máx 200):")
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

@bot.callback_query_handler(func=lambda c: c.data == "creator_vcs")
def cb_creator_vcs(call):
    if not is_creator(call.from_user.id): return
    conn = get_db()
    vcs = conn.execute("""SELECT v.*, u.first_name FROM videocalls v
        JOIN users u ON v.user_id=u.user_id
        WHERE v.creator_id=? ORDER BY v.id DESC LIMIT 15""", (call.from_user.id,)).fetchall()
    conn.close()
    text = "📞 <b>Videollamadas</b>\n\n"
    kb = types.InlineKeyboardMarkup()
    if not vcs:
        text += "Ninguna aún."
    for v in vcs:
        text += f"#{v['id']} {escape_html(v['first_name'])} — {v['status']} — {format_price(v['amount'])}\n"
        if v["status"] == "requested":
            kb.add(types.InlineKeyboardButton(f"✅ Aceptar #{v['id']}", callback_data=f"vcaccept_{v['id']}"))
            kb.add(types.InlineKeyboardButton(f"❌ Rechazar #{v['id']}", callback_data=f"vcreject_{v['id']}"))
        elif v["status"] == "accepted":
            kb.add(types.InlineKeyboardButton(f"✅ Completar #{v['id']}", callback_data=f"vccomplete_{v['id']}"))
    kb.add(types.InlineKeyboardButton("« Panel", callback_data="creator_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("vcaccept_"))
def cb_vc_accept(call):
    if not is_creator(call.from_user.id): return
    vc_id = int(call.data.split("_")[1])
    conn = get_db()
    vc = conn.execute("SELECT * FROM videocalls WHERE id=? AND creator_id=?", (vc_id, call.from_user.id)).fetchone()
    if not vc or vc["status"] != "requested":
        bot.answer_callback_query(call.id, "No disponible", show_alert=True)
        conn.close()
        return
    changed = conn.execute("UPDATE videocalls SET status='accepted' WHERE id=? AND creator_id=? AND status='requested'",
                           (vc_id, call.from_user.id))
    if changed.rowcount != 1:
        conn.close()
        bot.answer_callback_query(call.id, "Ya procesada", show_alert=True)
        return
    conn.commit()
    conn.close()
    bot.send_message(vc["user_id"], f"✅ El creador aceptó tu videollamada #{vc_id}.\nCoordina por mensaje privado.")
    bot.answer_callback_query(call.id, "Aceptada")
    call.data = "creator_vcs"
    cb_creator_vcs(call)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("vcreject_"))
def cb_vc_reject(call):
    if not is_creator(call.from_user.id): return
    vc_id = int(call.data.split("_")[1])
    conn = get_db()
    vc = conn.execute("SELECT * FROM videocalls WHERE id=? AND creator_id=?", (vc_id, call.from_user.id)).fetchone()
    if not vc or vc["status"] not in ("requested", "accepted"):
        conn.close()
        bot.answer_callback_query(call.id, "No disponible", show_alert=True)
        return
    conn.execute("UPDATE videocalls SET status='rejected' WHERE id=? AND creator_id=? AND status IN ('requested','accepted')",
                 (vc_id, call.from_user.id))
    conn.commit()
    conn.close()
    bot.send_message(vc["user_id"], f"❌ Videollamada #{vc_id} rechazada.")
    bot.answer_callback_query(call.id, "Rechazada")
    call.data = "creator_vcs"
    cb_creator_vcs(call)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("vccomplete_"))
def cb_vc_complete(call):
    if not is_creator(call.from_user.id): return
    vc_id = int(call.data.split("_")[1])
    conn = get_db()
    changed = conn.execute("UPDATE videocalls SET status='completed', completed_at=? WHERE id=? AND creator_id=? AND status='accepted'",
                           (datetime.now().isoformat(), vc_id, call.from_user.id))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "Marcada como completada" if changed.rowcount == 1 else "No disponible")
    call.data = "creator_vcs"
    cb_creator_vcs(call)

# ==================== APROBAR PAGOS (CON COMISIÓN) ====================
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
    fee = tx["platform_fee"] if tx["platform_fee"] is not None else 0
    net = tx["creator_net"] if tx["creator_net"] is not None else tx["amount"]
    claimed = conn.execute("UPDATE transactions SET status='approved', reviewed_at=? WHERE id=? AND status='pending'",
                           (now.isoformat(), tx_id))
    if claimed.rowcount != 1:
        conn.close()
        bot.answer_callback_query(call.id, "Ya procesado", show_alert=True)
        return

    if tx["type"] == "creator_fee":
        conn.execute("UPDATE users SET role='creator', creator_verified=2 WHERE user_id=?", (tx["user_id"],))
        conn.execute("INSERT OR IGNORE INTO creators (user_id, display_name, bio, created_at) VALUES (?,?,?,?)",
                     (tx["user_id"], f"Creator {tx['user_id']}", "Nuevo creador", now.isoformat()))
        for ptype, info in PLAN_TYPES.items():
            conn.execute("INSERT INTO creator_plans (creator_id, plan_type, name, price, days, credits, description) VALUES (?,?,?,?,?,?,?)",
                         (tx["user_id"], ptype, info["name"], info["default_price"], info["days"], info["credits"], info["name"]))
        conn.commit()
        conn.close()
        bot.send_message(tx["user_id"], "✅ ¡Eres Creador! Sube contenido y configura precios.")
        bot.answer_callback_query(call.id, "Creador aprobado")
        return

    # Plan o videollamada
    plan = conn.execute("SELECT * FROM creator_plans WHERE id=?", (tx["plan_id"],)).fetchone() if tx["plan_id"] else None
    if tx["plan_id"] and (not plan or plan["creator_id"] != tx["creator_id"]):
        conn.rollback()
        conn.close()
        bot.answer_callback_query(call.id, "El plan asociado no es válido", show_alert=True)
        return
    legacy_reference = tx["reference"] if "reference" in tx.keys() else None
    legacy_plan_type = legacy_reference if legacy_reference in ("monthly", "quarterly") else None
    days = plan["days"] if plan else (90 if legacy_plan_type == "quarterly" else 30)
    credits = plan["credits"] if plan else 0
    granted_plan_type = plan["plan_type"] if plan else (legacy_plan_type or tx["type"])
    end = (now + timedelta(days=days)).isoformat() if days > 0 else now.isoformat()

    if tx["type"] == "videocall" or (plan and plan["plan_type"] == "videocall"):
        updated = conn.execute("UPDATE videocalls SET status='requested' WHERE transaction_id=? AND status='pending_payment'",
                               (tx_id,))
        if updated.rowcount != 1:
            conn.rollback()
            conn.close()
            bot.answer_callback_query(call.id, "No existe la videollamada vinculada", show_alert=True)
            return
        # Notificar al creador
        try:
            bot.send_message(tx["creator_id"],
                f"📞 Nueva solicitud de videollamada\nDe: {tx['user_id']}\nMonto: {format_price(tx['amount'])}\n"
                f"Ve a Panel Creador → Videollamadas para aceptar.")
        except: pass
    else:
        if tx["type"] not in ("subscription", "monthly", "quarterly") and not tx["type"].startswith("plan_"):
            conn.rollback()
            conn.close()
            bot.answer_callback_query(call.id, "Tipo de pago no válido", show_alert=True)
            return
        conn.execute("""INSERT INTO subscriptions
            (user_id, creator_id, plan_id, plan_type, amount, status, start_date, end_date, credits_left, payment_method, created_at)
            VALUES (?,?,?,?,?,'active',?,?,?,?,?)""",
                     (tx["user_id"], tx["creator_id"], tx["plan_id"], granted_plan_type, tx["amount"],
                      now.isoformat(), end, credits, "manual", now.isoformat()))

    if tx["type"] != "videocall" and not (plan and plan["plan_type"] == "videocall"):
        conn.execute("UPDATE creators SET total_subscribers=total_subscribers+1, total_earnings=total_earnings+? WHERE user_id=?",
                     (net, tx["creator_id"]))
    else:
        conn.execute("UPDATE creators SET total_earnings=total_earnings+? WHERE user_id=?",
                     (net, tx["creator_id"]))
    conn.commit()
    conn.close()

    extra = f"Créditos: {credits}" if credits else (f"Hasta: {end[:10]}" if days else "Videollamada solicitada")
    bot.send_message(tx["user_id"], f"✅ <b>Pago aprobado</b>\n{extra}")
    # Aviso al admin de su comisión
    bot.send_message(ADMIN_ID, f"💰 Comisión plataforma: {format_price(fee)} (de TX #{tx_id})")
    bot.answer_callback_query(call.id, f"Aprobado | Tu comisión: {format_price(fee)}")

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
    changed = conn.execute("UPDATE transactions SET status='rejected', reviewed_at=? WHERE id=? AND status='pending'",
                           (datetime.now().isoformat(), tx_id))
    if changed.rowcount != 1:
        conn.close()
        bot.answer_callback_query(call.id, "Ya procesado", show_alert=True)
        return
    if tx["type"] == "creator_fee":
        conn.execute("UPDATE users SET creator_verified=0 WHERE user_id=?", (tx["user_id"],))
    conn.commit()
    conn.close()
    bot.send_message(tx["user_id"], "❌ Pago rechazado.")
    bot.answer_callback_query(call.id, "Rechazado")

# ==================== CUENTA / ADMIN ====================
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
    if not user or is_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "Usa /start para continuar", show_alert=True)
        return
    dname = escape_html(user["display_name"] or user["first_name"] or "Usuario")
    text = (f"👤 <b>Mi perfil</b> {get_badges(user)}\n\n"
            f"Nombre: <b>{dname}</b>\n"
            f"ID: <code>{call.from_user.id}</code>\nRol: {user['role'] if user else 'user'}\n"
            f"VIP: {'Sí' if is_vip(call.from_user.id) else 'No'}\n"
            f"Género: {get_gender_text(user)}\n")
    if user["bio"]:
        text += f"\n📄 {escape_html(user['bio'][:200])}\n"
    try:
        if user["location"]:
            text += f"📍 {escape_html(user['location'])}\n"
        if user["website"]:
            text += f"🌐 {escape_html(user['website'])}\n"
        if user["social_ig"]:
            text += f"📸 IG: {escape_html(user['social_ig'])}\n"
        if user["social_x"]:
            text += f"🐦 X: {escape_html(user['social_x'])}\n"
        if user["social_tiktok"]:
            text += f"🎵 TT: {escape_html(user['social_tiktok'])}\n"
    except Exception:
        pass
    if user["profile_photo_id"]:
        text += "📷 Foto de perfil: sí\n"
    else:
        text += "📷 Foto de perfil: falta\n"

    kb = types.InlineKeyboardMarkup()
    if not (user and user["age_verified_real"] == 2):
        kb.add(types.InlineKeyboardButton(t("request_verif", lang), callback_data="request_real_verification"))
        kb.add(types.InlineKeyboardButton("Enviar fotos manualmente", callback_data="manual_verification"))
    if user and user["creator_verified"] != 2:
        kb.add(types.InlineKeyboardButton("🎨 Ser Creador ($50)", callback_data="become_creator"))
    kb.add(types.InlineKeyboardButton(t("edit_profile", lang), callback_data="edit_profile_menu"))
    kb.add(types.InlineKeyboardButton("Ver perfil público", callback_data=f"profile_{call.from_user.id}"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "request_real_verification")
def cb_request_verification(call):
    user = get_user(call.from_user.id)
    if (not is_private_chat(call.message) or not user or is_banned(call.from_user.id)
            or not user["age_declared"] or not user["terms_accepted"]):
        bot.answer_callback_query(call.id, "Completa primero /start y acepta los términos", show_alert=True)
        return
    if user["age_verified_real"] == 2:
        bot.answer_callback_query(call.id, "Ya estás verificado", show_alert=True)
        return
    if user["age_verified_real"] == 1:
        bot.answer_callback_query(call.id, "Ya tienes una verificación pendiente", show_alert=True)
        return
    if not WEBAPP_VERIFICATION_URL:
        bot.answer_callback_query(call.id, "Mini App no configurada; usa el envío manual", show_alert=True)
        return
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(types.KeyboardButton(
        "Abrir Mini App de verificación",
        web_app=types.WebAppInfo(url=WEBAPP_VERIFICATION_URL),
    ))
    bot.send_message(call.message.chat.id,
        "Pulsa el botón para abrir la cámara. La Mini App no sube las fotos; después tendrás que adjuntarlas aquí.",
        reply_markup=keyboard)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "manual_verification")
def cb_manual_verification(call):
    user = get_user(call.from_user.id)
    if (not is_private_chat(call.message) or not user or is_banned(call.from_user.id)
            or not user["age_declared"] or not user["terms_accepted"]):
        bot.answer_callback_query(call.id, "Completa primero /start y acepta los términos", show_alert=True)
        return
    if user["age_verified_real"] == 2:
        bot.answer_callback_query(call.id, "Ya estás verificado", show_alert=True)
        return
    conn = get_db()
    pending = conn.execute("SELECT 1 FROM verifications WHERE user_id=? AND status='pending' LIMIT 1",
                           (call.from_user.id,)).fetchone()
    if pending:
        conn.close()
        bot.answer_callback_query(call.id, "Ya hay una solicitud pendiente", show_alert=True)
        return
    conn.execute("INSERT INTO verifications (user_id,status,source,created_at) VALUES (?,'pending','manual',?)",
                 (call.from_user.id, datetime.now().isoformat()))
    conn.execute("UPDATE users SET age_verified_real=1 WHERE user_id=?", (call.from_user.id,))
    conn.commit()
    conn.close()
    bot.send_message(call.message.chat.id,
        "Envía primero una foto del documento y después una selfie sosteniéndolo. "
        "Las fotos se enviarán al administrador para revisión.",
        reply_markup=types.ReplyKeyboardRemove())
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
    text = "Sin planes activos." if not subs else "📋 <b>Mis planes</b>\n\n"
    kb = types.InlineKeyboardMarkup()
    for s in (subs or []):
        ptype = (s["plan_type"] or "") if "plan_type" in s.keys() else ""
        if ptype.startswith("pack") or ptype in ("pack3", "pack10"):
            extra = f"📦 Pack — {s['credits_left'] or 0} fotos restantes"
            btn = f"📦 Pack {s['display_name']}"
        elif ptype in ("monthly", "quarterly"):
            extra = f"🔓 {'Mensual' if ptype=='monthly' else 'Trimestral'} hasta {(s['end_date'] or '')[:10]}"
            btn = f"🔓 Feed {s['display_name']}"
        else:
            extra = f"hasta {(s['end_date'] or '')[:10]}" if s["end_date"] else f"{s['credits_left'] or 0} cr"
            btn = f"Ver {s['display_name']}"
        text += f"• <b>{escape_html(s['display_name'])}</b> — {extra}\n"
        kb.add(types.InlineKeyboardButton(btn[:60], callback_data=f"viewcontent_{s['creator_id']}_0"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "become_creator")
def cb_become_creator(call):
    lang = get_lang(call.from_user.id)
    text = f"🎨 Ser Creador — {format_price(CREATOR_FEE)}\n\nPublica, pon precios, videollamadas.\nComisión plataforma: {get_platform_fee_percent()}%\n\n{t('payment_test_mode', lang)}\n\n{get_setting('payment_methods')}"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💸 Ya pagué", callback_data="pay_creator_fee"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="menu_account"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "pay_creator_fee")
def cb_pay_creator_fee(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"📸 Captura del pago de ${CREATOR_FEE}:")
    bot.register_next_step_handler(msg, process_creator_fee)

def process_creator_fee(message):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Envía foto.")
        return
    file_id = message.photo[-1].file_id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO transactions (user_id, type, amount, platform_fee, creator_net, status, payment_method, screenshot_file_id, created_at)
        VALUES (?,'creator_fee',?,0,0,'pending','manual',?,?)""",
                (message.from_user.id, CREATOR_FEE, file_id, datetime.now().isoformat()))
    tx_id = cur.lastrowid
    conn.execute("UPDATE users SET creator_verified=1 WHERE user_id=?", (message.from_user.id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Recibido.")
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_tx_{tx_id}"),
           types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_tx_{tx_id}"))
    bot.send_photo(ADMIN_ID, file_id, caption=f"🎨 CREATOR FEE\nUser: {message.from_user.id}\nTX #{tx_id}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "admin_panel")
def cb_admin_panel(call):
    if not is_admin(call.from_user.id):
        return
    conn = get_db()
    pending_tx = conn.execute("SELECT COUNT(*) FROM transactions WHERE status='pending'").fetchone()[0]
    total_fees = conn.execute("SELECT COALESCE(SUM(platform_fee),0) FROM transactions WHERE status='approved'").fetchone()[0]
    contents = conn.execute("SELECT COUNT(*) FROM content").fetchone()[0]
    users_n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    creators_n = conn.execute("SELECT COUNT(*) FROM users WHERE creator_verified=2").fetchone()[0]
    conn.close()
    text = (
        f"🔧 <b>Panel Admin</b>\n\n"
        f"👥 Usuarios: {users_n} | 🎨 Creadores: {creators_n}\n"
        f"⏳ Pagos pendientes: <b>{pending_tx}</b>\n"
        f"📸 Contenidos: {contents}\n"
        f"💰 Comisiones: {format_price(total_fees)} ({get_platform_fee_percent()}%)\n"
        f"Grupo: {escape_html(GROUP_INVITE or '—')}"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("⏳ Pagos pendientes", callback_data="admin_pending_tx"))
    kb.add(types.InlineKeyboardButton("💳 Métodos de pago", callback_data="admin_pay_methods"))
    kb.add(types.InlineKeyboardButton("💰 % Comisión", callback_data="set_fee"))
    kb.add(types.InlineKeyboardButton("📢 Anuncio grupo", callback_data="admin_set_announcement"))
    kb.add(types.InlineKeyboardButton("📜 Términos", callback_data="admin_set_terms"))
    kb.add(types.InlineKeyboardButton("📋 Reglas grupo", callback_data="admin_set_rules"))
    kb.add(types.InlineKeyboardButton("📊 Stats", callback_data="admin_stats"))
    kb.add(types.InlineKeyboardButton("« Menú", callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "set_fee")
def cb_set_fee(call):
    if not is_admin(call.from_user.id): return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        f"Comisión actual: {get_platform_fee_percent()}%\nEscribe el nuevo porcentaje (ej: 15):")
    bot.register_next_step_handler(msg, save_fee)

def save_fee(message):
    if not is_admin(message.from_user.id): return
    try:
        pct = float(message.text.replace(",", ".").strip())
        if not math.isfinite(pct) or pct < 0 or pct > 100: raise ValueError
    except (AttributeError, TypeError, ValueError):
        bot.send_message(message.chat.id, "❌ Número inválido (0-100).")
        return
    set_setting("platform_fee", str(pct))
    bot.send_message(message.chat.id, f"✅ Comisión actualizada a {pct}%.")

# ==================== VERIFICACIÓN (resumida) ====================
@bot.message_handler(content_types=["web_app_data"])
def handle_webapp(message):
    if not is_private_chat(message) or is_banned(message.from_user.id):
        return
    try:
        raw = message.web_app_data.data
        if not raw or len(raw) > 4096:
            return
        payload = json.loads(raw)
    except (AttributeError, TypeError, ValueError):
        return
    if not isinstance(payload, dict) or payload.get("type") != "verification" or payload.get("status") != "photos_captured":
        return
    if payload.get("user_id") not in (None, message.from_user.id):
        return
    user = get_user(message.from_user.id)
    if not user or not user["age_declared"] or not user["terms_accepted"]:
        bot.send_message(message.chat.id, "Completa primero la declaración de edad y acepta los términos con /start.")
        return
    conn = get_db()
    pending = conn.execute("SELECT id FROM verifications WHERE user_id=? AND status='pending' LIMIT 1",
                           (message.from_user.id,)).fetchone()
    if pending:
        conn.close()
        bot.send_message(message.chat.id, "Ya hay una verificación pendiente. Envía documento y selfie en este chat privado.")
        return
    conn.execute("INSERT INTO verifications (user_id, status, source, created_at) VALUES (?,'pending','webapp',?)",
                 (message.from_user.id, datetime.now().isoformat()))
    conn.execute("UPDATE users SET age_verified_real=1 WHERE user_id=?", (message.from_user.id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id,
        "La cámara de la Mini App no subió tus fotos. Para completar la solicitud, envía aquí en este chat privado "
        "primero la foto del documento y después la selfie con el documento. Ambas se enviarán al administrador para revisión.",
        reply_markup=types.ReplyKeyboardRemove())

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
        conn.close()
        bot.send_message(message.chat.id, "No tienes una verificación pendiente. Inicia /start y abre la opción de verificación primero.")
        return
    if not ver["doc_photo_id"]:
        conn.execute("UPDATE verifications SET doc_photo_id=? WHERE id=?", (file_id, ver["id"]))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "Documento OK. Envía selfie.")
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
        bot.send_photo(ADMIN_ID, ver["doc_photo_id"] or file_id, caption=f"Doc — {message.from_user.id}")
        bot.send_photo(ADMIN_ID, file_id, caption="Selfie", reply_markup=kb)
        return
    conn.close()

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("verif_"))
def cb_verify(call):
    if not is_admin(call.from_user.id): return
    parts = call.data.split("_")
    if len(parts) != 3 or parts[1] not in ("male", "female", "reject"):
        bot.answer_callback_query(call.id, "Acción no válida", show_alert=True)
        return
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
        bot.send_message(ver["user_id"], "❌ Rechazado.")
        bot.answer_callback_query(call.id, "Rechazado")
        return
    gender = "male" if action == "male" else "female"
    conn.execute("UPDATE verifications SET status='approved', assigned_gender=?, reviewed_at=?, reviewed_by=? WHERE id=?",
                 (gender, now, call.from_user.id, ver_id))
    conn.execute("UPDATE users SET age_verified_real=2, gender=?, gender_verified=1 WHERE user_id=?", (gender, ver["user_id"]))
    conn.commit()
    conn.close()
    gender_icon = "♂️" if gender == "male" else "♀️"
    bot.send_message(ver["user_id"], f"✅ Verificado. 🔞✅ {gender_icon}")
    bot.answer_callback_query(call.id, "OK")

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
        bot.send_message(message.chat.id, t("group_welcome", get_lang(tg_user=m), name=escape_html(m.first_name or "Usuario")))

@bot.message_handler(commands=["ayuda", "help", "comandos"])
def cmd_help_g(message):
    if is_private_chat(message):
        bot.send_message(message.chat.id, t("help_text", get_lang(tg_user=message.from_user)))
        return
    text = (
        "📋 <b>Comandos del grupo</b>\n\n"
        "👤 Todos:\n"
        "• /ayuda /comandos — esta lista\n"
        "• /reglas — reglas del grupo\n"
        "• /soporte &lt;msg&gt; — contactar admin\n"
        "• /yo — tu perfil y badges\n"
        "• /anuncio — anuncio de la app\n"
        "• /traducir &lt;texto&gt; — traducir a español\n\n"
    )
    if is_vip(message.from_user.id):
        text += (
            "👑 VIP / Creadores:\n"
            "• /promo — publicar perfil (cada 30 min)\n"
            "• /invitar — link de invitación a tu perfil\n\n"
        )
    if is_admin(message.from_user.id):
        text += (
            "🔧 Admin:\n"
            "• /silenciar — silenciar grupo\n"
            "• /activar — quitar silencio\n"
            "• /broadcast &lt;msg&gt; — anuncio en grupo\n"
            "• /stats — estadísticas\n"
        )
    bot.reply_to(message, text)

@bot.message_handler(commands=["reglas"])
def cmd_rules(message):
    if is_private_chat(message): return
    bot.reply_to(message, get_setting("group_rules"))

@bot.message_handler(commands=["soporte"])
def cmd_support(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "/soporte mensaje")
        return
    bot.reply_to(message, "✅ Enviado.")
    bot.send_message(ADMIN_ID, f"Soporte {message.from_user.id}: {escape_html(parts[1][:3000])}")

@bot.message_handler(commands=["yo"])
def cmd_me(message):
    upsert_user(message.from_user)
    u = get_user(message.from_user.id)
    bot.reply_to(message, f"{escape_html(message.from_user.first_name)} {get_badges(u)}")

@bot.message_handler(commands=["anuncio"])
def cmd_anuncio(message):
    bot.reply_to(message, get_setting("announcement") or "Sin anuncios.")


@bot.message_handler(commands=["traducir", "translate"])
def cmd_traducir(message):
    """Traducción simple al español para mensajes del grupo."""
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Uso: /traducir texto a traducir")
        return
    text = parts[1].strip()
    # Diccionario básico + respuesta clara (sin API externa)
    # Si el texto ya parece español, se devuelve tal cual.
    sample = text.lower()
    es_markers = (" el ", " la ", " de ", " que ", " y ", " con ", " por ", " para ")
    if any(m in f" {sample} " for m in es_markers):
        bot.reply_to(message, f"🇪🇸 Ya parece español:\n{escape_html(text)[:1500]}")
        return
    # Mini glosario para frases comunes del grupo
    glossary = {
        "hello": "hola", "hi": "hola", "thanks": "gracias", "thank you": "gracias",
        "please": "por favor", "help": "ayuda", "support": "soporte",
        "subscribe": "suscribirse", "price": "precio", "content": "contenido",
        "creator": "creador", "profile": "perfil", "welcome": "bienvenido",
        "rules": "reglas", "banned": "baneado", "promo": "promoción",
    }
    out = text
    low = text.lower()
    for en, es in sorted(glossary.items(), key=lambda x: -len(x[0])):
        if en in low:
            out = out.replace(en, es).replace(en.title(), es.capitalize()).replace(en.upper(), es.upper())
            low = out.lower()
    bot.reply_to(
        message,
        f"🇪🇸 <b>Traducción (básica)</b>:\n{escape_html(out)[:1500]}\n\n"
        f"<i>Para traducciones avanzadas usa un traductor externo; este comando cubre frases del grupo.</i>",
    )

@bot.message_handler(commands=["promo"])
def cmd_promo(message):
    if is_private_chat(message):
        bot.reply_to(message, "Usa /promo en el grupo.")
        return
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
    bot.send_message(message.chat.id, f"🔥 <b>PROMO</b>\n🎨 {escape_html(c['display_name'])}\n{escape_html(c['bio'])}\n➡️ /start")

@bot.message_handler(commands=["invitar"])
def cmd_invite(message):
    if not is_creator(message.from_user.id): return
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
    fees = conn.execute("SELECT COALESCE(SUM(platform_fee),0) FROM transactions WHERE status='approved'").fetchone()[0]
    conn.close()
    bot.reply_to(message, f"Usuarios: {u}\nComisiones: {format_price(fees)}")

@bot.message_handler(func=lambda m: m.chat.type in ("group", "supergroup") and is_group_muted() and not is_admin(m.from_user.id),
                     content_types=["text", "photo", "video", "sticker", "animation", "voice", "document"])
def filter_muted(message):
    if GROUP_ID and message.chat.id != GROUP_ID: return
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass


# ==================== FAVORITOS / AJUSTES / BLOQUEO / MENSAJES ====================
@bot.callback_query_handler(func=lambda c: c.data == "menu_favs")
def cb_favs(call):
    lang = get_lang(call.from_user.id)
    conn = get_db()
    rows = conn.execute("""SELECT f.creator_id, c.display_name, u.first_name FROM favorites f
        JOIN creators c ON c.user_id=f.creator_id
        JOIN users u ON u.user_id=f.creator_id
        WHERE f.user_id=? ORDER BY f.created_at DESC LIMIT 30""", (call.from_user.id,)).fetchall()
    conn.close()
    kb = types.InlineKeyboardMarkup()
    if not rows:
        text = t("no_favs", lang)
    else:
        text = "⭐ <b>Favoritos</b>\n\n"
        for r in rows:
            name = escape_html(r["display_name"] or r["first_name"] or str(r["creator_id"]))
            text += f"• {name}\n"
            kb.add(types.InlineKeyboardButton(name, callback_data=f"profile_{r['creator_id']}"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("togglefav_"))
def cb_toggle_fav(call):
    lang = get_lang(call.from_user.id)
    cid = int(call.data.split("_")[1])
    added = toggle_favorite(call.from_user.id, cid)
    bot.answer_callback_query(call.id, t("fav_added" if added else "fav_removed", lang))
    show_profile(call.message.chat.id, call.from_user.id, cid, call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("block_"))
def cb_block(call):
    lang = get_lang(call.from_user.id)
    tid = int(call.data.split("_")[1])
    if tid == call.from_user.id:
        bot.answer_callback_query(call.id, "No puedes bloquearte a ti mismo", show_alert=True)
        return
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO blocks (user_id, blocked_id, created_at) VALUES (?,?,?)",
                 (call.from_user.id, tid, datetime.now().isoformat()))
    conn.execute("DELETE FROM favorites WHERE user_id=? AND creator_id=?", (call.from_user.id, tid))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, t("blocked", lang), show_alert=True)
    send_main_menu(call.message.chat.id, call.from_user.id, call.message.message_id, lang)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("msgcreator_"))
def cb_msg_creator(call):
    lang = get_lang(call.from_user.id)
    tid = int(call.data.split("_")[1])
    ok, wait = check_cooldown(call.from_user.id, "msg_creator", minutes=5)
    if not ok:
        bot.answer_callback_query(call.id, f"Espera {wait} min", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, t("msg_creator_prompt", lang))
    bot.register_next_step_handler(msg, process_creator_message, tid)

def process_creator_message(message, creator_id):
    lang = get_lang(message.from_user.id)
    text = (message.text or "").strip()[:500]
    if not text:
        bot.send_message(message.chat.id, "Mensaje vacío.")
        return
    conn = get_db()
    conn.execute("INSERT INTO creator_messages (from_id, to_id, text, created_at) VALUES (?,?,?,?)",
                 (message.from_user.id, creator_id, text, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    set_cooldown(message.from_user.id, "msg_creator")
    try:
        bot.send_message(creator_id,
            f"✉️ Mensaje de {escape_html(message.from_user.first_name)} (<code>{message.from_user.id}</code>):\n\n{escape_html(text)}")
    except Exception:
        pass
    bot.send_message(message.chat.id, t("msg_sent", lang))

@bot.callback_query_handler(func=lambda c: c.data == "menu_settings")
def cb_settings(call):
    lang = get_lang(call.from_user.id)
    text = t("settings_title", lang) + f"\n\nIdioma: <b>{lang}</b>\n"
    text += "\n" + t("payment_test_mode", lang)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🇪🇸 Español", callback_data="setlang_es"),
           types.InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en"))
    kb.add(types.InlineKeyboardButton(t("pay_history", lang), callback_data="pay_history"))
    kb.add(types.InlineKeyboardButton("🗑 Eliminar mis datos", callback_data="delete_data_ask"))
    kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("setlang_"))
def cb_setlang(call):
    lang = call.data.split("_")[1]
    if lang not in ("es", "en"):
        bot.answer_callback_query(call.id, "Idioma no válido", show_alert=True)
        return
    conn = get_db()
    conn.execute("UPDATE users SET language=? WHERE user_id=?", (lang, call.from_user.id))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, t("lang_set", lang))
    cb_settings(call)

@bot.callback_query_handler(func=lambda c: c.data == "pay_history")
def cb_pay_history(call):
    lang = get_lang(call.from_user.id)
    conn = get_db()
    rows = conn.execute("""SELECT id, type, amount, status, created_at FROM transactions
        WHERE user_id=? ORDER BY id DESC LIMIT 15""", (call.from_user.id,)).fetchall()
    conn.close()
    if not rows:
        text = t("empty_history", lang)
    else:
        text = t("pay_history", lang) + "\n\n"
        for r in rows:
            text += f"#{r['id']} {escape_html(r['type'])} {format_price(r['amount'])} — {r['status']} ({(r['created_at'] or '')[:10]})\n"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="menu_settings"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "delete_data_ask")
def cb_delete_ask(call):
    lang = get_lang(call.from_user.id)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Confirmar borrado", callback_data="delete_data_yes"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="menu_settings"))
    bot.edit_message_text(t("delete_data_confirm", lang), call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "delete_data_yes")
def cb_delete_yes(call):
    lang = get_lang(call.from_user.id)
    uid = call.from_user.id
    if is_admin(uid):
        bot.answer_callback_query(call.id, "El admin no puede auto-borrarse", show_alert=True)
        return
    conn = get_db()
    for table, col in [
        ("favorites", "user_id"), ("blocks", "user_id"), ("reactions", "user_id"),
        ("comments", "user_id"), ("subscriptions", "user_id"), ("transactions", "user_id"),
        ("verifications", "user_id"), ("reports", "reporter_id"), ("creator_messages", "from_id"),
        ("videocalls", "user_id"), ("cooldowns", "user_id"),
    ]:
        try:
            conn.execute(f"DELETE FROM {table} WHERE {col}=?", (uid,))
        except Exception:
            pass
    conn.execute("DELETE FROM users WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    bot.edit_message_text(t("delete_data_done", lang), call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("viewfree_"))
def cb_view_free(call):
    lang = get_lang(call.from_user.id)
    parts = call.data.split("_")
    creator_id, offset = int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
    conn = get_db()
    rows = conn.execute("""SELECT * FROM content WHERE creator_id=? AND is_free=1
        ORDER BY id DESC LIMIT 1 OFFSET ?""", (creator_id, offset)).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM content WHERE creator_id=? AND is_free=1", (creator_id,)).fetchone()[0]
    conn.close()
    if not rows:
        bot.answer_callback_query(call.id, t("no_content", lang), show_alert=True)
        return
    item = rows[0]
    caption = f"🆓 Muestra\n{escape_html(item['title'] or '')}"
    try:
        if item["media_type"] == "video":
            bot.send_video(call.message.chat.id, item["file_id"], caption=caption, protect_content=True)
        else:
            bot.send_photo(call.message.chat.id, item["file_id"], caption=caption, protect_content=True)
    except Exception:
        bot.send_message(call.message.chat.id, t("no_content", lang))
    kb = types.InlineKeyboardMarkup()
    if offset + 1 < total:
        kb.add(types.InlineKeyboardButton("Siguiente muestra", callback_data=f"viewfree_{creator_id}_{offset+1}"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data=f"profile_{creator_id}"))
    bot.send_message(call.message.chat.id, f"Muestra {offset+1}/{total}", reply_markup=kb)
    bot.answer_callback_query(call.id)



@bot.callback_query_handler(func=lambda c: c.data == "edit_profile_menu")
def cb_edit_profile_menu(call):
    lang = get_lang(call.from_user.id)
    user = get_user(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id, t("profile_incomplete", lang), show_alert=True)
        return
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(t("set_name", lang), callback_data="edit_name"))
    kb.add(types.InlineKeyboardButton(t("set_bio", lang), callback_data="edit_bio"))
    kb.add(types.InlineKeyboardButton(t("set_photo", lang), callback_data="edit_photo"))
    kb.add(types.InlineKeyboardButton(t("set_location", lang), callback_data="edit_location"))
    kb.add(types.InlineKeyboardButton(t("set_links", lang), callback_data="edit_links"))
    kb.add(types.InlineKeyboardButton(t("set_cats", lang), callback_data="edit_cats"))
    kb.add(types.InlineKeyboardButton(t("back", lang), callback_data="menu_account"))
    bot.edit_message_text("✏️ <b>Editar perfil</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "edit_name")
def cb_edit_name(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, t("onboard_name", get_lang(call.from_user.id)))
    bot.register_next_step_handler(msg, process_edit_name)

def process_edit_name(message):
    lang = get_lang(message.from_user.id)
    name = (message.text or "").strip()
    if len(name) < 2 or len(name) > 40:
        bot.send_message(message.chat.id, "Nombre entre 2 y 40 caracteres.")
        return
    conn = get_db()
    conn.execute("UPDATE users SET display_name=? WHERE user_id=?", (name, message.from_user.id))
    conn.execute("UPDATE creators SET display_name=? WHERE user_id=?", (name, message.from_user.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, t("name_saved", lang))

@bot.callback_query_handler(func=lambda c: c.data == "edit_bio")
def cb_edit_bio(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, t("onboard_bio", get_lang(call.from_user.id)))
    bot.register_next_step_handler(msg, process_edit_bio)

def process_edit_bio(message):
    lang = get_lang(message.from_user.id)
    bio = (message.text or "").strip()
    if bio.lower() in ("skip", "omitir", "-"):
        bio = ""
    bio = bio[:300]
    conn = get_db()
    conn.execute("UPDATE users SET bio=? WHERE user_id=?", (bio, message.from_user.id))
    conn.execute("UPDATE creators SET bio=? WHERE user_id=?", (bio, message.from_user.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, t("bio_saved", lang))

@bot.callback_query_handler(func=lambda c: c.data == "edit_photo")
def cb_edit_photo(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, t("onboard_photo", get_lang(call.from_user.id)))
    bot.register_next_step_handler(msg, process_edit_photo)

def process_edit_photo(message):
    lang = get_lang(message.from_user.id)
    if not message.photo:
        bot.send_message(message.chat.id, t("photo_required", lang))
        bot.register_next_step_handler(message, process_edit_photo)
        return
    file_id = message.photo[-1].file_id
    conn = get_db()
    conn.execute("UPDATE users SET profile_photo_id=? WHERE user_id=?", (file_id, message.from_user.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, t("photo_saved", lang))



@bot.callback_query_handler(func=lambda c: c.data == "edit_location")
def cb_edit_location(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, t("onboard_location", get_lang(call.from_user.id)))
    bot.register_next_step_handler(msg, process_edit_location)

def process_edit_location(message):
    lang = get_lang(message.from_user.id)
    loc = (message.text or "").strip()
    if loc.lower() in ("skip", "omitir", "-"):
        loc = ""
    conn = get_db()
    conn.execute("UPDATE users SET location=? WHERE user_id=?", (loc[:80], message.from_user.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, t("location_saved", lang))

@bot.callback_query_handler(func=lambda c: c.data == "edit_links")
def cb_edit_links(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, t("onboard_links", get_lang(call.from_user.id)))
    bot.register_next_step_handler(msg, process_edit_links)

def process_edit_links(message):
    lang = get_lang(message.from_user.id)
    website, ig, x, tt = _parse_links_line(message.text)
    conn = get_db()
    conn.execute(
        "UPDATE users SET website=?, social_ig=?, social_x=?, social_tiktok=? WHERE user_id=?",
        (website, ig, x, tt, message.from_user.id),
    )
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, t("links_saved", lang))

@bot.callback_query_handler(func=lambda c: c.data == "edit_cats")
def cb_edit_cats(call):
    bot.answer_callback_query(call.id)
    send_category_picker(call.message.chat.id, call.from_user.id, get_lang(call.from_user.id), onboard=False)



# ==================== ADMIN: PAGOS Y AJUSTES ====================
PAY_METHOD_KEYS = [
    ("pay_zelle", "🇺🇸 Zelle"),
    ("pay_mexico", "🇲🇽 México (banco/CLABE)"),
    ("pay_oxxo", "🏪 OXXO"),
    ("pay_euros", "🇪🇺 Euros"),
    ("pay_mobile", "📱 Saldo móvil"),
    ("pay_other", "➕ Otro"),
]

@bot.callback_query_handler(func=lambda c: c.data == "admin_pay_methods")
def cb_admin_pay_methods(call):
    if not is_admin(call.from_user.id):
        return
    text = "💳 <b>Métodos de pago</b>\n\nElige cuál editar. El texto que pongas lo verán los usuarios al pagar.\n\n"
    text += build_payment_methods_text()
    kb = types.InlineKeyboardMarkup()
    for key, label in PAY_METHOD_KEYS:
        kb.add(types.InlineKeyboardButton(label, callback_data=f"admin_edit_pay_{key}"))
    kb.add(types.InlineKeyboardButton("🔄 Regenerar texto", callback_data="admin_refresh_pay"))
    kb.add(types.InlineKeyboardButton("« Admin", callback_data="admin_panel"))
    bot.edit_message_text(text[:4000], call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_refresh_pay")
def cb_admin_refresh_pay(call):
    if not is_admin(call.from_user.id):
        return
    refresh_payment_methods_setting()
    bot.answer_callback_query(call.id, "Texto actualizado")
    cb_admin_pay_methods(call)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("admin_edit_pay_"))
def cb_admin_edit_pay(call):
    if not is_admin(call.from_user.id):
        return
    key = call.data.replace("admin_edit_pay_", "", 1)
    labels = dict(PAY_METHOD_KEYS)
    if key not in labels:
        bot.answer_callback_query(call.id, "Método no válido", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    current = get_setting(key) or "—"
    msg = bot.send_message(
        call.message.chat.id,
        f"Editar <b>{labels[key]}</b>\nActual: <code>{escape_html(current)}</code>\n\n"
        f"Envía el nuevo texto (cuenta, CLABE, teléfono, instrucciones).\n"
        f"Escribe <code>-</code> para dejarlo vacío.",
    )
    bot.register_next_step_handler(msg, process_admin_pay_value, key, labels[key])

def process_admin_pay_value(message, key, label):
    if not is_admin(message.from_user.id):
        return
    val = (message.text or "").strip()
    if val == "-":
        val = "—"
    if len(val) > 500:
        val = val[:500]
    set_setting(key, val)
    refresh_payment_methods_setting()
    bot.send_message(message.chat.id, f"✅ {label} actualizado.\n<code>{escape_html(val)}</code>")

@bot.callback_query_handler(func=lambda c: c.data == "admin_pending_tx")
def cb_admin_pending_tx(call):
    if not is_admin(call.from_user.id):
        return
    conn = get_db()
    rows = conn.execute(
        """SELECT id, user_id, creator_id, type, amount, status, created_at, screenshot_file_id
           FROM transactions WHERE status='pending' ORDER BY id DESC LIMIT 15"""
    ).fetchall()
    conn.close()
    if not rows:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("« Admin", callback_data="admin_panel"))
        bot.edit_message_text("No hay pagos pendientes.", call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    text = "⏳ <b>Pagos pendientes</b>\n\n"
    kb = types.InlineKeyboardMarkup()
    for r in rows:
        text += f"#{r['id']} user {r['user_id']} → {r['creator_id'] or '-'} | {r['type']} {format_price(r['amount'])}\n"
        kb.add(
            types.InlineKeyboardButton(f"✅ #{r['id']}", callback_data=f"approve_tx_{r['id']}"),
            types.InlineKeyboardButton(f"❌ #{r['id']}", callback_data=f"reject_tx_{r['id']}"),
        )
    kb.add(types.InlineKeyboardButton("« Admin", callback_data="admin_panel"))
    bot.edit_message_text(text[:4000], call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_set_announcement")
def cb_admin_set_announcement(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Envía el nuevo texto de /anuncio del grupo:")
    bot.register_next_step_handler(msg, lambda m: _admin_save_setting(m, "announcement", "Anuncio"))

@bot.callback_query_handler(func=lambda c: c.data == "admin_set_terms")
def cb_admin_set_terms(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Envía el nuevo texto de términos (HTML básico permitido):")
    bot.register_next_step_handler(msg, lambda m: _admin_save_setting(m, "terms", "Términos"))

@bot.callback_query_handler(func=lambda c: c.data == "admin_set_rules")
def cb_admin_set_rules(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Envía el nuevo texto de /reglas del grupo:")
    bot.register_next_step_handler(msg, lambda m: _admin_save_setting(m, "group_rules", "Reglas"))

def _admin_save_setting(message, key, label):
    if not is_admin(message.from_user.id):
        return
    val = (message.text or "").strip()
    if not val:
        bot.send_message(message.chat.id, "Vacío, no se guardó.")
        return
    set_setting(key, val[:4000])
    bot.send_message(message.chat.id, f"✅ {label} actualizado.")

@bot.callback_query_handler(func=lambda c: c.data == "admin_stats")
def cb_admin_stats(call):
    if not is_admin(call.from_user.id):
        return
    conn = get_db()
    users_n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    vip_n = conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM subscriptions WHERE status='active'"
    ).fetchone()[0]
    fees = conn.execute(
        "SELECT COALESCE(SUM(platform_fee),0) FROM transactions WHERE status='approved'"
    ).fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM transactions WHERE status='pending'").fetchone()[0]
    conn.close()
    text = (
        f"📊 <b>Stats</b>\n\nUsuarios: {users_n}\nCon plan activo: {vip_n}\n"
        f"Pendientes: {pending}\nComisiones: {format_price(fees)}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Admin", callback_data="admin_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id)

# Reply keyboard text shortcuts (private chat)
@bot.message_handler(func=lambda m: m.chat.type == "private" and (m.text or "") in {
    "🔍 Explorar", "🔎 Buscar", "⭐ Favoritos", "📋 Mis planes", "👤 Mi perfil",
    "⚙️ Ajustes", "❓ Ayuda", "🏠 Menú",
})
def reply_keyboard_router(message):
    if is_banned(message.from_user.id):
        return
    user = get_user(message.from_user.id)
    lang = get_lang(tg_user=message.from_user)
    if not user or not user["age_declared"] or not user["terms_accepted"] or not profile_is_complete(user):
        show_login(message.chat.id, lang, message.from_user)
        return
    text = message.text or ""
    uid = message.from_user.id
    chat_id = message.chat.id
    if text == "🏠 Menú":
        send_main_menu(chat_id, uid, lang=lang)
        return
    if text == "🔎 Buscar":
        msg = bot.send_message(chat_id, t("search_prompt", lang))
        bot.register_next_step_handler(msg, process_search)
        return
    if text == "❓ Ayuda":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(t("back_menu", lang), callback_data="menu_main"))
        bot.send_message(chat_id, t("help_text", lang), reply_markup=kb)
        return
    # For the rest: send a menu message the user can use with inline buttons
    mapping = {
        "🔍 Explorar": "menu_explore",
        "⭐ Favoritos": "menu_favs",
        "📋 Mis planes": "menu_subs",
        "👤 Mi perfil": "menu_account",
        "⚙️ Ajustes": "menu_settings",
    }
    data = mapping.get(text)
    if not data:
        return
    # Create a disposable message and "click" via editing flow
    sent = bot.send_message(chat_id, "⏳ Cargando...")
    class _Msg:
        pass
    class _Call:
        pass
    m = _Msg()
    m.chat = message.chat
    m.message_id = sent.message_id
    m.text = message.text
    c = _Call()
    c.from_user = message.from_user
    c.message = m
    c.id = "rk"
    c.data = data
    try:
        if data == "menu_explore":
            cb_explore(c)
        elif data == "menu_favs":
            cb_favs(c)
        elif data == "menu_subs":
            cb_subs(c)
        elif data == "menu_account":
            cb_account(c)
        elif data == "menu_settings":
            cb_settings(c)
    except Exception as e:
        bot.edit_message_text(f"Error: {e}", chat_id, sent.message_id)


def validate_runtime_config():
    if not TELEGRAM_TOKEN or ":" not in TELEGRAM_TOKEN or TELEGRAM_TOKEN.startswith("PON_AQUI"):
        raise RuntimeError("Configura TELEGRAM_TOKEN como variable de entorno antes de arrancar.")
    token_id, separator, token_secret = TELEGRAM_TOKEN.partition(":")
    if not separator or not token_id.isdigit() or not token_secret:
        raise RuntimeError("TELEGRAM_TOKEN no tiene el formato esperado.")
    if ADMIN_ID <= 0:
        raise RuntimeError("Configura un ADMIN_ID numérico positivo.")
    if WEBAPP_VERIFICATION_URL and not WEBAPP_VERIFICATION_URL.startswith("https://"):
        raise RuntimeError("WEBAPP_VERIFICATION_URL debe usar HTTPS.")

if __name__ == "__main__":
    validate_runtime_config()
    init_db()
    group_muted = is_group_muted()
    print("OnlyFans_ManagerBot V9 started")
    print(f"Comisión plataforma: {get_platform_fee_percent()}%")
    print("Precios editables | Borrar contenido | Videollamadas")
    print("Polling activo — el proceso se mantiene en ejecución")
    # infinity_polling mantiene el proceso vivo consultando Telegram
    bot.infinity_polling(none_stop=True, interval=0, timeout=20)
