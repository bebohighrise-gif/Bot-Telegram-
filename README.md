# OnlyFans_ManagerBot — Guía completa de creación en Telegram

## 1. Crear / configurar el BOT en @BotFather

1. Abre Telegram y busca **@BotFather**
2. Envía `/newbot` (o usa el bot que ya tienes)
3. Nombre visible: `OnlyFans Manager` (o el que quieras)
4. Username: debe terminar en `bot`, ejemplo: `OnlyFans_ManagerBot`
5. Copia el **TOKEN** que te da (formato `123456:ABC-DEF...`)

### Configuraciones obligatorias en BotFather

Envía estos comandos a @BotFather:

```
/setdescription
```
Elige tu bot y pon algo como:
```
Plataforma de contenido exclusivo. Solo mayores de 18. Verificación de edad y género.
```

```
/setabouttext
```
```
OnlyFans Manager Bot - Contenido exclusivo con verificación real
```

```
/setuserpic
```
(Envía una foto de perfil del bot)

```
/setcommands
```
Pega esto:
```
start - Iniciar el bot / Start the bot
help - Ayuda / Help
```

### Activar la Mini App (muy importante)

1. En @BotFather envía `/mybots`
2. Elige tu bot
3. **Bot Settings** → **Configure Mini App**
4. **Enable Mini App**
5. Pon la URL HTTPS donde alojaste `webapp/verification.html`
   Ejemplo: `https://tuusuario.github.io/Bot-Telegram-/webapp/verification.html`

---

## 2. Grupo

Ya tienes el invite:
**https://t.me/+oMkBHSWhjf5lNTZh**

### Qué hacer con el grupo:

1. Entra al grupo con ese enlace
2. Añade el bot como **administrador**:
   - Toca el nombre del grupo → Administradores → Añadir administrador
   - Busca `@OnlyFans_ManagerBot` (o el username que pusiste)
   - Dale permisos de:
     - Eliminar mensajes
     - Banear usuarios
     - Invitar usuarios (importante para invite links)
3. Para obtener el **ID numérico** del grupo:
   - Añade temporalmente @userinfobot o @getidsbot al grupo
   - O reenvía un mensaje del grupo a @userinfobot
   - El ID suele ser negativo, ejemplo: `-1001234567890`

---

## 3. Mini App de verificación (cámara)

Archivo del repo: `webapp/verification.html`

### Cómo publicarla (elige una):

**Opción A – GitHub Pages (gratis)**
1. El archivo ya está en tu repo
2. Ve a Settings del repo → Pages
3. Source: Deploy from branch `main` / folder `/webapp` o raíz
4. La URL será algo como:
   `https://bebohighrise-gif.github.io/Bot-Telegram-/verification.html`
   (o la ruta que te salga)

**Opción B – Cloudflare Pages / Vercel / Netlify**
- Sube solo la carpeta `webapp`
- Te dan una URL HTTPS

Luego pones esa URL en:
- BotFather → Configure Mini App
- Y en `main.py` → `WEBAPP_VERIFICATION_URL = "https://..."`

---

## 4. Configurar el código (main.py)

Abre `main.py` y cambia estas líneas:

```python
TELEGRAM_TOKEN = "EL_TOKEN_QUE_TE_DIO_BOTFATHER"
ADMIN_ID = 7653419875
WEBAPP_VERIFICATION_URL = "https://TU_URL_DE_LA_MINI_APP"
```

---

## 5. Arrancar el bot

```bash
pip install -r requirements.txt
python main.py
```

Si todo está bien verás:
```
OnlyFans_ManagerBot V4 started
Admin ID: 7653419875
WebApp URL: https://...
Group: https://t.me/+oMkBHSWhjf5lNTZh
```

---

## Resumen de lo que tienes que crear/confirmar

| Qué | Dónde | Estado que debes confirmar |
|-----|-------|---------------------------|
| Bot creado | @BotFather | Username + Token |
| Nombre | OnlyFans_ManagerBot (o similar) | Listo |
| Descripción y comandos | @BotFather | /setdescription + /setcommands |
| Mini App activada | BotFather → Configure Mini App | URL HTTPS puesta |
| Archivo verification.html | Hosting HTTPS | Publicado |
| WEBAPP_VERIFICATION_URL | main.py | Misma URL que en BotFather |
| Grupo | https://t.me/+oMkBHSWhjf5lNTZh | Bot añadido como admin |
| Admin ID | 7653419875 | Ya está en el código |
| Token en main.py | main.py | Pegado correctamente |

---

## Flujo de verificación para el usuario

1. Usuario entra al bot → /start
2. Declara edad + acepta términos
3. Va a **Mi Cuenta** → **Verificación con cámara**
4. Se abre la Mini App automáticamente
5. Usa la cámara (documento + selfie)
6. Tú recibes las fotos y eliges género (Hombre / Mujer) o rechazas
7. Se asignan los badges `🔞✅` y `♂️/♀️`

---

## Si algo no abre la cámara

- La Mini App **solo funciona dentro de Telegram** (no en navegador normal)
- Debe ser URL **HTTPS**
- El usuario debe dar permiso de cámara cuando el móvil lo pida
- Prueba primero en el móvil (Telegram app)
