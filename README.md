# 💖 Bot Telegram tipo OnlyFans (V2 Avanzado)

Plataforma de contenido exclusivo con verificación de edad, roles, suscripciones y paneles de creador/admin.

## Características principales

### Registro y Verificación
- Registro automático con Telegram
- Confirmación de mayoría de edad (18+)
- Aceptación de términos y condiciones
- Roles: **Usuario**, **Creador**, **Admin**
- Para convertirse en Creador: pago de **50 USD** + verificación de identidad (manual/admin + placeholder para Veriff)

### Menús
- Todo con botones **inline**
- Mensajes que se **editan** (no llenan el chat)
- Paginación y botón « Volver

### Suscripciones y Pagos
- Planes: Mensual / Trimestral
- Acceso automático a canal privado del creador
- Pagos: Manual (captura) + preparación para Telegram Stars
- Registro de transacciones

### Panel de Creador
- Subir contenido
- Configurar precios de suscripción
- Estadísticas de suscriptores e ingresos
- Mensajes masivos a suscriptores

### Panel Admin + Seguridad
- Baneos y desbaneos
- Reportes y moderación
- Logs de acciones
- protect_content en contenido sensible
- Anti-spam básico

## Instalación

```bash
pip install -r requirements.txt
python main.py
```

## Configuración obligatoria (main.py)

```python
TELEGRAM_TOKEN = "tu_token_de_BotFather"
ADMIN_ID = 123456789          # Tu ID (usa @userinfobot)
CREATOR_FEE = 50.0            # Precio para ser creador (USD)
PRIVATE_CHANNEL_ID = -100...  # ID del canal privado principal (opcional)
```

## Flujo de usuario

1. `/start` → Verificación de edad + Términos
2. Menú principal
3. Explorar creadores / Suscribirse
4. (Opcional) Pagar 50$ para convertirse en Creador

## Notas importantes

- La verificación de identidad de creadores está preparada para integrar **Veriff** (o similar). Actualmente se hace aprobación manual por admin.
- Telegram Stars se puede activar fácilmente cuando tengas el bot configurado para pagos.
- Usa `protect_content=True` en el contenido premium.
