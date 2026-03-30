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
# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

ESTADO_BOT = {"buscando_en": "Iniciando...", "total_hashes": 0, "ultima_actualizacion": "-"}
LISTA_TRAMPAS = []
ARCHIVO_REPORTES = "lista_trampas.json" # Cambiado a JSON para mejor estructura

# Bloqueo para proteger el acceso a LISTA_TRAMPAS y ESTADO_BOT
data_lock = threading.Lock()

# Token de GitHub (se recomienda usar variables de entorno en producción)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", None) # Obtener de variable de entorno
HEADERS = {'Authorization': f'token {GITHUB_TOKEN}'} if GITHUB_TOKEN else {}

def inicializar_lista():
    global LISTA_TRAMPAS, ESTADO_BOT
    if os.path.exists(ARCHIVO_REPORTES):
        try:
            with open(ARCHIVO_REPORTES, "r", encoding="utf-8") as f:
                LISTA_TRAMPAS = json.load(f)
            logging.info(f"Lista de trampas cargada desde {ARCHIVO_REPORTES}")
        except json.JSONDecodeError as e:
            logging.error(f"Error al decodificar JSON de {ARCHIVO_REPORTES}: {e}")
            LISTA_TRAMPAS = [] # Reiniciar si hay error en el JSON
        except IOError as e:
            logging.error(f"Error de E/S al leer {ARCHIVO_REPORTES}: {e}")
            LISTA_TRAMPAS = []
    else:
        logging.info(f"Archivo {ARCHIVO_REPORTES} no encontrado, iniciando lista vacía.")

    with data_lock:
        ESTADO_BOT["total_hashes"] = len(LISTA_TRAMPAS)

def guardar_lista():
    with data_lock:
        try:
            with open(ARCHIVO_REPORTES, "w", encoding="utf-8") as f:
                json.dump(LISTA_TRAMPAS, f, indent=4)
            logging.info(f"Lista de trampas guardada en {ARCHIVO_REPORTES}")
        except IOError as e:
            logging.error(f"Error de E/S al escribir en {ARCHIVO_REPORTES}: {e}")

# --- LÓGICA DEL RASTREADOR (Background) ---
def rastreador_24_7():
    terminos = ["bf3 injector exe", "battlefield 3 cheat dll", "bf3 silent aim hack"]
    
    while True:
        for query in terminos:
            with data_lock:
                ESTADO_BOT["buscando_en"] = query
                ESTADO_BOT["ultima_actualizacion"] = datetime.now().strftime("%H:%M:%S")
            logging.info(f"Buscando en GitHub: {query}")
            
            try:
                # Búsqueda en GitHub API (usando headers si hay token)
                api_url = f"https://api.github.com/search/repositories?q={query.replace(' ', '+')}&sort=updated"
                response = requests.get(api_url, headers=HEADERS, timeout=15)
                response.raise_for_status() # Lanza una excepción para códigos de estado HTTP erróneos
                repos = response.json().get('items', [])
                
                for repo in repos:
                    repo_name = repo.get('full_name', 'N/A')
                    logging.info(f"Procesando repositorio: {repo_name}")
                    try:
                        # Para evitar demasiadas peticiones, podríamos buscar solo en los archivos del repo principal
                        # o usar la API de búsqueda de código si la query es muy específica.
                        # Por simplicidad, mantenemos la lógica original de listar contenidos.
                        c_url = repo['contents_url'].replace('{+path}', '') # Eliminar placeholder de path
                        content_response = requests.get(c_url, headers=HEADERS, timeout=15)
                        content_response.raise_for_status()
                        archivos = content_response.json()
                        
                        if isinstance(archivos, list):
                            for f in archivos:
                                if f['type'] == 'file' and f['name'].lower().endswith(('.dll', '.exe')):
                                    procesar_archivo(f['download_url'], f['name'])
                    except requests.exceptions.RequestException as e:
                        logging.warning(f"Error al obtener contenido del repo {repo_name}: {e}")
                    except json.JSONDecodeError as e:
                        logging.warning(f"Error al decodificar JSON del contenido del repo {repo_name}: {e}")

            except requests.exceptions.RequestException as e:
                logging.error(f"Error en la búsqueda de GitHub para '{query}': {e}")
                if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers and int(response.headers['X-RateLimit-Remaining']) == 0:
                    reset_time = int(response.headers['X-RateLimit-Reset'])
                    sleep_duration = max(0, reset_time - time.time()) + 60 # Esperar hasta el reset + 1 minuto
                    logging.warning(f"Límite de tasa de GitHub alcanzado. Esperando {sleep_duration:.0f} segundos.")
                    time.sleep(sleep_duration)
            except json.JSONDecodeError as e:
                logging.error(f"Error al decodificar JSON de la respuesta de búsqueda de GitHub para '{query}': {e}")
            
            time.sleep(30) # Espera entre queries para no saturar la API
        
        logging.info("Ciclo de búsqueda completado. Esperando 1 hora para el siguiente ciclo.")
        time.sleep(3600) # Espera 1 hora para no ser bloqueado

def procesar_archivo(url, nombre):
    try:
        r = requests.get(url, stream=True, timeout=20)
        r.raise_for_status()
        
        sha256_hash = hashlib.sha256()
        md5_hash = hashlib.md5() # Nuevo: calcular MD5

        for chunk in r.iter_content(chunk_size=8192):
            sha256_hash.update(chunk)
            md5_hash.update(chunk)
        
        nuevo_sha256 = sha256_hash.hexdigest()
        nuevo_md5 = md5_hash.hexdigest() # Nuevo: hash MD5
        
        with data_lock:
            # Verificar si el hash SHA256 ya existe
            if not any(t['sha256'] == nuevo_sha256 for t in LISTA_TRAMPAS):
                fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                tipo = "DLL" if url.lower().endswith(".dll") else "EXE"
                
                nueva_trampa = {
                    "fecha": fecha_ahora, 
                    "tipo": tipo, 
                    "sha256": nuevo_sha256, # Guardar SHA256
                    "md5": nuevo_md5,     # Guardar MD5
                    "nombre": nombre, 
                    "link": url
                }
                LISTA_TRAMPAS.insert(0, nueva_trampa)
                ESTADO_BOT["total_hashes"] = len(LISTA_TRAMPAS)
                guardar_lista() # Guardar la lista cada vez que se añade una nueva trampa
                logging.info(f"[*] Nuevo hash guardado: {nombre} (SHA256: {nuevo_sha256}, MD5: {nuevo_md5})")
            else:
                logging.info(f"Hash ya existente para {nombre} (SHA256: {nuevo_sha256}). No se añade.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error al descargar o procesar archivo {url}: {e}")
    except Exception as e:
        logging.error(f"Error inesperado al procesar archivo {url}: {e}")

# --- INTERFAZ WEB ---
HTML_UI = """
<!DOCTYPE html>
<html>
<head>
    <title>Nex-Host Anti-Cheat Panel</title>
    <style>
        body { background: #0a0a0a; color: #eee; font-family: sans-serif; padding: 20px; }
        .card { background: #1a1a1a; padding: 15px; border-radius: 8px; border-left: 4px solid #ff00ff; margin-bottom: 20px; display: inline-block; min-width: 200px; margin-right: 15px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background: #333; color: #00ffcc; padding: 12px; text-align: left; }
        td { padding: 12px; border-bottom: 1px solid #222; font-size: 14px; }
        .btn { background: #ff00ff; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px; }
        .hash { font-family: monospace; color: #aaa; }
    </style>
    <meta http-equiv="refresh" content="60">
</head>
<body>
    <h1>🛡️ Anti-Cheat Intelligence (BF3)</h1>
    <div class="card"><h3>Hashes Guardados</h3><p style="font-size:24px; margin:0; color:#00ffcc;">{{ stats.total_hashes }}</p></div>
    <div class="card"><h3>Buscando en:</h3><p style="margin:0;">{{ stats.buscando_en }}</p></div>
    <div class="card"><h3>Última Actualización:</h3><p style="margin:0;">{{ stats.ultima_actualizacion }}</p></div>
    
    <table>
        <tr><th>Fecha</th><th>Tipo</th><th>Archivo</th><th>Hash SHA256</th><th>Hash MD5</th><th>Acción</th></tr>
        {% for t in trampas %}
        <tr>
            <td>{{ t.fecha }}</td>
            <td><b>{{ t.tipo }}</b></td>
            <td>{{ t.nombre }}</td>
            <td class="hash">{{ t.sha256 }}</td>
            <td class="hash">{{ t.md5 }}</td>
            <td><a href="{{ t.link }}" class="btn" target="_blank">Link Descarga</a></td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route('/')
def index():
    with data_lock:
        # Crear una copia para evitar modificar la lista mientras se itera en la plantilla
        trampas_para_mostrar = list(LISTA_TRAMPAS)
        estado_para_mostrar = dict(ESTADO_BOT)
    return render_template_string(HTML_UI, stats=estado_para_mostrar, trampas=trampas_para_mostrar)

if __name__ == "__main__":
    inicializar_lista()
    # Iniciar el rastreador en un hilo separado
    threading.Thread(target=rastreador_24_7, daemon=True).start()
      # Iniciar la aplicación Flask
    app.run(host='0.0.0.0', port=8080
