# OnlyFans_ManagerBot — V4

Bot tipo OnlyFans con:

- Verificación de edad/género mediante **Telegram Mini App** (cámara)
- Multilingüe (Español / Inglés según language_code del usuario)
- Pago obligatorio para ver contenido
- Badges `🔞✅` y `♂️/♀️`
- Suscripciones, panel creador, admin, reportes, etc.

## Nombre del bot
**OnlyFans_ManagerBot**

## Admin ID
El mismo que ya tenías en el repo (`7653419875`).

## Grupo
Invite: https://t.me/+oMkBHSWhjf5lNTZh  
(Añade el bot al grupo para obtener el ID numérico si lo necesitas).

## Mini App de verificación

Archivo: `webapp/verification.html`

### Cómo usarla

1. Sube `webapp/verification.html` a un hosting HTTPS (GitHub Pages, Cloudflare Pages, Vercel, Netlify, etc.).
2. En @BotFather → tu bot → Bot Settings → Configure Mini App → pon la URL de la página.
3. En el código del bot (main.py) cambia:

```python
WEBAPP_VERIFICATION_URL = "https://tu-dominio.com/verification.html"
```

4. El bot abrirá la Mini App con un botón. El usuario usa la cámara, captura documento + selfie y envía.

**Nota importante:**  
`Telegram.WebApp.sendData()` tiene límite de 4096 bytes y solo funciona si se abre con **KeyboardButton** de tipo `web_app`.  
Para fotos reales se recomienda que la Mini App suba las imágenes a tu backend o que el usuario las reenvíe al bot después de capturarlas. La versión actual deja el flujo listo y marca la solicitud como pendiente para revisión del admin.

## Multilingüe
El bot detecta `language_code` de Telegram y responde en español o inglés.

## Instalación

```bash
pip install -r requirements.txt
python main.py
```

Configura en `main.py`:

```python
TELEGRAM_TOKEN = "token_de_OnlyFans_ManagerBot"
ADMIN_ID = 7653419875
WEBAPP_VERIFICATION_URL = "https://tu-url-de-la-mini-app"
```
