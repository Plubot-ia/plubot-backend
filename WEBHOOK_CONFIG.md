# Configuración del Webhook de WhatsApp Business API

## URL del Webhook en Producción
```
https://plubot-backend.onrender.com/api/wa/webhook
```

## Token de Verificación
```
5365c5e47306b5b22ddc53c33b2ec111
```

## Configuración en Facebook Developer Console

1. Ve a tu app en [Facebook Developers](https://developers.facebook.com)
2. En el panel izquierdo, selecciona **WhatsApp > Configuration**
3. En la sección **Webhooks**, haz clic en **Edit**
4. Ingresa:
   - **Callback URL**: `https://plubot-backend.onrender.com/api/wa/webhook`
   - **Verify Token**: `5365c5e47306b5b22ddc53c33b2ec111`
5. Haz clic en **Verify and Save**

## Suscripciones del Webhook

Asegúrate de suscribirte a los siguientes campos:
- `messages` - Para recibir mensajes entrantes
- `message_status` - Para recibir actualizaciones de estado
- `message_template_status_update` - Para actualizaciones de plantillas

## Prueba del Webhook

Para verificar que el webhook funciona correctamente:

```bash
curl -X GET "https://plubot-backend.onrender.com/api/wa/webhook?hub.mode=subscribe&hub.verify_token=5365c5e47306b5b22ddc53c33b2ec111&hub.challenge=test123"
```

Deberías recibir `test123` como respuesta.

## Variables de Entorno Requeridas

Asegúrate de que estas variables estén configuradas en Render:

- `FACEBOOK_APP_ID` - ID de tu app de Facebook
- `FACEBOOK_APP_SECRET` - Secret de tu app de Facebook  
- `WHATSAPP_WEBHOOK_VERIFY_TOKEN` - Token de verificación (5365c5e47306b5b22ddc53c33b2ec111)
- `WHATSAPP_REDIRECT_URI` - URL de callback para OAuth
