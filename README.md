# Rust 133 Devblog — Bot de comunidad

Bot de Telegram para administrar el grupo de la comunidad: anuncios desde el chat privado del bot, moderación de usuarios, reglas, revisión de enlaces y traducción opcional al español.

## Funciones

- `/anuncio texto`: publica un anuncio en el grupo.
- `/anuncio` respondiendo a una foto, vídeo, archivo, audio o animación: copia el mensaje multimedia al grupo.
- `/wipe fecha y detalles`: publica un aviso de wipe con formato destacado.
- `/ban ID`, `/unban ID` y `/warn ID motivo`: moderación administrativa.
- `/reglas` y `/setreglas texto`: reglas configurables.
- `/enlaces off|review|auto`: política para enlaces no autorizados.
  - `review` retira el mensaje, lo registra y envía botones de **Expulsar** o **No hacer nada** a los administradores.
  - `auto` retira el mensaje y expulsa automáticamente al autor.
  - `off` no modera enlaces.
- `/permitir dominio.com`: añade un dominio permitido durante la ejecución.
- `/links`: lista enlaces pendientes de revisión.
- `/estado`: muestra el estado de configuración.
- Traducción automática opcional de mensajes que no parecen estar en español mediante Gemini.

## Requisitos y permisos

1. Crea el bot con [@BotFather](https://t.me/BotFather).
2. Desactiva **Privacy Mode** en BotFather para que el bot pueda revisar mensajes del grupo.
3. Añade el bot al grupo como administrador con permiso para borrar mensajes y restringir/banear usuarios.
4. Instala Python 3.10+.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Configuración

No guardes el token en el repositorio. Configura variables en el servicio donde ejecutarás el bot:

```bash
export TELEGRAM_TOKEN='TOKEN_DE_BOTFATHER'
export ADMIN_ID='123456789'
export GROUP_ID='-1001234567890'
export DB_FILE='/ruta/persistente/rust133bot.db'

# Opcional: varios administradores separados por comas
export ADMIN_IDS='123456789,987654321'

# Dominios permitidos, separados por comas
export ALLOWED_DOMAINS='rust.facepunch.com,facepunch.com,steamcommunity.com,store.steampowered.com'

# Traducción opcional
export TRANSLATION_ENABLED='1'
export GEMINI_API_KEY='...'
export GEMINI_MODEL='gemini-2.5-flash'
```

El modo de enlaces inicial es `review`. La base SQLite se crea de forma idempotente en `DB_FILE` y contiene registros de enlaces y acciones de moderación. Haz copias de seguridad del archivo antes de actualizarlo.

## Ejecución

```bash
TELEGRAM_TOKEN="$TELEGRAM_TOKEN" ADMIN_ID="$ADMIN_ID" GROUP_ID="$GROUP_ID" python main.py
```

Para producción, utiliza un supervisor como systemd, Docker o el proveedor de hosting elegido, con almacenamiento persistente para `DB_FILE`.

## Verificación

```bash
python -m unittest discover -s tests -v
python -m py_compile main.py
```

La prueba automática cubre extracción/clasificación de enlaces, reglas de dominios, detección básica de español y validación de configuración. La conexión real con Telegram, los permisos del grupo y la traducción externa deben comprobarse con un bot de pruebas.

## Notas de seguridad

- Nunca subas `.env`, tokens ni una base de datos con información de usuarios.
- Los usuarios administradores se autorizan por ID numérico; no se autoriza por nombre de usuario.
- Telegram debe entregar al bot permisos explícitos para borrar y expulsar; el código no puede superar permisos de Telegram.
- La traducción envía el texto del mensaje al proveedor configurado. Actívala solo si la comunidad acepta ese tratamiento.
- `/enlaces auto` es una política agresiva: úsala únicamente cuando todos los dominios desconocidos deban provocar expulsión.
