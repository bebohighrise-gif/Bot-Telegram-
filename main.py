import threading
import time
import requests
import hashlib
import os
import json
import logging
from flask import Flask, render_template_string
from datetime import datetime

# --- CONFIGURACIÓN Y MEMORIA ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

ESTADO_BOT = {"buscando_en": "Iniciando...", "total_hashes": 0, "ultima_actualizacion": "-"}
LISTA_TRAMPAS = []
ARCHIVO_REPORTES = "lista_trampas.json"

data_lock = threading.Lock()

# --- TOKENS ---
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", None)
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", None)
# MalwareBazaar NO requiere API key

HEADERS_GITHUB = {'Authorization': f'token {GITHUB_TOKEN}'} if GITHUB_TOKEN else {}
HEADERS_GITLAB = {'PRIVATE-TOKEN': GITLAB_TOKEN} if GITLAB_TOKEN else {}

# Términos de búsqueda exclusivos de BF3
TERMINOS_BF3 = [
    "battlefield 3 cheat",
    "bf3 hack dll",
    "bf3 injector exe",
    "battlefield 3 aimbot",
    "bf3 wallhack",
    "bf3 silent aim",
    "bf3 esp hack",
    "battlefield 3 trainer",
]

# Tags que MalwareBazaar usa para herramientas de cheating/injectors relacionados a BF3
TAGS_MALWAREBAZAAR = ["injector", "game-hack", "bf3", "battlefield"]

def inicializar_lista():
    global LISTA_TRAMPAS
    if os.path.exists(ARCHIVO_REPORTES):
        try:
            with open(ARCHIVO_REPORTES, "r", encoding="utf-8") as f:
                LISTA_TRAMPAS = json.load(f)
            logging.info(f"Lista cargada: {len(LISTA_TRAMPAS)} entradas.")
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Error al cargar {ARCHIVO_REPORTES}: {e}")
            LISTA_TRAMPAS = []
    with data_lock:
        ESTADO_BOT["total_hashes"] = len(LISTA_TRAMPAS)

def guardar_lista():
    try:
        with open(ARCHIVO_REPORTES, "w", encoding="utf-8") as f:
            json.dump(LISTA_TRAMPAS, f, indent=4)
    except IOError as e:
        logging.error(f"Error al guardar {ARCHIVO_REPORTES}: {e}")

def registrar_trampa(sha256, md5, nombre, link, fuente):
    """Registra un nuevo hash si no existe ya."""
    with data_lock:
        if not any(t['sha256'] == sha256 for t in LISTA_TRAMPAS):
            tipo = "DLL" if nombre.lower().endswith(".dll") else "EXE"
            nueva = {
                "fecha":  datetime.now().strftime("%Y-%m-%d %H:%M"),
                "tipo":   tipo,
                "sha256": sha256,
                "md5":    md5,
                "nombre": nombre,
                "link":   link,
                "fuente": fuente,
            }
            LISTA_TRAMPAS.insert(0, nueva)
            ESTADO_BOT["total_hashes"] = len(LISTA_TRAMPAS)
            guardar_lista()
            logging.info(f"[+] Nuevo hash [{fuente}]: {nombre} | SHA256: {sha256}")
        else:
            logging.info(f"[=] Ya existe: {nombre} ({sha256})")

def calcular_hashes(url):
    """Descarga un archivo y devuelve (sha256, md5) o (None, None) si falla."""
    try:
        r = requests.get(url, stream=True, timeout=20)
        r.raise_for_status()
        sha256 = hashlib.sha256()
        md5    = hashlib.md5()
        for chunk in r.iter_content(chunk_size=8192):
            sha256.update(chunk)
            md5.update(chunk)
        return sha256.hexdigest(), md5.hexdigest()
    except Exception as e:
        logging.warning(f"Error descargando {url}: {e}")
        return None, None

# ─────────────────────────────────────────
# FUENTE 1: GITHUB
# ─────────────────────────────────────────
def buscar_github(query):
    response = None
    try:
        url = f"https://api.github.com/search/repositories?q={query.replace(' ', '+')}&sort=updated"
        response = requests.get(url, headers=HEADERS_GITHUB, timeout=15)
        response.raise_for_status()
        for repo in response.json().get('items', []):
            repo_name = repo.get('full_name', 'N/A')
            try:
                c_url = repo['contents_url'].replace('{+path}', '')
                cr = requests.get(c_url, headers=HEADERS_GITHUB, timeout=15)
                cr.raise_for_status()
                archivos = cr.json()
                if isinstance(archivos, list):
                    for f in archivos:
                        if f['type'] == 'file' and f['name'].lower().endswith(('.dll', '.exe')):
                            sha256, md5 = calcular_hashes(f['download_url'])
                            if sha256:
                                registrar_trampa(sha256, md5, f['name'], f['download_url'], "GitHub")
            except Exception as e:
                logging.warning(f"[GitHub] Error en repo {repo_name}: {e}")
    except requests.exceptions.RequestException as e:
        logging.error(f"[GitHub] Error buscando '{query}': {e}")
        if (response is not None and response.status_code == 403 and
                int(response.headers.get('X-RateLimit-Remaining', 1)) == 0):
            reset_time = int(response.headers.get('X-RateLimit-Reset', time.time()))
            sleep_dur = max(0, reset_time - time.time()) + 60
            logging.warning(f"[GitHub] Rate limit. Esperando {sleep_dur:.0f}s.")
            time.sleep(sleep_dur)

# ─────────────────────────────────────────
# FUENTE 2: GITLAB
# ─────────────────────────────────────────
def buscar_gitlab(query):
    try:
        url = f"https://gitlab.com/api/v4/projects?search={query.replace(' ', '+')}&order_by=last_activity_at"
        r = requests.get(url, headers=HEADERS_GITLAB, timeout=15)
        r.raise_for_status()
        for proyecto in r.json():
            pid = proyecto.get('id')
            nombre_proj = proyecto.get('name_with_namespace', 'N/A')
            try:
                tree_url = f"https://gitlab.com/api/v4/projects/{pid}/repository/tree"
                tr = requests.get(tree_url, headers=HEADERS_GITLAB, timeout=15)
                tr.raise_for_status()
                for item in tr.json():
                    if item.get('type') == 'blob' and item['name'].lower().endswith(('.dll', '.exe')):
                        branch = proyecto.get('default_branch', 'main')
                        raw_url = f"https://gitlab.com/{proyecto['path_with_namespace']}/-/raw/{branch}/{item['name']}"
                        sha256, md5 = calcular_hashes(raw_url)
                        if sha256:
                            registrar_trampa(sha256, md5, item['name'], raw_url, "GitLab")
            except Exception as e:
                logging.warning(f"[GitLab] Error en proyecto {nombre_proj}: {e}")
    except requests.exceptions.RequestException as e:
        logging.error(f"[GitLab] Error buscando '{query}': {e}")

# ─────────────────────────────────────────
# FUENTE 3: MALWAREBAZAAR (gratuita, sin API key)
# https://bazaar.abuse.ch/api/
# Busca por tag y filtra nombres relacionados a BF3
# ─────────────────────────────────────────
def buscar_malwarebazaar(tag):
    try:
        url = "https://mb-api.abuse.ch/api/v1/"
        payload = {
            "query": "get_taginfo",
            "tag": tag,
            "limit": 50
        }
        r = requests.post(url, data=payload, timeout=20)
        r.raise_for_status()
        data = r.json()

        if data.get("query_status") != "ok":
            logging.info(f"[MalwareBazaar] Sin resultados para tag '{tag}'.")
            return

        for muestra in data.get("data", []):
            nombre = muestra.get("file_name", "desconocido")
            sha256 = muestra.get("sha256_hash", "")
            md5    = muestra.get("md5_hash", "")
            link   = f"https://bazaar.abuse.ch/sample/{sha256}/"

            if not nombre.lower().endswith(('.dll', '.exe')):
                continue
            if sha256:
                registrar_trampa(sha256, md5, nombre, link, "MalwareBazaar")

    except requests.exceptions.RequestException as e:
        logging.error(f"[MalwareBazaar] Error con tag '{tag}': {e}")

# ─────────────────────────────────────────
# HILO PRINCIPAL DEL RASTREADOR
# ─────────────────────────────────────────
def rastreador_24_7():
    while True:
        # GitHub y GitLab: buscar por términos BF3
        for query in TERMINOS_BF3:
            with data_lock:
                ESTADO_BOT["buscando_en"] = f"GitHub/GitLab: {query}"
                ESTADO_BOT["ultima_actualizacion"] = datetime.now().strftime("%H:%M:%S")

            logging.info(f"--- Buscando: '{query}' ---")
            buscar_github(query)
            time.sleep(10)
            buscar_gitlab(query)
            time.sleep(30)

        # MalwareBazaar: buscar por tags
        for tag in TAGS_MALWAREBAZAAR:
            with data_lock:
                ESTADO_BOT["buscando_en"] = f"MalwareBazaar: {tag}"
                ESTADO_BOT["ultima_actualizacion"] = datetime.now().strftime("%H:%M:%S")

            logging.info(f"--- MalwareBazaar tag: '{tag}' ---")
            buscar_malwarebazaar(tag)
            time.sleep(15)

        logging.info("Ciclo completo. Esperando 1 hora...")
        time.sleep(3600)

# --- INTERFAZ WEB ---
HTML_UI = """
<!DOCTYPE html>
<html>
<head>
    <title>Nex-Host Anti-Cheat Panel</title>
    <style>
        body { background: #0a0a0a; color: #eee; font-family: sans-serif; padding: 20px; }
        .card { background: #1a1a1a; padding: 15px; border-radius: 8px; border-left: 4px solid #ff00ff;
                margin-bottom: 20px; display: inline-block; min-width: 200px; margin-right: 15px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background: #333; color: #00ffcc; padding: 12px; text-align: left; }
        td { padding: 12px; border-bottom: 1px solid #222; font-size: 13px; }
        .btn { background: #ff00ff; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px; }
        .hash { font-family: monospace; color: #aaa; font-size: 11px; }
        .fuente-github       { color: #58a6ff; font-weight: bold; }
        .fuente-gitlab       { color: #fc6d26; font-weight: bold; }
        .fuente-malwarebazaar{ color: #f5a623; font-weight: bold; }
    </style>
    <meta http-equiv="refresh" content="60">
</head>
<body>
    <h1>🛡️ Anti-Cheat Intelligence — Battlefield 3</h1>
    <div class="card"><h3>Hashes Guardados</h3><p style="font-size:24px;margin:0;color:#00ffcc;">{{ stats.total_hashes }}</p></div>
    <div class="card"><h3>Buscando en:</h3><p style="margin:0;">{{ stats.buscando_en }}</p></div>
    <div class="card"><h3>Última Actualización:</h3><p style="margin:0;">{{ stats.ultima_actualizacion }}</p></div>

    <table>
        <tr>
            <th>Fecha</th><th>Tipo</th><th>Archivo</th>
            <th>SHA256</th><th>MD5</th><th>Fuente</th><th>Acción</th>
        </tr>
        {% for t in trampas %}
        <tr>
            <td>{{ t.fecha }}</td>
            <td><b>{{ t.tipo }}</b></td>
            <td>{{ t.nombre }}</td>
            <td class="hash">{{ t.sha256 }}</td>
            <td class="hash">{{ t.md5 }}</td>
            <td class="fuente-{{ t.fuente | lower }}">{{ t.fuente }}</td>
            <td><a href="{{ t.link }}" class="btn" target="_blank">Ver</a></td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route('/')
def index():
    with data_lock:
        trampas_para_mostrar = list(LISTA_TRAMPAS)
        estado_para_mostrar  = dict(ESTADO_BOT)
    return render_template_string(HTML_UI, stats=estado_para_mostrar, trampas=trampas_para_mostrar)

if __name__ == "__main__":
    inicializar_lista()
    threading.Thread(target=rastreador_24_7, daemon=True).start()
    app.run(host='0.0.0.0', port=8080)
