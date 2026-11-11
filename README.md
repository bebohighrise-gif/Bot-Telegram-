# GAMAER CITY — Bot de comunidad

Bot asíncrono basado en `python-telegram-bot` v20+ para administrar el grupo y servidor GAMAER CITY.

## Funciones

- Administradores dinámicos: `/addadmin`, `/deladmin`, `/listadmins`.
- Revisión de enlaces con botones **Validar** y **Expulsar**, prevención de dobles resoluciones y `/pendientes`.
- Anuncios privados con texto o multimedia mediante `/anuncio`.
- Moderación configurable con `/moderacion on|off`.
- `/ban`, `/kick`, `/mute`, `/unmute` y `/warn`.
- Filtro de palabras: `/filtro on|off`, `/filtro add palabra`, `/filtro remove palabra`, `/filtro list`.
- Las palabras filtradas usan `escalate` por defecto: primera infracción, mute de 5 minutos y advertencia; segunda, mute de 20 minutos y advertencia; tercera, expulsión permanente y ban.
- También puedes elegir `warn`, `mute`, `kick` o `ban` explícitamente para una palabra.
- Respuestas automáticas configurables: `/auto on|off`, `/auto list`, `/auto add palabra respuesta`, `/auto remove palabra`.
- `/servidor` muestra únicamente la IP configurada del servidor.
- Tickets privados con `/soporte` y `/tickets`.
- Traducción automática al español.
- `/reglas`, `/setreglas`, `/devblog` y `/wipe`.
- Bienvenida configurable con `/bienvenida on|off` y `/setbienvenida`.
- Encuestas con cierre programado.
- Automatizaciones periódicas: cierre de encuestas vencidas, recordatorios de wipe y avisos de tickets inactivos.
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
export GROUP_NAME='GAMAER CITY'
export ADMIN_IDS='123456789,987654321'
export DATA_DIR='/ruta/persistente/gamaer-city-data'
```

Los administradores añadidos con `/addadmin` se guardan en `admins.json`. Todos los administradores deben abrir el chat privado del bot y usar `/start` al menos una vez para recibir avisos.

## Comandos

Usuarios: `/help`, `/reglas`, `/devblog`, `/servidor`, `/wipe`, `/wipe recordatorio`, `/soporte`.

Administradores: `/addadmin ID`, `/deladmin ID`, `/listadmins`, `/anuncio`, `/pendientes`, `/moderacion on|off`, `/setservidor IP Nombre`, `/filtro on|off`, `/filtro add palabra [escalate|warn|mute|kick|ban]`, `/filtro remove palabra`, `/filtro list`, `/auto on|off`, `/auto add palabra respuesta`, `/auto remove palabra`, `/ban ID`, `/kick ID`, `/mute ID MIN`, `/unmute ID`, `/warn ID`, `/tickets`, `/bienvenida on|off`, `/setbienvenida texto`, `/setreglas texto`, `/setwipe DD/MM/YYYY HH:MM`, `/encuesta Título | Opción 1 | Opción 2 | duracion=30m`.

Ejemplos de acciones manualmente configuradas:

```text
/filtro add phishing ban
/filtro add spam mute
/filtro add palabra_prohibida escalate
```

Si no indicas una acción, se usa `escalate`. El baneo ocurre solamente después de la tercera infracción de una palabra configurada, siguiendo la escalada definida; una palabra nueva nunca produce un ban en la primera detección.

Ejemplo de configuración del servidor:

```text
/setservidor 123.45.67.89 GAMAER CITY
```

El usuario solo verá la IP mediante `/servidor`; el bot no publica puerto ni comandos técnicos.

## Permisos y seguridad

Añade el bot como administrador con permisos para borrar mensajes, restringir miembros y banear. Desactiva Privacy Mode en BotFather. Los enlaces siempre requieren revisión mediante botones. Las coincidencias del filtro de palabras no generan expulsión automática: un administrador debe revisar cualquier sanción.

No guardes el token en el código. Haz copias de seguridad de `DATA_DIR` y no subas sus archivos JSON al repositorio.

## Ejecutar

```bash
python bot.py
# o
python main.py
```

## Funciones avanzadas

- **Verificación segura de Telegram:** los nuevos miembros quedan restringidos hasta pulsar el botón de aceptación de reglas. El bot guarda la verificación en `verified.json` y solo libera al usuario que pulsó su propio botón.
- **Apelaciones:** `/apelar motivo` en privado envía la solicitud a los administradores.
- **Registro:** las acciones relevantes se guardan en `moderation_logs.json`.
- **Tickets y reportes:** `/soporte`, `/tickets` y `/reportar USER_ID motivo`.
- **Eventos:** `/evento crear Título | fecha | detalles`, `/eventos` y `/evento cancelar ID`.
- **Sorteos:** `/sorteo crear Premio`, `/sorteos`; los usuarios participan con un botón y no pueden registrarse dos veces.
- **Calendario de wipe:** `/wipe` y `/wipes`, con fecha manual y recordatorios privados.
- **Mensaje oficial fijado:** responde a un mensaje del grupo con `/fijar` como administrador.
- **Enlaces oficiales:** `/enlaces` para usuarios y `/setenlaces discord|web|channel|donaciones URL` para administradores.
- **Panel:** `/panel` muestra botones de enlaces, tickets, reglas, servidor y mantenimiento.
- **Roles:** `/rol USER_ID admin|moderator|support|announcer|user`.
- **Mantenimiento:** `/mantenimiento on|off` bloquea mensajes normales de usuarios mientras los administradores siguen operativos.
- **Recuperación:** los errores se registran y se notifica a los administradores sin detener el polling.

El filtrado y los enlaces siguen requiriendo configuración explícita. Las sanciones graves deben revisarse conforme a las reglas de GAMAER CITY.
