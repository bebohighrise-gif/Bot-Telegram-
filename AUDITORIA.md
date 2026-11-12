# Auditoría de Bot-Telegram- (GAMAER CITY)

Revisión completa de `bot.py` (1172 líneas), `main.py`, configuración, README y tests, con análisis estático (pyflakes, bandit), lectura línea a línea y pruebas nuevas. Estado: **corregido en la rama `hardening`** (44 pruebas, pyflakes y bandit sin avisos, probado con python-telegram-bot 21.11 y 22.8).

No se pudo probar contra Telegram real (no hay token ni red hacia Telegram en el entorno de revisión): ver la lista de comprobación manual al final.

## Críticos / altos

| # | Hallazgo | Corrección |
|---|---|---|
| 1 | **Token filtrado en los logs**: `httpx` registra la URL con el token a nivel INFO (el valor por defecto) | `httpx`, `httpcore` y `telegram.request` fijados en WARNING |
| 2 | **Lista de enlaces permitidos evadible**: `lstrip("www.")` recorta caracteres, así que `wfacepunch.com` pasaba como `facepunch.com`; también `facepunch.com@evil.com` y `evil.com\@facepunch.com` | Análisis con `urllib.parse`, rechazo de userinfo/barra invertida/esquemas no http(s) |
| 3 | **Enlaces ocultos sin moderar**: texto con hipervínculo y dominios sin esquema (`t.me/…`) no coincidían con la regex | Se leen las entidades `url` y `text_link` de Telegram |
| 4 | **Cualquier admin podía crear/quitar admins y cambiar roles**; el sistema de roles (`has_permission`) estaba definido pero nunca se usaba y `/mod`, `/support`, `/announcer` no daban ningún acceso | Modelo real de permisos aplicado a todos los comandos y callbacks; gestión de roles solo para el propietario; sincronía admins↔roles |
| 5 | **Un usuario silenciado podía quitarse el mute** pulsando su botón de verificación; además `/unmute` y la verificación dejaban permisos incompletos | La verificación no levanta restricciones temporales; se restauran los permisos por defecto del grupo |
| 6 | **Bienvenida + restricción repetidas en cada cambio de estado** (cualquier mute o ascenso reactivaba `new_member`) | Solo se dispara cuando alguien entra |
| 7 | **Moderación de multimedia y `/responder` rotos**: `Message.content_type` no existe en python-telegram-bot (AttributeError en cada foto/vídeo) | `message_kind()` con atributos reales |
| 8 | **Estado de `/soporte` "pegado"**: tras responder un ticket, todos los mensajes privados posteriores del admin se reenviaban al usuario; `/cerrar_ticket` no existía; `/apelar` sin texto nunca terminaba | Respuesta de un solo uso con botones Responder/Cerrar; flujo de apelación completo |
| 9 | **Admins anónimos moderados** (sus enlaces/fotos se borraban) y admins del grupo no exentos | Exención de admins anónimos, del grupo y de otros bots |
| 10 | **Spam a los admins**: todo error (incluido "Message is not modified" al pulsar dos veces un botón) avisaba a todos; doble `call.answer()` provocaba excepciones | Respuesta única a callbacks, `safe_edit`, avisos solo al propietario y limitados a 1 cada 10 min |
| 11 | **El arranque fallaba** si un admin nunca había iniciado el bot (`set_my_commands` por chat) | Tolerado y registrado |
| 12 | **Comandos de administración visibles para todos** en el menú privado (el README decía lo contrario) | Solo se registran para el equipo |

## Medios

- Traducción síncrona en el bucle de mensajes (hasta ~12 s por mensaje bloqueando moderación y callbacks): ahora en segundo plano, con límite de concurrencia, detección de idioma (no responde a textos en español) y opción `TRANSLATE_ENABLED`. Se elimina la dependencia `deep-translator`.
- `edit_message_text` con argumentos en orden incorrecto: las encuestas cerradas y el mensaje fijado **nunca se actualizaban** (el error se tragaba).
- Contador de infracciones del filtro compartido con `/warn`: dos `/warn` manuales adelantaban un baneo automático. Ahora son independientes y el baneo automático avisa al equipo.
- Confirmaciones de `/ban`/`/kick` sin caducidad; `/mute` sin minutos fallaba con un error críptico; ahora se valida (1–40320).
- Mute que solo bloqueaba texto: ahora usa `ChatPermissions.no_permissions()`.
- `JsonStore`: los valores por defecto se compartían entre llamadas (mutables), un JSON corrupto se sobrescribía sin copia, sin `fsync` ni permisos restrictivos. Condiciones de carrera entre la tarea periódica y los handlers: bloqueo global.
- Callbacks sin comprobación de permiso por rol, entradas de flujo (`/anuncio`, `/setwipe`…) aceptadas también desde el grupo y sin caducidad.
- Sorteos con `random` y ganador oculto tras "participante seleccionado": ahora `secrets` y nombre visible.
- Sin límites de frecuencia en tickets/apelaciones/reportes (spam a los admins).
- `/devblog`: `feedparser` sin timeout (podía colgar un hilo) y filtraba excepciones a los usuarios.
- `.env` obligatorio aunque las variables estuvieran en el entorno; `GROUP_ID` no numérico daba un traceback al importar; `DATA_DIR` por defecto `.` (con `.gitignore` sin `*.json`: riesgo de subir datos de usuarios).

## Bajos / mantenimiento

Código muerto (`welcome_cmd`, `tickets_cerrados.json`), botones duplicados en el teclado, teclado persistente enviado también en grupos, `@None` en avisos, `except Exception: pass` (bandit B110), README desactualizado y contradictorio (decía que el filtro nunca expulsa), `hashes.txt` vacío (eliminado). Añadidos: CI (GitHub Actions), Dockerfile con usuario no root, `requirements-dev.txt`, límites superiores de versión.

## Pendiente de decisión tuya

- `webapp/verification.html` no se usa en ningún sitio (dead code): bórralo o intégralo.
- La traducción envía mensajes a Google: informa en las reglas o desactívala.
- `MEDIA_MODERATION` borra también stickers y notas de voz de usuarios sin rol; desactívalo si no lo quieres.
- Los datos viven en JSON: para más de unos cientos de usuarios activos conviene migrar a SQLite.

## Comprobación manual recomendada (necesita Telegram real)

1. Arrancar con `BOT_OWNER_ID` y probar `/start`, `/panel`, `/testgrupo`.
2. Entrar con una cuenta de prueba: debe quedar silenciada, verse un único mensaje de bienvenida y poder verificarse.
3. Mutearla con `/mute ID 2`, pulsar su botón viejo de verificación (no debe liberarla) y `/unmute`.
4. Enviar `https://wfacepunch.com`, un texto con hipervínculo y `t.me/algo`: los tres deben ir a revisión.
5. Pulsar dos veces un botón de navegación: no debe llegar ningún aviso de error a los admins.
