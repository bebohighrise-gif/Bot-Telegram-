# GAMAER CITY — Bot de comunidad

Bot asíncrono (`python-telegram-bot` 21/22) para moderar y gestionar el grupo y el servidor de Rust de GAMAER CITY.
Persistencia en JSON atómico, roles con permisos, auditoría y pruebas automáticas.

## Instalación

Requiere Python 3.10 o superior.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # rellena TELEGRAM_TOKEN y GROUP_ID como mínimo
python main.py
```

El archivo `.env` es opcional si las variables ya están en el entorno (systemd, Docker, etc.). **Nunca subas `.env` ni `data/`** (el `.gitignore` ya los excluye).

### Docker

```bash
docker build -t gamaer-bot .
docker run -d --restart unless-stopped --env-file .env -v gamaer-data:/data gamaer-bot
```

## Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `TELEGRAM_TOKEN` | Sí | Token de @BotFather |
| `GROUP_ID` | Sí | ID numérico del supergrupo (`-100…`) |
| `BOT_OWNER_ID` | Recomendada | Tu ID: propietario del bot, único que gestiona roles/admins. Si falta, los de `ADMIN_IDS` son propietarios |
| `ADMIN_IDS` | No | IDs iniciales del equipo (rol `admin`) |
| `GROUP_NAME` | No | Nombre visible |
| `DATA_DIR` | No | Carpeta de datos (por defecto `./data`). Haz copias de seguridad |
| `LOG_LEVEL` | No | `INFO` por defecto |
| `TRANSLATE_ENABLED` | No | `true`/`false`. Ver *Privacidad* |
| `MEDIA_MODERATION` | No | `true`/`false`. Borra multimedia de usuarios sin rol |

Configuración del bot en Telegram: añádelo al grupo como **administrador** con permisos para borrar mensajes, restringir miembros, banear y fijar mensajes, y desactiva *Privacy Mode* en @BotFather.

## Roles y permisos

Solo el **propietario** gestiona roles (`/addadmin`, `/deladmin`, `/rol`, `/admin`, `/mod`, `/support`, `/announcer`). Un admin no puede ascender a otros.

| Rol | Puede |
|---|---|
| `owner` | Todo, incluida la gestión de roles |
| `admin` | Moderar, soporte, anuncios y configuración |
| `moderator` | Enlaces pendientes, `/ban` `/kick` `/mute` `/unmute` `/warn`, filtro de palabras, apelaciones y reportes |
| `support` | Tickets y `/responder` |
| `announcer` | `/anuncio`, `/evento`, `/sorteo`, `/encuesta` |

Los avisos privados (tickets, enlaces, apelaciones…) solo llegan a quien tiene el permiso correspondiente. Los administradores del grupo (también los anónimos) y otros bots nunca se moderan. No se puede sancionar a miembros del equipo.

## Funciones

- **Verificación de entrada:** el nuevo miembro queda silenciado hasta pulsar su botón de aceptación de reglas. Solo se dispara cuando alguien *entra*, el botón nunca levanta un silencio temporal impuesto por moderación y el mensaje de bienvenida se elimina al verificar.
- **Enlaces:** se retiran silenciosamente y pasan a revisión privada del propietario (Validar / Expulsar). No se publica ningún aviso en el grupo. Se detectan también los ocultos tras texto y los dominios sin `https://`. Solo se permiten `facepunch.com` y Steam.
- **Multimedia:** las fotos, vídeos y archivos de usuarios sin autorización se eliminan sin mensaje público; el propietario recibe el aviso privado con el usuario, tipo y mensaje.
- **Filtro de palabras** (`/filtro on|off|add|remove|list`): acción `escalate` por defecto (1.ª: mute 5 min · 2.ª: mute 20 min · 3.ª: baneo y aviso al equipo). También `warn`, `mute`, `kick`, `ban` por palabra. Contador propio, separado de los `/warn` manuales.
- **Moderación manual:** `/ban` y `/kick` piden confirmación con botones (caduca en 10 min); `/mute ID MINUTOS`, `/unmute`, `/warn` (3 = baneo). Todo queda en `moderation_logs.json`.
- **Apelaciones** (`/apelar`), **reportes** (`/reportar ID motivo`) y **tickets** (`/soporte`, `/tickets`) con límite de frecuencia.
- **Anuncios** (`/anuncio`, texto o multimedia), **eventos** con recordatorio (`/evento crear Título | 2026-11-20T19:00:00 | detalles`), **sorteos** (ganador con `secrets`), **encuestas** con cierre programado.
- **Servidor y wipe:** `/setservidor`, `/servidor`, `/setwipe DD/MM/YYYY HH:MM` (UTC), `/wipe`, `/wipe recordatorio`.
- **Respuestas automáticas** (`/auto`), reglas (`/setreglas`), enlaces oficiales (`/setenlaces`), mensaje fijado (`/fijar`), modo mantenimiento, `/devblog`, panel (`/panel`).
- **Traducción automática** al español de mensajes en otros idiomas (detecta el idioma; no responde a textos en español).
- Las bienvenidas son automáticas (acompañan a la verificación); los comandos de bienvenida manual ya no existen.
- En el chat privado se registra el menú completo de comandos para todos los usuarios, pero cada comando administrativo vuelve a validar permisos. En el grupo solo se muestran los comandos públicos.
- El arranque usa un bloqueo local para impedir dos procesos simultáneos y trata un conflicto de Telegram como error fatal de instancia, no como una actualización normal.

## Seguridad y privacidad

- El token **no se escribe en los logs** (los clientes HTTP se fijan en `WARNING`). Los errores internos no se muestran a los usuarios y solo se avisa al propietario, como mucho cada 10 minutos.
- Los archivos de datos se escriben de forma atómica con permisos `600`; si uno se corrompe se conserva una copia `*.corrupt-<fecha>` antes de reiniciarlo.
- Los handlers y las tareas periódicas se serializan con un bloqueo global para evitar pérdidas de datos.
- **Privacidad:** con `TRANSLATE_ENABLED=true`, el texto de los mensajes de usuarios sin rol se envía al servicio de traducción de Google. Infórmalo en las reglas o desactívalo.
- Los datos guardados incluyen IDs, nombres y textos de tickets/apelaciones/reportes. Aplica tu política de retención y protege `DATA_DIR`.

## Desarrollo

```bash
pip install -r requirements-dev.txt
python -m pyflakes bot.py main.py && bandit -q -r bot.py main.py && python -m pytest tests -q
```

La integración continua (`.github/workflows/ci.yml`) ejecuta lo mismo en Python 3.10 y 3.12.
