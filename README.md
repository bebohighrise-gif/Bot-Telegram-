# OnlyFans_ManagerBot — V9

Bot de Telegram para perfiles de creadores, planes de pago manual, contenido, moderación y solicitudes de videollamada. Esta versión mantiene SQLite y `pyTelegramBotAPI`.

> **Estado:** el código contiene pruebas automáticas básicas, pero no debe considerarse certificado ni listo para producción. Los pagos siguen siendo revisados manualmente. La cámara de la Mini App no transmite las imágenes: al iniciar la solicitud, el bot pide que el usuario adjunte documento y selfie en el chat privado.

## Requisitos

- Python 3.10 o posterior.
- Un bot creado con [@BotFather](https://t.me/BotFather).
- Un `ADMIN_ID` numérico positivo.
- Para abrir la Mini App, una URL HTTPS estable y configurada en BotFather.

## Instalación y configuración

No pegues el token en `main.py`, en el README ni en mensajes. Configura las variables en el entorno del servicio que ejecutará el bot:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

export TELEGRAM_TOKEN='token_entregado_por_BotFather'
export ADMIN_ID='123456789'
export DB_FILE='/ruta/persistente/bot.db'
# Opcionales:
export WEBAPP_VERIFICATION_URL='https://tu-dominio.example/verification.html'
export GROUP_ID='-1001234567890'
export GROUP_INVITE='https://t.me/tu_invitacion'
```

Protege el archivo de base de datos y el entorno del proceso con permisos mínimos. Si un token real se compartió o comprometió, revócalo en BotFather y crea uno nuevo.

## Ejecutar

```bash
python main.py
```

El proceso valida la configuración antes de iniciar. Para producción, ejecútalo bajo un supervisor de servicios y usa un almacenamiento persistente con copias de seguridad cifradas y probadas.

## Mini App y verificación

1. Publica `webapp/verification.html` en HTTPS y configura la misma URL en `WEBAPP_VERIFICATION_URL` y BotFather.
2. El bot abre la Mini App desde un botón de teclado de respuesta de Telegram, necesario para entregar `web_app_data`. La Mini App permite capturar y revisar fotos localmente, pero **no las sube**. La señal solo avisa al bot para pedir las imágenes por el chat privado.
3. El usuario debe adjuntar primero la foto del documento y después la selfie. El bot reenvía ambas al administrador para revisión.
4. No habilites esta función hasta definir aviso de privacidad, base legal, acceso autorizado, período de retención, proceso de borrado y protección de copias para datos de identidad. El bot no aplica todavía eliminación automática de esas fotos.

## Pruebas

```bash
. .venv/bin/activate
TELEGRAM_TOKEN='123456:TEST_ONLY' ADMIN_ID='123456789' python -m unittest discover -s tests -v
python -m py_compile main.py
pip-audit -r requirements.txt
```

El token de prueba sirve solo para cargar código y ejecutar pruebas; no permite conectarse a Telegram. `pip-audit` debe instalarse previamente si aún no está disponible (`pip install pip-audit`).

## Seguridad y operación pendientes

- Sustituir la revisión manual de capturas por un proveedor de pagos con confirmación server-side antes de otorgar acceso.
- Añadir límites de tasa, registros operativos sin datos sensibles, monitorización, gestión de errores y una estrategia probada de backup/restore.
- Definir retención y borrado de IDs de archivos de documentos y selfies, junto con controles de acceso y respuesta ante incidentes.
- No considerar `protect_content` una protección contra capturas de pantalla o redistribución.
- Antes de actualizar desde una base V4, detener el proceso y hacer una copia recuperable. La inicialización añade columnas, convierte arrays antiguos de medios en filas, elimina la restricción V4 de una suscripción por creador conservando sus filas y crea los planes de creadores antiguos usando sus precios guardados; no reemplaza ni elimina el archivo SQLite.
- Ejecutar las pruebas en cada cambio y probar manualmente los flujos de usuario y administrador con un bot de pruebas antes de desplegar.
