# Configuración de WhatsApp Business API

## ✅ Estado Actual
- **Webhook URL:** `https://plubot-backend.onrender.com/api/wa/webhook`
- **Token de Verificación:** `plubot_verify_2024`
- **Estado:** ✅ Funcionando correctamente

## Configuración en Facebook Developer Console

### 1. Configurar Webhook
1. Ve a tu app en [Facebook Developers](https://developers.facebook.com)
2. En el panel izquierdo, selecciona **WhatsApp > Configuration**
3. En la sección **Webhook**, haz clic en **Edit**
4. Ingresa:
   - **Callback URL:** `https://plubot-backend.onrender.com/api/wa/webhook`
   - **Verify Token:** `plubot_verify_2024`
5. Suscríbete a los siguientes campos:
   - `messages`
   - `messaging_postbacks`
   - `messaging_optins`
   - `message_status`

### 2. Configurar OAuth Redirect URI
1. En **Facebook Login > Settings**
2. Agrega la URL de callback: `https://plubot.com/whatsapp-callback.html`
3. Guarda los cambios

### 3. Variables de Entorno Requeridas en Render
```env
FACEBOOK_APP_ID=tu_app_id
FACEBOOK_APP_SECRET=tu_app_secret
WHATSAPP_WEBHOOK_VERIFY_TOKEN=plubot_verify_2024
WHATSAPP_REDIRECT_URI=https://plubot.com/whatsapp-callback.html
```

## Endpoints Disponibles

### Públicos
- `GET /api/wa/webhook` - Verificación del webhook (usado por Facebook)
- `POST /api/wa/webhook` - Recepción de eventos de WhatsApp

### Protegidos (requieren JWT)
- `GET /api/wa/status/<plubot_id>` - Verificar estado de conexión
- `POST /api/wa/connect` - Iniciar proceso OAuth
- `POST /api/wa/callback` - Procesar callback OAuth
- `POST /api/wa/disconnect/<plubot_id>` - Desconectar WhatsApp
- `POST /api/wa/send` - Enviar mensaje

## Flujo de Integración

1. **Conectar WhatsApp a un Plubot:**
   ```javascript
   // Frontend llama a /api/wa/connect con JWT válido
   const response = await fetch('/api/wa/connect', {
     method: 'POST',
     headers: {
       'Authorization': `Bearer ${token}`,
       'Content-Type': 'application/json'
     },
     body: JSON.stringify({ plubot_id: 123 })
   });
   const { oauth_url } = await response.json();
   // Redirigir al usuario a oauth_url
   ```

2. **Procesar Callback OAuth:**
   ```javascript
   // Después de autorización, Facebook redirige con código
   const response = await fetch('/api/wa/callback', {
     method: 'POST',
     headers: {
       'Authorization': `Bearer ${token}`,
       'Content-Type': 'application/json'
     },
     body: JSON.stringify({ 
       code: 'codigo_de_facebook',
       plubot_id: 123 
     })
   });
   ```

3. **Enviar Mensaje:**
   ```javascript
   const response = await fetch('/api/wa/send', {
     method: 'POST',
     headers: {
       'Authorization': `Bearer ${token}`,
       'Content-Type': 'application/json'
     },
     body: JSON.stringify({
       plubot_id: 123,
       to: '+1234567890',
       message: 'Hola desde Plubot!'
     })
   });
   ```

## Pruebas con cURL

### Verificar Webhook (público)
```bash
curl -X GET "https://plubot-backend.onrender.com/api/wa/webhook?hub.mode=subscribe&hub.verify_token=plubot_verify_2024&hub.challenge=test123"
```

### Simular Evento de Webhook
```bash
curl -X POST "https://plubot-backend.onrender.com/api/wa/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "1234567890",
            "id": "msg_123",
            "type": "text",
            "text": {"body": "Mensaje de prueba"}
          }]
        }
      }]
    }]
  }'
```

## Troubleshooting

### Error: "No autorizado"
- Verifica que estés enviando un JWT válido en el header Authorization
- El token debe tener el formato: `Bearer <token>`

### Error: "API route not found"
- Asegúrate de que Render haya completado el despliegue
- Verifica la URL exacta del endpoint

### Webhook no valida en Facebook
- Confirma que el token de verificación sea exactamente: `plubot_verify_2024`
- Verifica que la URL sea: `https://plubot-backend.onrender.com/api/wa/webhook`
- Revisa los logs en Render para ver errores

## Notas Importantes

- El servicio FlowService está temporalmente deshabilitado
- Los tokens de acceso de WhatsApp se almacenan encriptados en la base de datos
- Cada Plubot puede tener solo una cuenta de WhatsApp conectada
- Los mensajes y eventos se registran en las tablas `whatsapp_messages` y `whatsapp_webhook_events`
