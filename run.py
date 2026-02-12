import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import yt_dlp

# --- CONFIGURACIÓN WEB PARA RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot de Video 1080p activo 24/7"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- LÓGICA DEL BOT DE TELEGRAM ---
TOKEN = "8283445971:AAFx7r0rbHyLUt9YS46cZL2sghKAzZ4wFk0"

async def descargar_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    chat_id = update.message.chat_id
    
    # PARCHE ANTI-BLOQUEO (Simula App de Android)
    ydl_opts = {
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
        'outtmpl': '%(title)s.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        # Configuración para saltar el "Sign in to confirm you're not a bot"
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['dash', 'hls']
            }
        },
        'user_agent': 'Mozilla/5.0 (Android 13; Mobile; rv:109.0) Gecko/114.0 Firefox/114.0'
    }

    mensaje_status = await update.message.reply_text("⏳ Procesando video en 1080p (Modo Android)...")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Asegurar extensión mp4 tras la fusión
            if not os.path.exists(filename):
                filename = os.path.splitext(filename)[0] + ".mp4"

        with open(filename, 'rb') as video:
            await context.bot.send_video(
                chat_id=chat_id, 
                video=video, 
                caption=f"✅ {info.get('title')}",
                supports_streaming=True
            )
        
        os.remove(filename) # Borrar para ahorrar espacio
        await mensaje_status.delete()

    except Exception as e:
        error_msg = str(e)
        if "Sign in" in error_msg:
            await update.message.reply_text("❌ YouTube sigue bloqueando la IP. Necesitarás subir el archivo 'cookies.txt'.")
        else:
            await update.message.reply_text(f"❌ Error: {error_msg[:100]}")

def run_bot():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, descargar_video))
    print("Bot de Telegram iniciado...")
    application.run_polling()

if __name__ == '__main__':
    # Hilo para que Render vea una web activa
    threading.Thread(target=run_flask, daemon=True).start()
    # Ejecución del bot
    run_bot()
