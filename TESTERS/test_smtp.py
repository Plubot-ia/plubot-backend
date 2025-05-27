import smtplib
from email.message import EmailMessage

# Configuración
mail_server = "smtp.zoho.com"
mail_port = 587
mail_username = "info@plubot.com"
mail_password = "k3LwDw07mqgy"  # Reemplaza con la contraseña correcta

# Crear mensaje de prueba
msg = EmailMessage()
msg.set_content("Este es un correo de prueba desde Plubot.")
msg["Subject"] = "Correo de Prueba"
msg["From"] = mail_username
msg["To"] = "test@example.com"  # Un correo de prueba

# Conectar y enviar
try:
    with smtplib.SMTP(mail_server, mail_port) as server:
        server.starttls()
        server.login(mail_username, mail_password)
        server.send_message(msg)
        print("Correo enviado exitosamente")
except Exception as e:
    print("Error al enviar correo:", str(e))