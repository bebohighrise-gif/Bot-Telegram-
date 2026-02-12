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
    return "El bot está vivo y funcionando 24/7."

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- LÓGICA DEL BOT DE TELEGRAM ---
TOKEN = "TU_TOKEN_AQUÍ"

async def descargar_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    chat_id = update.message.chat_id
    
    ydl_opts = {
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
        'outtmpl': '%(title)s.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': True,
    }

    status = await update.message.reply_text("⏳ Descargando video en 1080p...")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        with open(filename, 'rb') as video:
            await context.bot.send_video(chat_id=chat_id, video=video, caption=f"✅ {info.get('title')}")
        
        os.remove(filename)
        await status.delete()
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}")

def run_bot():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, descargar_video))
    application.run_polling()

# --- LANZAMIENTO ---
if __name__ == '__main__':
    # Inicia Flask en un hilo separado
    threading.Thread(target=run_flask).start()
    # Inicia el bot de Telegram
    run_bot()
