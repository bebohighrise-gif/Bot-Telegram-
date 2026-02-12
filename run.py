import os, threading, requests
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import yt_dlp

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Vivo con Parche PoToken"

# --- CONFIGURACIÓN DEL BOT ---
TOKEN = "8283445971:AAFx7r0rbHyLUt9YS46cZL2sghKAzZ4wFk0"

async def descargar_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    chat_id = update.message.chat_id
    
    # Parche para saltar el "Sign in" en servidores
    ydl_opts = {
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
        'outtmpl': '%(title)s.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'tv'], # Clientes con menos restricciones
                'player_skip': ['webpage', 'configs'],
                'po_token': ['web+https://www.youtube.com'] # Intento de token básico
            }
        },
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }

    status = await update.message.reply_text("🕵️ Bypassing YouTube... bajando 1080p")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename): filename = os.path.splitext(filename)[0] + ".mp4"

        with open(filename, 'rb') as video:
            await context.bot.send_video(chat_id=chat_id, video=video, caption=f"✅ {info.get('title')}")
        
        os.remove(filename)
        await status.delete()
    except Exception as e:
        await update.message.reply_text(f"❌ YouTube detectó el servidor. Error: {str(e)[:100]}")

if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000))), daemon=True).start()
    Application.builder().token(TOKEN).build().add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, descargar_video)).run_polling()
                
