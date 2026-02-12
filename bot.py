import os, threading, requests, random, time
from flask import Flask, render_template_string, request, jsonify, send_file
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import yt_dlp

app = Flask(__name__)

TOKEN = "8283445971:AAFx7r0rbHyLUt9YS46cZL2sghKAzZ4wFk0"

# Obtener proxies públicos automáticamente
def fetch_public_proxies():
    proxies = []
    try:
        # ProxyScrape - Lista pública actualizada
        response = requests.get('https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=elite')
        if response.status_code == 200:
            proxy_list = response.text.strip().split('\n')
            for proxy in proxy_list[:20]:  # Tomar primeros 20
                if proxy:
                    proxies.append(f'http://{proxy}')
    except:
        pass
    
    try:
        # Free Proxy List - Alternativa
        response = requests.get('https://www.proxy-list.download/api/v1/get?type=http')
        if response.status_code == 200:
            proxy_list = response.text.strip().split('\n')
            for proxy in proxy_list[:10]:
                if proxy:
                    proxies.append(f'http://{proxy}')
    except:
        pass
    
    return proxies

# Cache de proxies (se actualiza cada hora)
PROXY_CACHE = {'proxies': [], 'last_update': 0}

def get_working_proxies():
    current_time = time.time()
    # Actualizar cada hora
    if current_time - PROXY_CACHE['last_update'] > 3600 or not PROXY_CACHE['proxies']:
        print("🔄 Actualizando lista de proxies...")
        PROXY_CACHE['proxies'] = fetch_public_proxies()
        PROXY_CACHE['last_update'] = current_time
        print(f"✅ {len(PROXY_CACHE['proxies'])} proxies cargados")
    
    return PROXY_CACHE['proxies']

def get_random_proxy():
    proxies = get_working_proxies()
    if proxies:
        return random.choice(proxies)
    return None

def get_random_user_agent():
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15'
    ]
    return random.choice(agents)

def cleanup_old_files():
    while True:
        try:
            if os.path.exists('downloads'):
                now = time.time()
                for filename in os.listdir('downloads'):
                    filepath = os.path.join('downloads', filename)
                    if os.path.isfile(filepath):
                        if now - os.path.getmtime(filepath) > 3600:
                            os.remove(filepath)
        except:
            pass
        time.sleep(1800)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Downloader Pro</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 600px;
            width: 100%;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 2em;
            text-align: center;
        }
        .subtitle {
            color: #666;
            text-align: center;
            margin-bottom: 30px;
            font-size: 0.9em;
        }
        .status {
            background: #e8f5e9;
            color: #2e7d32;
            padding: 10px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
            font-weight: bold;
        }
        .search-box, .url-box {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 600;
        }
        input[type="text"] {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            margin-bottom: 10px;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .btn-primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .results {
            margin-top: 30px;
            display: none;
        }
        .video-item {
            background: #f9f9f9;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .video-item img {
            width: 120px;
            border-radius: 8px;
        }
        .video-info {
            flex: 1;
        }
        .video-title {
            font-weight: bold;
            margin-bottom: 5px;
            color: #333;
        }
        .video-duration {
            color: #666;
            font-size: 0.9em;
        }
        .download-section {
            margin-top: 30px;
            display: none;
            text-align: center;
        }
        .loading {
            display: none;
            text-align: center;
            margin: 20px 0;
            color: #667eea;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            display: none;
        }
        @media (max-width: 600px) {
            .video-item {
                flex-direction: column;
                text-align: center;
            }
            .video-item img {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 YouTube Downloader</h1>
        <p class="subtitle">Descarga videos con IPs aleatorias mundiales</p>
        
        <div class="status" id="statusBar">
            🔄 Cargando proxies...
        </div>

        <div class="search-box">
            <label>🔍 Buscar en YouTube</label>
            <input type="text" id="searchInput" placeholder="Buscar videos..." onkeypress="if(event.key==='Enter')searchVideos()">
            <button class="btn btn-primary" id="searchBtn" onclick="searchVideos()">Buscar</button>
        </div>

        <div style="text-align: center; margin: 20px 0; color: #999;">- O -</div>

        <div class="url-box">
            <label>🔗 URL Directa de YouTube</label>
            <input type="text" id="urlInput" placeholder="https://youtube.com/watch?v=..." onkeypress="if(event.key==='Enter')downloadByUrl()">
            <button class="btn btn-primary" id="downloadBtn" onclick="downloadByUrl()">Descargar</button>
        </div>

        <div class="loading">
            <div class="spinner"></div>
            <p style="margin-top: 10px;">Procesando...</p>
        </div>

        <div class="results" id="results"></div>
        <div class="download-section" id="downloadSection"></div>
        <div class="error" id="error"></div>
    </div>

    <script>
        // Actualizar estado de proxies
        async function updateProxyStatus() {
            try {
                const response = await fetch('/proxy_status');
                const data = await response.json();
                const statusBar = document.getElementById('statusBar');
                if (data.proxies > 0) {
                    statusBar.innerHTML = `🔒 ${data.proxies} IPs Globales Activas | 🌐 Conexión Anónima`;
                    statusBar.style.background = '#e8f5e9';
                    statusBar.style.color = '#2e7d32';
                } else {
                    statusBar.innerHTML = '⚠️ Sin proxies - Usando IP del servidor';
                    statusBar.style.background = '#fff3e0';
                    statusBar.style.color = '#e65100';
                }
            } catch (e) {
                console.error('Error actualizando estado:', e);
            }
        }

        // Actualizar cada 30 segundos
        updateProxyStatus();
        setInterval(updateProxyStatus, 30000);

        function showLoading() {
            document.querySelector('.loading').style.display = 'block';
            document.getElementById('results').style.display = 'none';
            document.getElementById('downloadSection').style.display = 'none';
            document.getElementById('error').style.display = 'none';
            document.getElementById('searchBtn').disabled = true;
            document.getElementById('downloadBtn').disabled = true;
        }

        function hideLoading() {
            document.querySelector('.loading').style.display = 'none';
            document.getElementById('searchBtn').disabled = false;
            document.getElementById('downloadBtn').disabled = false;
        }

        function showError(msg) {
            const errorDiv = document.getElementById('error');
            errorDiv.textContent = '❌ ' + msg;
            errorDiv.style.display = 'block';
        }

        async function searchVideos() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) {
                showError('Por favor ingresa un término de búsqueda');
                return;
            }

            showLoading();

            try {
                const response = await fetch('/search', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: query})
                });

                const data = await response.json();
                hideLoading();

                if (data.error) {
                    showError(data.error);
                    return;
                }

                const resultsDiv = document.getElementById('results');
                resultsDiv.innerHTML = '<h3 style="margin-bottom: 15px;">Resultados:</h3>';
                
                data.results.forEach(video => {
                    resultsDiv.innerHTML += `
                        <div class="video-item">
                            <img src="${video.thumbnail}" alt="thumbnail" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22120%22 height=%2268%22%3E%3Crect fill=%22%23ddd%22 width=%22120%22 height=%2268%22/%3E%3C/svg%3E'">
                            <div class="video-info">
                                <div class="video-title">${video.title}</div>
                                <div class="video-duration">⏱️ ${video.duration}</div>
                            </div>
                            <button class="btn btn-primary" style="width: auto; padding: 10px 20px;" onclick="downloadVideo('${video.url}')">
                                📥 Descargar
                            </button>
                        </div>
                    `;
                });

                resultsDiv.style.display = 'block';
            } catch (error) {
                hideLoading();
                showError('Error al buscar videos. Intenta de nuevo.');
            }
        }

        async function downloadByUrl() {
            const url = document.getElementById('urlInput').value.trim();
            if (!url) {
                showError('Por favor ingresa una URL válida');
                return;
            }
            if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
                showError('Solo se aceptan URLs de YouTube');
                return;
            }
            downloadVideo(url);
        }

        async function downloadVideo(url) {
            showLoading();

            try {
                const response = await fetch('/download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url})
                });

                const data = await response.json();
                hideLoading();

                if (data.error) {
                    showError(data.error);
                    return;
                }

                const downloadDiv = document.getElementById('downloadSection');
                downloadDiv.innerHTML = `
                    <h3 style="color: #2e7d32; margin-bottom: 15px;">✅ Descarga Lista</h3>
                    <p style="margin-bottom: 15px;"><strong>${data.title}</strong></p>
                    <a href="/get_file/${data.filename}" class="btn btn-primary" style="text-decoration: none; display: inline-block;">
                        📥 Descargar Video (${data.size || 'N/A'})
                    </a>
                `;
                downloadDiv.style.display = 'block';
            } catch (error) {
                hideLoading();
                showError('Error al descargar el video. Intenta de nuevo.');
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/health')
def health():
    proxies = get_working_proxies()
    return {'status': 'ok', 'proxies': len(proxies)}, 200

@app.route('/proxy_status')
def proxy_status():
    proxies = get_working_proxies()
    return jsonify({'proxies': len(proxies)})

@app.route('/search', methods=['POST'])
def search():
    try:
        query = request.json.get('query', '').strip()
        if not query:
            return jsonify({'error': 'Búsqueda vacía'}), 400
        
        proxy = get_random_proxy()
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'user_agent': get_random_user_agent(),
            'socket_timeout': 30,
            'nocheckcertificate': True,
            'geo_bypass': True
        }
        
        if proxy:
            ydl_opts['proxy'] = proxy
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch5:{query}", download=False)
            
            videos = []
            for entry in result.get('entries', []):
                if entry:
                    videos.append({
                        'title': entry.get('title', 'Sin título'),
                        'url': f"https://youtube.com/watch?v={entry['id']}",
                        'thumbnail': entry.get('thumbnail', ''),
                        'duration': entry.get('duration_string', 'N/A')
                    })
            
            return jsonify({'results': videos})
    except Exception as e:
        return jsonify({'error': f'Error en búsqueda: {str(e)[:100]}'}), 500

@app.route('/download', methods=['POST'])
def download():
    try:
        url = request.json.get('url', '').strip()
        if not url:
            return jsonify({'error': 'URL vacía'}), 400
        
        proxy = get_random_proxy()
        
        ydl_opts = {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': True,
            'user_agent': get_random_user_agent(),
            'socket_timeout': 30,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'tv'],
                    'player_skip': ['webpage', 'configs'],
                }
            }
        }
        
        if proxy:
            ydl_opts['proxy'] = proxy
        
        os.makedirs('downloads', exist_ok=True)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                filename = os.path.splitext(filename)[0] + ".mp4"
            
            size = os.path.getsize(filename)
            size_mb = f"{size / (1024*1024):.1f} MB"
            
            return jsonify({
                'title': info.get('title', 'Video'),
                'filename': os.path.basename(filename),
                'size': size_mb
            })
    except Exception as e:
        return jsonify({'error': f'Error al descargar: {str(e)[:100]}'}), 500

@app.route('/get_file/<filename>')
def get_file(filename):
    try:
        filepath = os.path.join('downloads', filename)
        if not os.path.exists(filepath):
            return "Archivo no encontrado", 404
        
        response = send_file(filepath, as_attachment=True)
        
        @response.call_on_close
        def cleanup():
            try:
                time.sleep(2)
                if os.path.exists(filepath):
                    os.remove(filepath)
            except:
                pass
        
        return response
    except Exception as e:
        return f"Error: {str(e)}", 404

async def descargar_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = update.message.chat_id
    
    if not ('youtube.com' in url or 'youtu.be' in url):
        await update.message.reply_text("❌ Solo URLs de YouTube")
        return
    
    proxy = get_random_proxy()
    
    ydl_opts = {
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
        'outtmpl': 'telegram_%(id)s.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'tv'],
                'player_skip': ['webpage', 'configs'],
            }
        },
        'user_agent': get_random_user_agent(),
        'socket_timeout': 30,
        'nocheckcertificate': True,
        'geo_bypass': True
    }
    
    if proxy:
        ydl_opts['proxy'] = proxy

    status = await update.message.reply_text("🕵️ Descargando con IP aleatoria...")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename): 
                filename = os.path.splitext(filename)[0] + ".mp4"

        with open(filename, 'rb') as video:
            await context.bot.send_video(
                chat_id=chat_id, 
                video=video, 
                caption=f"✅ {info.get('title', 'Video')}"
            )
        
        os.remove(filename)
        await status.delete()
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}")

if __name__ == '__main__':
    # Cargar proxies al inicio
    print("🚀 Iniciando bot...")
    get_working_proxies()
    
    # Iniciar limpieza de archivos
    threading.Thread(target=cleanup_old_files, daemon=True).start()
    
    # Configurar proxy para Telegram
    proxy_config = {}
    proxy_url = get_random_proxy()
    
    if proxy_url:
        proxy_config = {'proxy_url': proxy_url}
    
    # Iniciar Flask
    threading.Thread(
        target=lambda: app.run(
            host='0.0.0.0', 
            port=int(os.environ.get("PORT", 10000))
        ), 
        daemon=True
    ).start()
    
    # Iniciar bot de Telegram
    app_builder = Application.builder().token(TOKEN)
    if proxy_config:
        app_builder = app_builder.proxy(**proxy_config)
    
    app_builder.build().add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, descargar_video)
    ).run_polling()
