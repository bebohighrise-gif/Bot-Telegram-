import os
import requests
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# --- WEB PARA RENDER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Cobalt Activo 24/7"

# --- LÓGICA DEL BOT ---
TOKEN = "8283445971:AAFx7r0rbHyLUt9YS46cZL2sghKAzZ4wFk0"

async def descargar_con_cobalt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url_usuario = update.message.text
    chat_id = update.message.chat_id
    
    msg = await update.message.reply_text("🚀 Procesando con Cobalt (Anti-bloqueo)...")

    # Configuración para la API de Cobalt (Calidad 1080p)
    payload = {
        "url": url_usuario,
        "videoQuality": "1080",
        "filenameStyle": "classic",
        "downloadMode": "video"
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        # Usamos la API pública de Cobalt
        r = requests.post("https://api.cobalt.tools", json=payload, headers=headers)
        data = r.json()

        # Si Cobalt nos da el link directo del video
        if "url" in data:
            video_directo = data["url"]
            await context.bot.send_video(
                chat_id=chat_id, 
                video=video_directo, 
                caption="✅ Video listo (1080p)"
            )
            await msg.delete()
        else:
            await update.message.reply_text("❌ Cobalt no pudo obtener el video. Prueba otro link.")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:50]}")

if __name__ == '__main__':
    # Iniciar servidor web para Render
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True).start()
    
    # Iniciar Bot de Telegram
    print("Bot encendido...")
    Application.builder().token(TOKEN).build().add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, descargar_con_cobalt)
    ).run_polling()
