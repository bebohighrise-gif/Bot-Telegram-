#!/usr/bin/env python3
"""
BF3 Cheat Hunter - Sistema de búsqueda de trampas para Battlefield 3
Bot de Telegram + Escaneo continuo + Hashes SHA-256
"""

import threading
import time
import requests
import hashlib
import os
import re
import logging
from datetime import datetime
from typing import Optional, Tuple, Set
import telebot
from telebot import types

# --- CONFIGURACIÓN ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Telegram Bot
TELEGRAM_TOKEN = "8401493599:AAF1SbAfmEepa-9gkTa3BgloyfoEq5vOIGA"
ADMIN_CHAT_ID = 7653419875

# Archivos
HASH_FILE = "/app/hashes.txt"
LOG_FILE = "/app/search_log.txt"

# API Tokens (opcionales)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")

# Headers para APIs
HEADERS_GITHUB = {'Authorization': f'token {GITHUB_TOKEN}'} if GITHUB_TOKEN else {}
HEADERS_GITLAB = {'PRIVATE-TOKEN': GITLAB_TOKEN} if GITLAB_TOKEN else {}

# --- TÉRMINOS DE BÚSQUEDA BF3 ---
TERMINOS_BF3 = [
    # Términos generales BF3
    "battlefield 3 cheat", "bf3 hack", "bf3 injector", "bf3 aimbot",
    "bf3 wallhack", "bf3 esp", "bf3 multihack", "bf3 trainer",
    "battlefield 3 hack dll", "bf3 silent aim", "bf3 no recoil",
    
    # Nombres específicos de trampas conocidas
    "cheatengine", "extreme injector", "x64dbg", "ollydbg",
    "dll injector", "process hacker", "reclass", "ida pro",
    
    # Bypasses anti-cheat
    "punkbuster bypass", "pb bypass", "fairfight bypass",
    "eac bypass", "battleye bypass", "anticheat bypass",
    
    # Herramientas de inyección
    "manual map injector", "reflective dll injection",
    "kernel injector", "driver injector",
]

# Tags para MalwareBazaar
TAGS_MALWAREBAZAAR = [
    "injector", "game-hack", "cheat", "aimbot", "wallhack",
    "esp", "trainer", "dll-injection", "memory-hack"
]

# Nombres de procesos conocidos de trampas
KNOWN_CHEAT_NAMES = {
    # Editores de Memoria
    "cheatengine", "ce", "artmoney", "tsearch", "scanmem", "squalr",
    "gamehacker", "pmemory", "memoryhacker", "hexeditor", "hxd", "winhex",
    
    # Inyectores DLL
    "extremeinjector", "extreme_injector", "xenos", "injectme", "dllinjector",
    "processinjector", "winject", "ginjector", "rinjector", "simpleinject",
    
    # Depuradores
    "x64dbg", "x32dbg", "ollydbg", "ida", "ida64", "windbg", "dnspy",
    "ilspy", "dotpeek", "reclass", "pe-bear", "cffexplorer",
    
    # Trucos específicos
    "bf3hack", "bf3cheat", "aimbot", "wallhack", "esp", "ragehack",
    "multihack", "hwidspoofer", "spoofer", "speedhack", "norecoil",
    
    # Análisis de Red
    "wireshark", "fiddler", "charles", "burpsuite", "mitmproxy",
    
    # Automatización
    "autoclicker", "tinytask", "macrorecorder", "autoit",
}

# --- ESTADO GLOBAL ---
hashes_set: Set[str] = set()
data_lock = threading.Lock()
bot = telebot.TeleBot(TELEGRAM_TOKEN)
scanning_active = True
current_search = "Iniciando..."
total_found = 0
last_update = "-"


def cargar_hashes():
    """Carga los hashes existentes del archivo TXT"""
    global hashes_set, total_found
    if os.path.exists(HASH_FILE):
        try:
            with open(HASH_FILE, "r", encoding="utf-8") as f:
                hashes_set = {line.strip() for line in f if line.strip()}
            total_found = len(hashes_set)
            logging.info(f"Cargados {total_found} hashes desde {HASH_FILE}")
        except Exception as e:
            logging.error(f"Error cargando hashes: {e}")
            hashes_set = set()


def guardar_hash(sha256: str, nombre: str = "", fuente: str = ""):
    """Guarda un nuevo hash en el archivo TXT (uno por línea)"""
    global total_found
    with data_lock:
        if sha256 not in hashes_set:
            hashes_set.add(sha256)
            total_found = len(hashes_set)
            
            # Guardar solo el hash en el archivo principal
            with open(HASH_FILE, "a", encoding="utf-8") as f:
                f.write(f"{sha256}\n")
            
            # Guardar log detallado
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {nombre} | {sha256} | {fuente}\n")
            
            logging.info(f"[+] NUEVO: {nombre} | {sha256[:16]}... | {fuente}")
            
            # Notificar por Telegram
            notificar_nueva_trampa(sha256, nombre, fuente)
            return True
    return False


def notificar_nueva_trampa(sha256: str, nombre: str, fuente: str):
    """Envía notificación al admin cuando se encuentra una trampa"""
    try:
        mensaje = (
            f"🚨 *NUEVA TRAMPA DETECTADA*\n\n"
            f"📁 *Nombre:* `{nombre}`\n"
            f"🔐 *SHA-256:*\n`{sha256}`\n"
            f"📍 *Fuente:* {fuente}\n"
            f"⏰ *Fecha:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        bot.send_message(ADMIN_CHAT_ID, mensaje, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error enviando notificación Telegram: {e}")


def calcular_hash_archivo(contenido: bytes) -> str:
    """Calcula SHA-256 de contenido binario"""
    return hashlib.sha256(contenido).hexdigest()


def calcular_hash_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Descarga archivo y calcula SHA-256 y MD5"""
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        
        sha256 = hashlib.sha256()
        md5 = hashlib.md5()
        
        for chunk in r.iter_content(chunk_size=8192):
            sha256.update(chunk)
            md5.update(chunk)
        
        return sha256.hexdigest(), md5.hexdigest()
    except Exception as e:
        logging.warning(f"Error descargando {url}: {e}")
        return None, None


def es_archivo_trampa(nombre: str) -> bool:
    """Verifica si el nombre coincide con trampas conocidas"""
    nombre_lower = nombre.lower()
    
    # Verificar extensión
    if not nombre_lower.endswith(('.dll', '.exe', '.sys')):
        return False
    
    # Verificar nombres conocidos
    base_name = nombre_lower.replace('.dll', '').replace('.exe', '').replace('.sys', '')
    
    for cheat_name in KNOWN_CHEAT_NAMES:
        if cheat_name in base_name:
            return True
    
    # Palabras clave sospechosas
    keywords = ['hack', 'cheat', 'inject', 'aim', 'esp', 'wall', 'bypass', 'spoof']
    for kw in keywords:
        if kw in base_name:
            return True
    
    return False


# ============================================
# FUENTES DE BÚSQUEDA
# ============================================

def buscar_github(query: str):
    """Busca en GitHub repositorios con archivos sospechosos"""
    global current_search
    current_search = f"GitHub: {query}"
    
    try:
        url = f"https://api.github.com/search/repositories?q={query.replace(' ', '+')}&sort=updated&per_page=30"
        r = requests.get(url, headers=HEADERS_GITHUB, timeout=15)
        
        if r.status_code == 403:
            reset = int(r.headers.get('X-RateLimit-Reset', time.time() + 60))
            wait = max(0, reset - time.time()) + 10
            logging.warning(f"[GitHub] Rate limit. Esperando {wait:.0f}s")
            time.sleep(wait)
            return
        
        r.raise_for_status()
        
        for repo in r.json().get('items', [])[:10]:
            try:
                contents_url = repo['contents_url'].replace('{+path}', '')
                cr = requests.get(contents_url, headers=HEADERS_GITHUB, timeout=10)
                
                if cr.status_code != 200:
                    continue
                
                archivos = cr.json()
                if not isinstance(archivos, list):
                    continue
                
                for f in archivos:
                    if f.get('type') == 'file' and es_archivo_trampa(f.get('name', '')):
                        sha256, _ = calcular_hash_url(f.get('download_url', ''))
                        if sha256:
                            guardar_hash(sha256, f['name'], f"GitHub: {repo['full_name']}")
                
                time.sleep(2)
            except Exception as e:
                logging.debug(f"[GitHub] Error repo: {e}")
                
    except Exception as e:
        logging.error(f"[GitHub] Error búsqueda '{query}': {e}")


def buscar_gitlab(query: str):
    """Busca en GitLab proyectos con archivos sospechosos"""
    global current_search
    current_search = f"GitLab: {query}"
    
    try:
        url = f"https://gitlab.com/api/v4/projects?search={query.replace(' ', '+')}&order_by=last_activity_at&per_page=20"
        r = requests.get(url, headers=HEADERS_GITLAB, timeout=15)
        r.raise_for_status()
        
        for proyecto in r.json()[:10]:
            try:
                pid = proyecto.get('id')
                tree_url = f"https://gitlab.com/api/v4/projects/{pid}/repository/tree"
                tr = requests.get(tree_url, headers=HEADERS_GITLAB, timeout=10)
                
                if tr.status_code != 200:
                    continue
                
                for item in tr.json():
                    if item.get('type') == 'blob' and es_archivo_trampa(item.get('name', '')):
                        branch = proyecto.get('default_branch', 'main')
                        raw_url = f"https://gitlab.com/{proyecto['path_with_namespace']}/-/raw/{branch}/{item['name']}"
                        sha256, _ = calcular_hash_url(raw_url)
                        if sha256:
                            guardar_hash(sha256, item['name'], f"GitLab: {proyecto['path_with_namespace']}")
                
                time.sleep(1)
            except Exception as e:
                logging.debug(f"[GitLab] Error proyecto: {e}")
                
    except Exception as e:
        logging.error(f"[GitLab] Error búsqueda '{query}': {e}")


def buscar_malwarebazaar(tag: str):
    """Busca en MalwareBazaar por tag (API gratuita)"""
    global current_search
    current_search = f"MalwareBazaar: {tag}"
    
    try:
        url = "https://mb-api.abuse.ch/api/v1/"
        payload = {"query": "get_taginfo", "tag": tag, "limit": 100}
        
        r = requests.post(url, data=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        
        if data.get("query_status") != "ok":
            return
        
        for muestra in data.get("data", []):
            nombre = muestra.get("file_name", "unknown")
            sha256 = muestra.get("sha256_hash", "")
            
            if sha256 and es_archivo_trampa(nombre):
                guardar_hash(sha256, nombre, "MalwareBazaar")
                
    except Exception as e:
        logging.error(f"[MalwareBazaar] Error tag '{tag}': {e}")


def buscar_virustotal_recientes():
    """Busca archivos recientes reportados (sin API key, limitado)"""
    global current_search
    current_search = "VirusTotal: archivos recientes"
    
    # VirusTotal requiere API key para búsquedas avanzadas
    # Aquí buscamos por nombres conocidos en su feed público
    logging.info("[VirusTotal] Requiere API key para búsquedas avanzadas")


def buscar_hybrid_analysis():
    """Busca en Hybrid Analysis (sandbox público)"""
    global current_search
    current_search = "HybridAnalysis: muestras recientes"
    
    try:
        # API pública de Hybrid Analysis
        url = "https://www.hybrid-analysis.com/api/v2/feed/latest"
        headers = {
            "User-Agent": "Falcon Sandbox",
            "Accept": "application/json"
        }
        
        r = requests.get(url, headers=headers, timeout=20)
        
        if r.status_code == 200:
            data = r.json()
            for item in data.get('data', []):
                sha256 = item.get('sha256', '')
                nombre = item.get('submit_name', 'unknown')
                
                if sha256 and es_archivo_trampa(nombre):
                    guardar_hash(sha256, nombre, "HybridAnalysis")
    except Exception as e:
        logging.debug(f"[HybridAnalysis] Error: {e}")


def buscar_por_nombre_proceso(nombre: str):
    """Busca un nombre específico de proceso en todas las fuentes"""
    global current_search
    current_search = f"Búsqueda específica: {nombre}"
    
    logging.info(f"Buscando proceso específico: {nombre}")
    
    # Buscar en GitHub
    buscar_github(f"{nombre} dll exe")
    time.sleep(5)
    
    # Buscar en GitLab
    buscar_gitlab(f"{nombre}")
    time.sleep(3)
    
    # Buscar en MalwareBazaar
    try:
        url = "https://mb-api.abuse.ch/api/v1/"
        payload = {"query": "get_file_info", "search_term": nombre, "limit": 50}
        r = requests.post(url, data=payload, timeout=20)
        if r.status_code == 200:
            data = r.json()
            for muestra in data.get("data", []):
                sha256 = muestra.get("sha256_hash", "")
                file_name = muestra.get("file_name", nombre)
                if sha256:
                    guardar_hash(sha256, file_name, f"MalwareBazaar (búsqueda: {nombre})")
    except Exception as e:
        logging.debug(f"Error buscando {nombre} en MalwareBazaar: {e}")


# ============================================
# COMANDOS DEL BOT DE TELEGRAM
# ============================================

@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    """Muestra ayuda del bot"""
    ayuda = """
🛡️ *BF3 Cheat Hunter Bot*

*Comandos disponibles:*

/status - Estado actual del escaneo
/stats - Estadísticas de hashes encontrados
/hashes - Descargar archivo de hashes
/buscar <nombre> - Buscar trampa específica
/pausar - Pausar escaneo
/reanudar - Reanudar escaneo

*Envía un archivo .exe o .dll* para obtener su hash y verificar si está en la base de datos.
"""
    bot.reply_to(message, ayuda, parse_mode="Markdown")


@bot.message_handler(commands=['status'])
def cmd_status(message):
    """Muestra estado actual del escaneo"""
    status = (
        f"📊 *Estado del Escaneo*\n\n"
        f"🔍 *Buscando en:* {current_search}\n"
        f"📁 *Total hashes:* {total_found}\n"
        f"⏰ *Última actualización:* {last_update}\n"
        f"🟢 *Escaneo activo:* {'Sí' if scanning_active else 'No'}"
    )
    bot.reply_to(message, status, parse_mode="Markdown")


@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    """Muestra estadísticas detalladas"""
    stats = (
        f"📈 *Estadísticas*\n\n"
        f"🔐 *Total hashes únicos:* {len(hashes_set)}\n"
        f"📅 *Fecha inicio:* {datetime.now().strftime('%Y-%m-%d')}\n"
        f"🔄 *Ciclos completados:* Continuo"
    )
    bot.reply_to(message, stats, parse_mode="Markdown")


@bot.message_handler(commands=['hashes'])
def cmd_hashes(message):
    """Envía el archivo de hashes"""
    try:
        if os.path.exists(HASH_FILE) and os.path.getsize(HASH_FILE) > 0:
            with open(HASH_FILE, 'rb') as f:
                bot.send_document(
                    message.chat.id, 
                    f, 
                    caption=f"📁 Archivo de hashes ({len(hashes_set)} entradas)"
                )
        else:
            bot.reply_to(message, "⚠️ El archivo de hashes está vacío o no existe.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error enviando archivo: {e}")


@bot.message_handler(commands=['buscar'])
def cmd_buscar(message):
    """Busca un nombre específico de trampa"""
    try:
        partes = message.text.split(maxsplit=1)
        if len(partes) < 2:
            bot.reply_to(message, "⚠️ Uso: /buscar <nombre_proceso>")
            return
        
        nombre = partes[1].strip()
        bot.reply_to(message, f"🔍 Buscando '{nombre}'... Te notificaré si encuentro algo.")
        
        # Ejecutar búsqueda en hilo separado
        threading.Thread(target=buscar_por_nombre_proceso, args=(nombre,), daemon=True).start()
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")


@bot.message_handler(commands=['pausar'])
def cmd_pausar(message):
    """Pausa el escaneo"""
    global scanning_active
    scanning_active = False
    bot.reply_to(message, "⏸️ Escaneo pausado")


@bot.message_handler(commands=['reanudar'])
def cmd_reanudar(message):
    """Reanuda el escaneo"""
    global scanning_active
    scanning_active = True
    bot.reply_to(message, "▶️ Escaneo reanudado")


@bot.message_handler(content_types=['document'])
def handle_document(message):
    """Procesa archivos .exe o .dll enviados"""
    try:
        doc = message.document
        file_name = doc.file_name.lower()
        
        if not file_name.endswith(('.exe', '.dll', '.sys')):
            bot.reply_to(message, "⚠️ Solo acepto archivos .exe, .dll o .sys")
            return
        
        # Descargar archivo
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        # Calcular hash
        sha256 = calcular_hash_archivo(downloaded)
        
        # Verificar si existe
        existe = sha256 in hashes_set
        
        respuesta = (
            f"📁 *Archivo:* `{doc.file_name}`\n"
            f"📏 *Tamaño:* {doc.file_size:,} bytes\n"
            f"🔐 *SHA-256:*\n`{sha256}`\n\n"
        )
        
        if existe:
            respuesta += "⚠️ *Este hash YA ESTÁ en la base de datos de trampas conocidas*"
        else:
            respuesta += "✅ *Este hash NO está en la base de datos*\n\n¿Deseas agregarlo? Envía /agregar"
            # Guardar temporalmente para posible agregación
            bot.register_next_step_handler(
                bot.reply_to(message, respuesta, parse_mode="Markdown"),
                lambda m: agregar_hash_confirmado(m, sha256, doc.file_name)
            )
            return
        
        bot.reply_to(message, respuesta, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error procesando archivo: {e}")


def agregar_hash_confirmado(message, sha256: str, nombre: str):
    """Agrega hash después de confirmación"""
    if message.text and '/agregar' in message.text.lower():
        if guardar_hash(sha256, nombre, "Manual (Telegram)"):
            bot.reply_to(message, f"✅ Hash agregado correctamente:\n`{sha256}`", parse_mode="Markdown")
        else:
            bot.reply_to(message, "ℹ️ El hash ya existía en la base de datos")
    else:
        bot.reply_to(message, "❌ Operación cancelada")


# ============================================
# HILO PRINCIPAL DE ESCANEO
# ============================================

def escaneo_continuo():
    """Escaneo continuo 24/7"""
    global last_update, scanning_active
    
    logging.info("Iniciando escaneo continuo...")
    
    # Notificar inicio
    try:
        bot.send_message(
            ADMIN_CHAT_ID,
            "🟢 *Bot iniciado*\nEscaneo continuo activado.",
            parse_mode="Markdown"
        )
    except:
        pass
    
    ciclo = 0
    while True:
        if not scanning_active:
            time.sleep(10)
            continue
        
        ciclo += 1
        logging.info(f"=== Ciclo #{ciclo} iniciado ===")
        
        # Buscar en GitHub
        for query in TERMINOS_BF3:
            if not scanning_active:
                break
            buscar_github(query)
            last_update = datetime.now().strftime("%H:%M:%S")
            time.sleep(15)  # Evitar rate limit
        
        # Buscar en GitLab
        for query in TERMINOS_BF3[:5]:  # Solo primeros 5 términos
            if not scanning_active:
                break
            buscar_gitlab(query)
            last_update = datetime.now().strftime("%H:%M:%S")
            time.sleep(10)
        
        # Buscar en MalwareBazaar
        for tag in TAGS_MALWAREBAZAAR:
            if not scanning_active:
                break
            buscar_malwarebazaar(tag)
            last_update = datetime.now().strftime("%H:%M:%S")
            time.sleep(5)
        
        # Buscar en Hybrid Analysis
        buscar_hybrid_analysis()
        last_update = datetime.now().strftime("%H:%M:%S")
        
        logging.info(f"=== Ciclo #{ciclo} completado. Total hashes: {total_found} ===")
        
        # Esperar antes del siguiente ciclo (30 minutos)
        time.sleep(1800)


def iniciar_bot():
    """Inicia el bot de Telegram con reconexión automática"""
    while True:
        try:
            logging.info("Conectando bot de Telegram...")
            # Limpiar updates pendientes antes de iniciar
            bot.delete_webhook(drop_pending_updates=True)
            time.sleep(1)
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            logging.error(f"Error en bot Telegram: {e}")
            time.sleep(30)  # Esperar más tiempo antes de reconectar


# ============================================
# PUNTO DE ENTRADA
# ============================================

if __name__ == "__main__":
    # Cargar hashes existentes
    cargar_hashes()
    
    # Crear archivo si no existe
    if not os.path.exists(HASH_FILE):
        open(HASH_FILE, 'w').close()
    
    # Iniciar hilo de escaneo
    scan_thread = threading.Thread(target=escaneo_continuo, daemon=True)
    scan_thread.start()
    
    # Iniciar bot (bloquea el hilo principal)
    logging.info("Bot de Telegram iniciado. Esperando comandos...")
    iniciar_bot()
