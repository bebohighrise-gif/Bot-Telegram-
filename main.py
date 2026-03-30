import threading
import time
import requests
import hashlib
import os
from flask import Flask, render_template_string
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURACIÓN Y MEMORIA ---
ESTADO_BOT = {"buscando_en": "Iniciando...", "total_hashes": 0, "ultima_actualizacion": "-"}
LISTA_TRAMPAS = []
ARCHIVO_REPORTES = "lista_trampas.txt"

def inicializar_lista():
    if os.path.exists(ARCHIVO_REPORTES):
        with open(ARCHIVO_REPORTES, "r", encoding="utf-8") as f:
            for linea in f:
                if "HASH:" in linea:
                    try:
                        fecha = linea.split("]")[0].replace("[", "")
                        nombre = linea.split("ARCHIVO: ")[1].split(" |")[0]
                        h_val = linea.split("HASH: ")[1].split(" |")[0]
                        link = linea.split("LINK: ")[1].strip()
                        tipo = "DLL" if ".dll" in nombre.lower() else "EXE"
                        
                        LISTA_TRAMPAS.append({
                            "fecha": fecha, "tipo": tipo, "hash": h_val,
                            "nombre": nombre, "link": link
                        })
                    except: continue
        ESTADO_BOT["total_hashes"] = len(LISTA_TRAMPAS)

# --- LÓGICA DEL RASTREADOR (Background) ---
def rastreador_24_7():
    terminos = ["bf3+injector+exe", "battlefield+3+cheat+dll", "bf3+silent+aim+hack"]
    
    while True:
        for query in terminos:
            ESTADO_BOT["buscando_en"] = query.replace("+", " ")
            ESTADO_BOT["ultima_actualizacion"] = datetime.now().strftime("%H:%M:%S")
            
            try:
                # Búsqueda en GitHub API
                api_url = f"https://api.github.com/search/repositories?q={query}&sort=updated"
                repos = requests.get(api_url, timeout=10).json().get('items', [])
                
                for repo in repos:
                    c_url = repo['url'] + "/contents"
                    archivos = requests.get(c_url, timeout=10).json()
                    
                    if isinstance(archivos, list):
                        for f in archivos:
                            # FILTRO ESTRICTO: Solo ejecutables y librerías
                            if f['name'].lower().endswith(('.dll', '.exe')):
                                procesar_archivo(f['download_url'], f['name'])
            except: pass
            time.sleep(15) 
        
        time.sleep(3600) # Espera 1 hora para no ser bloqueado

def procesar_archivo(url, nombre):
    try:
        r = requests.get(url, stream=True, timeout=10)
        sha256 = hashlib.sha256()
        for chunk in r.iter_content(chunk_size=8192):
            sha256.update(chunk)
        
        nuevo_hash = sha256.hexdigest()
        
        if not any(t['hash'] == nuevo_hash for t in LISTA_TRAMPAS):
            fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
            tipo = "DLL" if url.lower().endswith(".dll") else "EXE"
            
            nueva_trampa = {
                "fecha": fecha_ahora, "tipo": tipo, 
                "hash": nuevo_hash, "nombre": nombre, "link": url
            }
            LISTA_TRAMPAS.insert(0, nueva_trampa)
            ESTADO_BOT["total_hashes"] = len(LISTA_TRAMPAS)
            
            with open(ARCHIVO_REPORTES, "a", encoding="utf-8") as f:
                f.write(f"[{fecha_ahora}] TIPO: {tipo} | HASH: {nuevo_hash} | ARCHIVO: {nombre} | LINK: {url}\n")
            print(f"[*] Nuevo hash guardado: {nombre}")
    except: pass

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
    
    <table>
        <tr><th>Fecha</th><th>Tipo</th><th>Archivo</th><th>Hash SHA256</th><th>Acción</th></tr>
        {% for t in trampas %}
        <tr>
            <td>{{ t.fecha }}</td>
            <td><b>{{ t.tipo }}</b></td>
            <td>{{ t.nombre }}</td>
            <td class="hash">{{ t.hash }}</td>
            <td><a href="{{ t.link }}" class="btn" target="_blank">Link Descarga</a></td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_UI, stats=ESTADO_BOT, trampas=LISTA_TRAMPAS)

if __name__ == "__main__":
    inicializar_db = inicializar_lista()
    threading.Thread(target=rastreador_24_7, daemon=True).start()
    app.run(host='0.0.0.0', port=8080)
                        
