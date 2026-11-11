# Rust 133 Dev Blog — Bot de comunidad

Bot asíncrono basado en `python-telegram-bot` v20+ para administrar el grupo de Rust 133 Dev Blog.

## Incluye

- Administradores dinámicos: `/addadmin`, `/deladmin`, `/listadmins`.
- Revisión de enlaces con persistencia, botones **Validar** y **Expulsar**, prevención de dobles resoluciones y `/pendientes`.
- Anuncios privados con texto o respuesta a multimedia mediante `/anuncio`.
- Moderación de enlaces y multimedia con `/moderacion on|off`.
- `/ban`, `/kick`, `/mute`, `/unmute`, `/warn`; tres advertencias producen baneo.
- Tickets privados: `/soporte`, `/tickets`, botones para atender/cerrar y respuestas del equipo.
- Traducción automática al español de texto del grupo mediante `deep-translator`.
- `/reglas`, `/setreglas`, `/devblog` y `/wipe` con recordatorio privado.
- Bienvenida configurable mediante `/bienvenida on|off` y `/setbienvenida`.
- Persistencia JSON atómica protegida por `asyncio.Lock`.

## Instalación

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Variables de entorno

```bash
export TELEGRAM_TOKEN='TOKEN_DE_BOTFATHER'
export GROUP_ID='-1001234567890'
export ADMIN_IDS='123456789,987654321'
export DATA_DIR='/ruta/persistente/rust133-data'
```

`ADMIN_IDS` es la semilla inicial. Los administradores añadidos con `/addadmin` se guardan en `admins.json`. Todos los administradores deben abrir el chat privado del bot y usar `/start` al menos una vez para recibir avisos de enlaces y tickets.

## Permisos y BotFather

Añade el bot como administrador del grupo con permisos para borrar mensajes, restringir miembros y banear. Desactiva Privacy Mode en BotFather para que pueda observar mensajes del grupo. Para que el bot pueda enviar notificaciones privadas, cada admin debe iniciar el bot primero.

## Ejecutar

```bash
python bot.py
# o
python main.py
```

Los archivos JSON se crean en `DATA_DIR`: `admins.json`, `pending_links.json`, `resolved_links.json`, `warns.json`, `tickets.json`, `tickets_cerrados.json`, `welcome.json`, `wipe_config.json`, `encuestas.json`, `settings.json` y `rules.txt`. Haz copias de seguridad de ese directorio y no lo subas al repositorio.

## Comandos principales

Usuarios: `/help`, `/reglas`, `/devblog`, `/wipe`, `/wipe recordatorio`, `/soporte`.

Administradores: `/addadmin ID`, `/deladmin ID`, `/listadmins`, `/anuncio`, `/pendientes`, `/moderacion on|off`, `/ban ID`, `/kick ID`, `/mute ID MIN`, `/unmute ID`, `/warn ID`, `/tickets`, `/bienvenida on|off`, `/setbienvenida texto`, `/setreglas texto`, `/setwipe DD/MM/YYYY HH:MM`.

## Seguridad

No guardes el token en el código. La aprobación de enlaces, tickets y botones comprueba el ID del administrador y el estado persistente antes de ejecutar acciones. `/addadmin` y `/deladmin` aceptan IDs numéricos: Telegram no permite resolver de manera segura cualquier `@username` si el usuario nunca interactuó con el bot.
