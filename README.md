# 💖 Bot Telegram tipo OnlyFans

Bot de venta de contenido exclusivo con pagos manuales y verificación por captura.

## Características

- Catálogo de packs / contenido
- Formas de pago editables por el dueño
- Usuario paga y envía captura → el bot te notifica
- Aprobación / rechazo con un solo toque
- Entrega automática del contenido al aprobar
- Panel de administración completo

## Comandos Usuario

| Comando | Descripción |
|---------|-------------|
| `/start` | Iniciar el bot |
| `/catalogo` | Ver packs disponibles |
| `/mis_compras` | Ver lo que ya compraste |
| `/ayuda` | Ayuda |

## Comandos Admin

| Comando | Descripción |
|---------|-------------|
| `/admin` | Panel de administración |
| `/set_pagos` | Actualizar formas de pago |
| `/add_pack` | Agregar nuevo pack |
| `/pendientes` | Ver pagos pendientes |
| `/stats` | Estadísticas |

## Instalación

```bash
pip install -r requirements.txt
python main.py
```

## Configuración

Edita en `main.py`:
- `TELEGRAM_TOKEN` → Token de @BotFather
- `ADMIN_ID` → Tu ID de Telegram (usa @userinfobot)

## Flujo de pago

1. Usuario elige un pack
2. Ve las formas de pago actuales
3. Realiza el pago y envía la captura al bot
4. Tú recibes notificación + botones Aprobar / Rechazar
5. Al aprobar → el contenido se entrega automáticamente
