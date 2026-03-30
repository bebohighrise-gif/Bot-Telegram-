# BF3 Cheat Hunter 🛡️

Sistema de detección de trampas para Battlefield 3 con bot de Telegram.

## Características

- 🔍 Escaneo continuo 24/7 en múltiples fuentes
- 📱 Bot de Telegram para notificaciones y gestión
- 🔐 Generación de hashes SHA-256
- 📁 Análisis de archivos .exe/.dll

## Fuentes de Búsqueda

- GitHub (repositorios de cheats)
- GitLab (proyectos sospechosos)
- MalwareBazaar (muestras de malware)
- HybridAnalysis (sandbox público)

## Comandos del Bot

| Comando | Descripción |
|---------|-------------|
| `/help` | Muestra ayuda |
| `/status` | Estado actual del escaneo |
| `/stats` | Estadísticas detalladas |
| `/hashes` | Descarga archivo de hashes |
| `/buscar <nombre>` | Busca trampa específica |
| `/pausar` | Pausa el escaneo |
| `/reanudar` | Reanuda el escaneo |

## Archivos

- `hashes.txt` - Hashes SHA-256 (uno por línea)
- `search_log.txt` - Log detallado de trampas encontradas
- `bot.log` - Logs del sistema

## Instalación

```bash
pip install -r requirements.txt
python main.py
```

## Configuración

Edita las variables en `main.py`:
- `TELEGRAM_TOKEN` - Token del bot
- `ADMIN_CHAT_ID` - ID del chat para notificaciones
