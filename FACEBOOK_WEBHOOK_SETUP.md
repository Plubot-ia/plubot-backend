# Configuración de Webhook en Facebook Developer Console

## Suscripciones Requeridas

Para que tu integración de WhatsApp Business funcione correctamente, debes activar las siguientes suscripciones en Facebook Developer Console:

### Suscripciones Esenciales (OBLIGATORIAS)

1. **`messages`** ✅
   - **Versión**: v23.0
   - **Función**: Recibe mensajes entrantes de los usuarios
   - **Acción**: Haz clic en "Suscribirse"

2. **`message_template_status_update`** ✅
   - **Versión**: v23.0
   - **Función**: Notificaciones sobre el estado de las plantillas de mensajes
   - **Acción**: Haz clic en "Suscribirse"

### Suscripciones Recomendadas

3. **`account_update`**
   - **Versión**: v23.0
   - **Función**: Cambios en la configuración de la cuenta
   - **Acción**: Haz clic en "Suscribirse"

4. **`phone_number_name_update`**
   - **Versión**: v23.0
   - **Función**: Cambios en el nombre del número de teléfono
   - **Acción**: Haz clic en "Suscribirse"

### Suscripciones Opcionales (según tu caso de uso)

5. **`message_echoes`**
   - **Función**: Ver los mensajes que envías (útil para debugging)
   
6. **`security`**
   - **Función**: Alertas de seguridad importantes

## Pasos para Configurar

1. Ve a: https://developers.facebook.com/apps/550833654728514/webhooks/?business_id=154131962116598

2. En la sección "Campos del webhook", busca cada campo mencionado arriba

3. Para cada campo:
   - Selecciona la versión **v23.0**
   - Haz clic en el botón **"Suscribirse"**

4. Una vez suscritos, verás el estado cambiar de "No suscritos" a "Suscritos"

## Verificación

Para verificar que todo funciona:

1. En la columna "Prueba", haz clic en **"Probar"** para el campo `messages`
2. Deberías ver una respuesta exitosa en los logs de tu servidor

## Configuración del Webhook

- **URL de devolución de llamada**: `https://plubot-backend.onrender.com/api/wa/webhook`
- **Token de verificación**: `5365c5e47306b5b22ddc53c33b2ec111`

## Notas Importantes

- La app debe estar **publicada** para recibir webhooks de producción
- Mientras esté sin publicar, solo recibirás webhooks de prueba
- Los administradores, desarrolladores y evaluadores pueden probar incluso sin publicar

## Próximos Pasos en el Frontend

Una vez configuradas las suscripciones:

1. Ve al editor de flujos en Plubot
2. Haz clic en el botón de compartir/publicar
3. Selecciona la pestaña "WhatsApp Business"
4. Haz clic en "Conectar con Facebook"
5. Autoriza los permisos necesarios
6. Tu flujo quedará conectado a WhatsApp Business

## Troubleshooting

Si no recibes webhooks:
- Verifica que el webhook esté verificado (debe mostrar un check verde)
- Revisa los logs en Render: https://dashboard.render.com
- Asegúrate de que las variables de entorno estén configuradas correctamente
