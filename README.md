# 💖 Bot Telegram tipo OnlyFans — V3

## Novedades V3 (prioridad 1-5)

1. **Telegram Stars** preparado (invoices XTR)
2. **Invite links automáticos** al canal privado del creador
3. **Botón Reportar** + moderación mejorada
4. **Verificación real** con foto de documento + selfie (admin aprueba género y edad)
5. **Cancelar suscripción** + estado claro

### Verificación real
- El usuario **no elige** el sexo.
- Para obtener badges debe subir:
  1. Foto del documento (DNI/Pasaporte)
  2. Selfie sosteniendo el documento
- El **admin revisa** y asigna:
  - Edad verificada → badge `🔞✅`
  - Género verificado → badge `♂️` o `♀️`
- Sin verificación real los perfiles muestran solo declaración básica.

### Acceso al contenido
- **Solo se ve contenido si hay suscripción activa y pagada**.

### Badges en perfiles
```
🔞✅ Edad Verificada   ♂️ Género Verificado
```

## Configuración

```python
TELEGRAM_TOKEN = "tu_token"
ADMIN_ID = 123456789
CREATOR_FEE = 50.0
```

## Flujo de verificación real (creadores y usuarios que quieran badges)

1. Botón “Solicitar verificación real”
2. Envía foto del documento
3. Envía selfie con el documento
4. Admin recibe ambas fotos + botones para aprobar y elegir género
5. Se asignan los badges
