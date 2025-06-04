# plubot-backend/utils/security.py
import os
from cryptography.fernet import Fernet
from flask import current_app
import logging

logger = logging.getLogger(__name__)

_cipher_suite = None

def _get_cipher_suite():
    """Retorna una instancia de Fernet inicializada con la clave de la app."""
    global _cipher_suite
    if _cipher_suite is None:
        try:
            # Intentar obtener la clave desde la configuración de la app Flask
            # Esto asume que la clave está cargada en app.config['ENCRYPTION_KEY']
            key = current_app.config.get('ENCRYPTION_KEY')
            if not key:
                # Fallback a variable de entorno si no está en app.config (ej. para scripts fuera de contexto de app)
                key = os.environ.get('ENCRYPTION_KEY')
            
            if not key:
                logger.error("ENCRYPTION_KEY no encontrada en la configuración de la app ni en las variables de entorno.")
                raise ValueError("ENCRYPTION_KEY no configurada.")
            
            _cipher_suite = Fernet(key.encode()) # La clave debe estar en bytes
        except RuntimeError: # Fuera del contexto de la aplicación
            key = os.environ.get('ENCRYPTION_KEY')
            if not key:
                logger.error("ENCRYPTION_KEY no encontrada en las variables de entorno (fuera de contexto de app).")
                raise ValueError("ENCRYPTION_KEY no configurada (fuera de contexto de app).")
            _cipher_suite = Fernet(key.encode())
    return _cipher_suite

def encrypt_token(token: str) -> str:
    """Cifra un token."""
    if not token:
        return ""
    try:
        cipher = _get_cipher_suite()
        encrypted_token_bytes = cipher.encrypt(token.encode())
        return encrypted_token_bytes.decode() # Guardar como string
    except Exception as e:
        logger.error(f"Error al cifrar el token: {e}")
        raise

def decrypt_token(encrypted_token_str: str) -> str:
    """Descifra un token."""
    if not encrypted_token_str:
        return ""
    try:
        cipher = _get_cipher_suite()
        decrypted_token_bytes = cipher.decrypt(encrypted_token_str.encode())
        return decrypted_token_bytes.decode()
    except Exception as e:
        logger.error(f"Error al descifrar el token: {e}")
        # Podría ser InvalidToken si el token es incorrecto o la clave ha cambiado
        raise

def generate_fernet_key() -> str:
    """Genera una nueva clave Fernet."""
    return Fernet.generate_key().decode()

# Para pruebas rápidas si se ejecuta este archivo directamente:
if __name__ == '__main__':
    # Esto requiere que ENCRYPTION_KEY esté seteada en el entorno para funcionar
    # o se puede mockear current_app.config si se usa un framework de testing
    print(f"Nueva clave Fernet generada: {generate_fernet_key()}")
    
    # Ejemplo de uso (requiere ENCRYPTION_KEY en el entorno)
    # Asegúrate de setear ENCRYPTION_KEY='tu_clave_generada_aqui' en tu terminal antes de correr
    # export ENCRYPTION_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
    # python utils/security.py
    if os.environ.get('ENCRYPTION_KEY'):
        sample_token = "my_super_secret_discord_bot_token"
        print(f"Token original: {sample_token}")
        encrypted = encrypt_token(sample_token)
        print(f"Token cifrado: {encrypted}")
        decrypted = decrypt_token(encrypted)
        print(f"Token descifrado: {decrypted}")
        assert sample_token == decrypted
        print("Prueba de cifrado/descifrado exitosa.")
    else:
        print("Para probar cifrado/descifrado, setea la variable de entorno ENCRYPTION_KEY.")
