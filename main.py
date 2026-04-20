cat > /app/main.py << 'ENDOFFILE'
#!/usr/bin/env python3
"""
BF3 Cheat Hunter - EXCLUSIVO para Battlefield 3
Busca trampas, hacks y herramientas de inyección específicas de BF3
"""

import threading
import time
import requests
import hashlib
import os
import logging
from datetime import datetime
from typing import Optional, Set
import telebot

# --- CONFIGURACIÓN ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

TELEGRAM_TOKEN = "8401493599:AAF1SbAfmEepa-9gkTa3BgloyfoEq5vOIGA"
ADMIN_CHAT_ID = 7653419875

HASH_FILE = "/app/hashes.txt"
LOG_FILE = "/app/search_log.txt"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")

HEADERS_GITHUB = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
} if GITHUB_TOKEN else {'Accept': 'application/vnd.github.v3+json'}

HEADERS_GITLAB = {'PRIVATE-TOKEN': GITLAB_TOKEN} if GITLAB_TOKEN else {}

# ============================================
# TÉRMINOS EXCLUSIVOS DE BF3
# ============================================

# Búsquedas de código en GitHub - ESPECÍFICAS BF3
CODIGO_BF3 = [
    "bf3+aimbot+extension:dll",
    "bf3+wallhack+extension:dll",
    "bf3+esp+extension:dll",
    "bf3+hook+extension:dll",
    "bf3+hack+extension:dll",
    "bf3+radar+extension:dll",
    "bf3+norecoil+extension:dll",
    "bf3+triggerbot+extension:dll",
    "battlefield+3+cheat+extension:dll",
    "battlefield+3+hack+extension:dll",
    "bf3+injector+extension:exe",
    "bf3+loader+extension:exe",
    "punkbuster+bypass+extension:dll",
    "punkbuster+hook+extension:dll",
    "pbbans+bypass+extension:dll",
    "fairfight+bypass+extension:dll",
    "bf3+overlay+extension:dll",
    "bf3+silent+aim+extension:dll",
    "bf3+no+spread+extension:dll",
    "bf3+prediction+extension:dll",
    "bf3+d3d+hook+extension:dll",
    "bf3+directx+hook+extension:dll",
    "bf3+renderer+hook+extension:dll",
    "frostbite+hack+extension:dll",
    "frostbite+hook+extension:dll",
]

# Búsquedas de repositorios - ESPECÍFICAS BF3
REPOS_BF3 = [
    "bf3 hack",
    "bf3 cheat",
    "bf3 aimbot",
    "bf3 wallhack",
    "bf3 esp hack",
    "battlefield 3 hack",
    "battlefield 3 cheat",
    "bf3 punkbuster bypass",
    "bf3 fairfight bypass",
    "bf3 hook d3d",
    "bf3 frostbite engine",
    "bf3 external hack",
    "bf3 internal hack",
    "bf3 overlay cheat",
    "bf3 no recoil hack",
]

# Nombres de archivos cheats específicos de BF3
NOMBRES_BF3 = [
    # BF3 directo
    "bf3hack", "bf3cheat", "bf3aimbot", "bf3wallhack", "bf3esp",
    "bf3radar", "bf3trigger", "bf3overlay", "bf3loader", "bf3hook",
    "bf3norecoil", "bf3nospread", "bf3silent", "bf3prediction",
    "bf3external", "bf3internal", "bf3d3d", "bf3menu",
    
    # Battlefield 3 explícito
    "battlefield3hack", "battlefield3cheat", "battlefield3aimbot",
    "battlefield3wallhack", "battlefield3esp", "battlefield3hook",
    
    # Frostbite Engine (motor de BF3)
    "frostbitehook", "frostbitehack", "frostbiteexploit",
    "fb3hook", "fb3hack",
    
    # PunkBuster específico de BF3
    "punkbusterbypass", "punkbusterhook", "punkbusterspoof",
    "pbbypass", "pbhack", "pbscreenshotbypass",
    "pbcleaner", "pbspoof", "pbdisabler",
    
    # FairFight (sistema anti-cheat de BF3)
    "fairfightbypass", "fairfighthook", "fairfightspoof",
    "ffbypass",
    
    # Inyectores usados comúnmente para BF3
    "extremeinjector", "xenosinjector", "injectorbf3",
    "perxinjector", "winject", "omfginjector",
    "hyperinjector", "naninjector", "jtinjector",
    
    # Herramientas de análisis usadas para BF3
    "reclass", "reclassdotnet", "cheatengine",
    "x64dbg", "x32dbg", "ollydbg", "ida64",
    "hwidspoofer", "spoofer",
    
    # Herramientas D3D/DirectX para hooks de BF3
    "d3dhook", "directxhook", "dxhook",
    "imgui", "imguihook", "imguicheat",
    "d2dhook", "direct2dhook",
]

# Extensiones a buscar
EXTENSIONES_BF3 = ['dll', 'exe', 'sys', 'bin', 'asi']

# Palabras clave específicas
KEYWORDS_BF3 = [
    'bf3', 'battlefield3', 'battlefield 3',
    'punkbuster', 'pbbans', 'fairfight',
    'frostbite', 'fb3',
    'aimbot', 'wallhack', 'esp', 'norecoil', 'nospread',
    'triggerbot', 'silentaim', 'prediction',
    'd3dhook', 'overlay', 'radarhack',
    'external', 'internal', 'injector', 'hook',
    'bypass', 'spoof', 'hwid',
]

# Tags para MalwareBazaar - enfocados en game hacks
TAGS_MALWAREBAZAAR = [
    "gamehack", "cheat", "aimbot", "wallhack",
    "esp", "injector", "dllinject", "gamecheat",
    "gamer", "hacktool",
]

# --- ESTADO GLOBAL ---
hashes_set: Set[str] = set()
data_lock = threading.Lock()
bot = telebot.TeleBot(TELEGRAM_TOKEN)
scanning_active = True
current_search = "Iniciando..."
total_found = 0
last_update = "-"
github_remaining = 60
github_reset_time = 0


def cargar_hashes():
    global hashes_set, total_found
    if os.path.exists(HASH_FILE):
        try:
            with open(HASH_FILE, "r", encoding="utf-8") as f:
                hashes_set = {line.strip() for line in f if line.strip() and len(line.strip()) == 64}
            total_found = len(hashes_set)
            logging.info(f"Cargados {total_found} hashes BF3")
        except Exception as e:
            logging.error(f"Error cargando hashes: {e}")
            hashes_set = set()


def guardar_hash(sha256: str, nombre: str = "", fuente: str = ""):
    global total_found
    if not sha256 or len(sha256) != 64:
        return False
    with data_lock:
        if sha256 not in hashes_set:
            hashes_set.add(sha256)
            total_found = len(hashes_set)
            with open(HASH_FILE, "a", encoding="utf-8") as f:
                f.write(f"{sha256}\n")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {nombre} | {sha256} | {fuente}\n")
            logging.info(f"[+] NUEVO BF3: {nombre} | {sha256[:16]}... | {fuente}")
            notificar_nueva_trampa(sha256, nombre, fuente)
            return True
    return False


def notificar_nueva_trampa(sha256: str, nombre: str, fuente: str):
    try:
        mensaje = (
            f"🚨 *TRAMPA BF3 DETECTADA*\n\n"
            f"🎮 *Juego:* Battlefield 3\n"
            f"📁 *Archivo:* `{nombre}`\n"
            f"🔐 *SHA-256:*\n`{sha256}`\n"
            f"📍 *Fuente:* {fuente}\n"
            f"⏰ *Fecha:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        bot.send_message(ADMIN_CHAT_ID, mensaje, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error notificación: {e}")


def descargar_y_hash(url: str, timeout: int = 30) -> Optional[str]:
    try:
        r = requests.get(url, stream=True, timeout=timeout)
        r.raise_for_status()
        if 'text/html' in r.headers.get('Content-Type', ''):
            return None
        size = int(r.headers.get('Content-Length', 0))
        if size > 50 * 1024 * 1024:
            return None
        sha256 = hashlib.sha256()
        downloaded = 0
        for chunk in r.iter_content(chunk_size=8192):
            sha256.update(chunk)
            downloaded += len(chunk)
            if downloaded > 50 * 1024 * 1024:
                return None
        return sha256.hexdigest()
    except:
        return None


def es_trampa_bf3(nombre: str) -> bool:
    """Verifica si es trampa específica de BF3"""
    if not nombre:
        return False
    nombre_lower = nombre.lower()
    
    # Verificar extensión
    ext = nombre_lower.rsplit('.', 1)[-1] if '.' in nombre_lower else ''
    if ext not in EXTENSIONES_BF3:
        return False
    
    base_name = nombre_lower.rsplit('.', 1)[0]
    
    # Verificar nombres específicos de BF3
    for cheat in NOMBRES_BF3:
        if cheat in base_name:
            return True
    
    # Verificar keywords BF3
    for kw in KEYWORDS_BF3:
        if kw in base_name:
            return True
    
    # Si tiene extensión sospechosa + keywords de hack genéricos
    hack_keywords = ['hack', 'cheat', 'inject', 'aim', 'esp', 'wall', 
                     'bypass', 'spoof', 'hook', 'overlay', 'radar', 'trigger']
    if any(kw in base_name for kw in hack_keywords):
        # Verificar si menciona algo de juegos/BF3
        game_keywords = ['bf3', 'battlefield', 'pb', 'punkbuster', 'fairfight',
                        'frostbite', 'game', 'gaming', 'fps', 'shooter']
        if any(gk in base_name for gk in game_keywords):
            return True
    
    return False


def esperar_github():
    global github_remaining, github_reset_time
    if github_remaining <= 2:
        wait = github_reset_time - time.time() + 5
        if wait > 0:
            logging.warning(f"[GitHub] Rate limit. Esperando {wait:.0f}s")
            time.sleep(wait)


def actualizar_github(response):
    global github_remaining, github_reset_time
    try:
        github_remaining = int(response.headers.get('X-RateLimit-Remaining', 60))
        github_reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 3600))
    except:
        pass


# ============================================
# BÚSQUEDAS BF3
# ============================================

def buscar_github_codigo_bf3(query: str):
    global current_search, github_remaining
    current_search = f"GitHub BF3: {query[:35]}"
    esperar_github()
    try:
        url = f"https://api.github.com/search/code?q={query}&per_page=30"
        r = requests.get(url, headers=HEADERS_GITHUB, timeout=15)
        actualizar_github(r)
        if r.status_code in [403, 422]:
            return
        if r.status_code != 200:
            return
        items = r.json().get('items', [])
        logging.info(f"[GitHub] '{query[:25]}' -> {len(items)} archivos")
        for item in items[:20]:
            try:
                nombre = item.get('name', '')
                if not es_trampa_bf3(nombre):
                    continue
                repo = item.get('repository', {})
                repo_name = repo.get('full_name', '')
                path = item.get('path', '')
                branch = repo.get('default_branch', 'main')
                raw_url = f"https://raw.githubusercontent.com/{repo_name}/{branch}/{path}"
                sha256 = descargar_y_hash(raw_url)
                if sha256:
                    guardar_hash(sha256, nombre, f"GitHub: {repo_name}")
                time.sleep(1)
            except:
                pass
    except Exception as e:
        logging.debug(f"[GitHub] Error: {e}")


def buscar_github_repo_bf3(repo_name: str, max_depth: int = 3):
    global github_remaining
    try:
        repo_url = f"https://api.github.com/repos/{repo_name}"
        r = requests.get(repo_url, headers=HEADERS_GITHUB, timeout=10)
        actualizar_github(r)
        if r.status_code != 200:
            return
        branch = r.json().get('default_branch', 'main')
        
        # Buscar en descripción si es BF3
        desc = r.json().get('description', '').lower() if r.json().get('description') else ''
        topics = r.json().get('topics', [])
        
        # Si no menciona BF3 en nombre/desc/topics, skipping parcial
        name_lower = repo_name.lower()
        if not any(kw in name_lower or kw in desc for kw in ['bf3', 'battlefield', 'punkbuster', 'fairfight']):
            max_depth = 1  # Buscar solo raíz
        
        cola = [("", 0)]
        encontrados = 0
        while cola and encontrados < 15:
            path, depth = cola.pop(0)
            if depth > max_depth:
                continue
            esperar_github()
            contents_url = f"https://api.github.com/repos/{repo_name}/contents/{path}"
            cr = requests.get(contents_url, headers=HEADERS_GITHUB, timeout=10)
            actualizar_github(cr)
            if cr.status_code != 200:
                continue
            items = cr.json()
            if not isinstance(items, list):
                continue
            for item in items:
                itype = item.get('type', '')
                iname = item.get('name', '')
                ipath = item.get('path', '')
                if itype == 'file' and es_trampa_bf3(iname):
                    raw_url = f"https://raw.githubusercontent.com/{repo_name}/{branch}/{ipath}"
                    sha256 = descargar_y_hash(raw_url)
                    if sha256:
                        guardar_hash(sha256, iname, f"GitHub: {repo_name}")
                        encontrados += 1
                elif itype == 'dir' and depth < max_depth:
                    cola.append((ipath, depth + 1))
            time.sleep(1)
    except:
        pass


def buscar_github_repos_bf3(query: str):
    global current_search, github_remaining
    current_search = f"GitHub Repos BF3: {query[:25]}"
    esperar_github()
    try:
        url = f"https://api.github.com/search/repositories?q={query.replace(' ', '+')}&sort=updated&per_page=15"
        r = requests.get(url, headers=HEADERS_GITHUB, timeout=15)
        actualizar_github(r)
        if r.status_code != 200:
            return
        repos = r.json().get('items', [])
        logging.info(f"[GitHub Repos] '{query}' -> {len(repos)} repos")
        for repo in repos[:8]:
            rn = repo.get('full_name', '')
            if rn:
                buscar_github_repo_bf3(rn)
                time.sleep(2)
    except:
        pass


def buscar_gitlab_bf3(query: str):
    global current_search
    current_search = f"GitLab BF3: {query[:25]}"
    try:
        url = f"https://gitlab.com/api/v4/projects"
        params = {"search": query, "order_by": "last_activity_at", "per_page": 20}
        r = requests.get(url, headers=HEADERS_GITLAB, params=params, timeout=15)
        if r.status_code != 200:
            return
        proyectos = r.json()
        logging.info(f"[GitLab] '{query}' -> {len(proyectos)} proyectos")
        for proj in proyectos[:6]:
            try:
                pid = proj.get('id')
                ns = proj.get('path_with_namespace', '')
                branch = proj.get('default_branch', 'main')
                if pid and ns:
                    # Búsqueda recursiva
                    cola = [("", 0)]
                    encontrados = 0
                    while cola and encontrados < 10:
                        path, depth = cola.pop(0)
                        if depth > 2:
                            continue
                        tree_url = f"https://gitlab.com/api/v4/projects/{pid}/repository/tree"
                        params2 = {"path": path, "per_page": 100}
                        tr = requests.get(tree_url, headers=HEADERS_GITLAB, params=params2, timeout=10)
                        if tr.status_code != 200:
                            continue
                        for item in tr.json():
                            itype = item.get('type', '')
                            iname = item.get('name', '')
                            ipath = item.get('path', '')
                            if itype == 'blob' and es_trampa_bf3(iname):
                                raw_url = f"https://gitlab.com/{ns}/-/raw/{branch}/{ipath}"
                                sha256 = descargar_y_hash(raw_url)
                                if sha256:
                                    guardar_hash(sha256, iname, f"GitLab: {ns}")
                                    encontrados += 1
                            elif itype == 'tree' and depth < 2:
                                cola.append((ipath, depth + 1))
                        time.sleep(1)
            except:
                pass
            time.sleep(2)
    except:
        pass


def buscar_malwarebazaar_bf3():
    global current_search
    for tag in TAGS_MALWAREBAZAAR:
        if not scanning_active:
            break
        current_search = f"MalwareBazaar BF3: {tag}"
        try:
            url = "https://mb-api.abuse.ch/api/v1/"
            payload = {"query": "get_taginfo", "tag": tag, "limit": 300}
            r = requests.post(url, data=payload, timeout=30)
            r.raise_for_status()
            data = r.json()
            if data.get("query_status") != "ok":
                continue
            muestras = data.get("data", [])
            count = 0
            for muestra in muestras:
                nombre = muestra.get("file_name", "")
                sha256 = muestra.get("sha256_hash", "")
                if sha256 and len(sha256) == 64 and es_trampa_bf3(nombre):
                    guardar_hash(sha256, nombre, f"MalwareBazaar ({tag})")
                    count += 1
            logging.info(f"[MalwareBazaar] Tag '{tag}' -> {count} trampas BF3")
            time.sleep(2)
        except:
            pass


def buscar_urlhaus_bf3():
    global current_search
    current_search = "URLhaus: trampas BF3"
    try:
        url = "https://urlhaus.abuse.ch/downloads/recent/"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        count = 0
        for line in r.text.split('\n'):
            if line.startswith('#') or not line.strip():
                continue
            parts = line.split(',')
            if len(parts) < 7:
                continue
            threat = parts[4].lower() if len(parts) > 4 else ""
            filename = parts[5].lower() if len(parts) > 5 else ""
            sha256 = parts[6] if len(parts) > 6 else ""
            # Buscar malware relacionado con juegos/BF3
            if sha256 and len(sha256) == 64:
                if es_trampa_bf3(filename):
                    guardar_hash(sha256, filename, f"URLhaus ({threat})")
                    count += 1
        logging.info(f"[URLhaus] {count} trampas BF3 encontradas")
    except:
        pass


def buscar_especifico_bf3(nombre: str):
    global current_search
    current_search = f"Búsqueda BF3: {nombre}"
    logging.info(f"Buscando específicamente BF3: {nombre}")
    
    buscar_github_codigo_bf3(f"{nombre}+extension:dll")
    time.sleep(2)
    buscar_github_codigo_bf3(f"{nombre}+extension:exe")
    time.sleep(2)
    buscar_github_codigo_bf3(f"{nombre}+bf3+extension:dll")
    time.sleep(3)
    buscar_github_repos_bf3(nombre)
    time.sleep(3)
    buscar_gitlab_bf3(nombre)
    time.sleep(2)
    
    try:
        url = "https://mb-api.abuse.ch/api/v1/"
        payload = {"query": "get_file_info", "search_term": nombre, "limit": 50}
        r = requests.post(url, data=payload, timeout=20)
        if r.status_code == 200:
            for muestra in r.json().get("data", []):
                sha256 = muestra.get("sha256_hash", "")
                fname = muestra.get("file_name", nombre)
                if sha256 and len(sha256) == 64 and es_trampa_bf3(fname):
                    guardar_hash(sha256, fname, f"MalwareBazaar ({nombre})")
    except:
        pass


# ============================================
# COMANDOS TELEGRAM
# ============================================

@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    ayuda = """
🎮 *BF3 Cheat Hunter*

Bot exclusivo para detectar trampas de *Battlefield 3*

*Comandos:*
/status - Estado del escaneo
/stats - Estadísticas
/hashes - Descargar hashes
/buscar <nombre> - Buscar trampa BF3
/pausar - Pausar
/reanudar - Reanudar
/ratelimit - Ver límite GitHub

📁 Envía un .exe/.dll para verificar
"""
    bot.reply_to(message, ayuda, parse_mode="Markdown")


@bot.message_handler(commands=['status'])
def cmd_status(message):
    status = (
        f"🎮 *BF3 Cheat Hunter*\n\n"
        f"🔍 *Buscando:* {current_search}\n"
        f"📁 *Trampas BF3:* {total_found}\n"
        f"⏰ *Último:* {last_update}\n"
        f"🟢 *Activo:* {'Sí' if scanning_active else 'No'}\n"
        f"📊 *GitHub:* {github_remaining} req"
    )
    bot.reply_to(message, status, parse_mode="Markdown")


@bot.message_handler(commands=['ratelimit'])
def cmd_ratelimit(message):
    wait = max(0, github_reset_time - time.time())
    info = (
        f"📊 *GitHub Rate Limit*\n\n"
        f"🔄 *Restantes:* {github_remaining} requests\n"
        f"⏰ *Se resetea en:* {wait:.0f} segundos\n"
        f"🔑 *Token configurado:* {'Sí' if GITHUB_TOKEN else 'No'}\n\n"
        f"{'💡 Sin token: 60 req/hora\n💡 Con token: 5000 req/hora' if not GITHUB_TOKEN else '✅ Usando token para límite extendido'}"
    )
    bot.reply_to(message, info, parse_mode="Markdown")


@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    stats = (
        f"📈 *Estadísticas*\n\n"
        f"🔐 *Total hashes únicos:* {len(hashes_set)}\n"
        f"📅 *Fecha inicio:* {datetime.now().strftime('%Y-%m-%d')}\n"
        f"📊 *GitHub rate:* {github_remaining} restantes"
    )
    bot.reply_to(message, stats, parse_mode="Markdown")


@bot.message_handler(commands=['hashes'])
def cmd_hashes(message):
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
    try:
        partes = message.text.split(maxsplit=1)
        if len(partes) < 2:
            bot.reply_to(message, "⚠️ Uso: /buscar <nombre_proceso>")
            return
        nombre = partes[1].strip()
        bot.reply_to(message, f"🔍 Buscando '{nombre}' en BF3...")
        threading.Thread(target=buscar_especifico_bf3, args=(nombre,), daemon=True).start()
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")


@bot.message_handler(commands=['pausar'])
def cmd_pausar(message):
    global scanning_active
    scanning_active = False
    bot.reply_to(message, "⏸️ Pausado")


@bot.message_handler(commands=['reanudar'])
def cmd_reanudar(message):
    global scanning_active
    scanning_active = True
    bot.reply_to(message, "▶️ Reanudado")


@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        doc = message.document
        fname = doc.file_name.lower()
        if not fname.endswith(('.exe', '.dll', '.sys', '.asi')):
            bot.reply_to(message, "⚠️ Solo .exe/.dll/.sys/.asi")
            return
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)
        sha256 = hashlib.sha256(downloaded).hexdigest()
        existe = sha256 in hashes_set
        
        es_bf3 = es_trampa_bf3(fname)
        
        resp = (
            f"📁 *Archivo:* `{doc.file_name}`\n"
            f"📏 *Tamaño:* {doc.file_size:,} bytes\n"
            f"🔐 *SHA-256:*\n`{sha256}`\n"
            f"🎮 *BF3 Cheat:* {'⚠️ SÍ' if es_bf3 else '❌ No detectado'}\n"
            f"📊 *En BD:* {'⚠️ SÍ' if existe else '✅ No'}\n\n"
        )
        if existe:
            resp += "🚨 *TRAMPA BF3 CONOCIDA*"
        elif es_bf3:
            resp += "⚠️ *Parece trampa BF3. Envía /agregar para registrar*"
            msg = bot.reply_to(message, resp, parse_mode="Markdown")
            bot.register_next_step_handler(msg, lambda m: agregar_bf3(m, sha256, doc.file_name))
            return
        else:
            resp += "✅ *No parece trampa BF3*"
        bot.reply_to(message, resp, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")


def agregar_bf3(message, sha256: str, nombre: str):
    if message.text and '/agregar' in message.text.lower():
        if guardar_hash(sha256, nombre, "Manual Telegram"):
            bot.reply_to(message, f"✅ Trampa BF3 registrada:\n`{sha256}`", parse_mode="Markdown")
        else:
            bot.reply_to(message, "ℹ️ Ya existía")
    else:
        bot.reply_to(message, "❌ Cancelado")


# ============================================
# ESCANEO CONTINUO BF3
# ============================================

def escaneo_continuo_bf3():
    global last_update, scanning_active
    logging.info("Iniciando escaneo BF3 continuo...")
    try:
        bot.send_message(ADMIN_CHAT_ID, 
            "🎮 *BF3 Cheat Hunter activo*\nEscaneando trampas de Battlefield 3...",
            parse_mode="Markdown")
    except:
        pass
    
    ciclo = 0
    while True:
        if not scanning_active:
            time.sleep(10)
            continue
        
        ciclo += 1
        logging.info(f"=== Ciclo BF3 #{ciclo} (GitHub: {github_remaining} req) ===")
        
        # Fase 1: GitHub Code - búsquedas BF3 específicas
        logging.info("[Fase 1] GitHub Code BF3...")
        for query in CODIGO_BF3:
            if not scanning_active or github_remaining <= 3:
                break
            buscar_github_codigo_bf3(query)
            last_update = datetime.now().strftime("%H:%M:%S")
            time.sleep(5)
        
        # Fase 2: GitHub Repos BF3
        logging.info("[Fase 2] GitHub Repos BF3...")
        for query in REPOS_BF3[:6]:
            if not scanning_active or github_remaining <= 8:
                break
            buscar_github_repos_bf3(query)
            last_update = datetime.now().strftime("%H:%M:%S")
            time.sleep(10)
        
        # Esperar si rate limit
        if github_remaining <= 3:
            wait = max(0, github_reset_time - time.time() + 10)
            if wait > 0:
                logging.warning(f"[Rate Limit] Esperando {wait:.0f}s")
                time.sleep(wait)
        
        # Fase 3: GitLab BF3
        logging.info("[Fase 3] GitLab BF3...")
        for query in REPOS_BF3[:6]:
            if not scanning_active:
                break
            buscar_gitlab_bf3(query)
            last_update = datetime.now().strftime("%H:%M:%S")
            time.sleep(5)
        
        # Fase 4: MalwareBazaar BF3
        logging.info("[Fase 4] MalwareBazaar BF3...")
        buscar_malwarebazaar_bf3()
        last_update = datetime.now().strftime("%H:%M:%S")
        
        # Fase 5: URLhaus BF3
        logging.info("[Fase 5] URLhaus BF3...")
        buscar_urlhaus_bf3()
        last_update = datetime.now().strftime("%H:%M:%S")
        
        logging.info(f"=== Ciclo BF3 #{ciclo} completado. Total: {total_found} ===")
        
        # Esperar 10 minutos
        time.sleep(600)


def iniciar_bot():
    while True:
        try:
            bot.delete_webhook(drop_pending_updates=True)
            time.sleep(1)
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            logging.error(f"Error bot: {e}")
            time.sleep(30)

if __name__ == "__main__":
    os.makedirs("/app", exist_ok=True)
    cargar_hashes()
    if not os.path.exists(HASH_FILE):
        open(HASH_FILE, 'w').close()
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, 'w').close()
    
    threading.Thread(target=escaneo_continuo_bf3, daemon=True).start()
    logging.info("🎮 BF3 Cheat Hunter iniciado")
    iniciar_bot()
ENDOFFILE

echo "✅ main.py creado - Específico para Battlefield 3"
