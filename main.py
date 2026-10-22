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
