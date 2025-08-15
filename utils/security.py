# plubot-backend/utils/security.py
import logging
import os
from typing import Final

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

logger: Final = logging.getLogger(__name__)

# --- Constantes de Error ---
_KEY_NOT_FOUND_ERROR: Final = "ENCRYPTION_KEY no configurada."
_ENCRYPT_ERROR: Final = "No se pudo cifrar el token."
_DECRYPT_ERROR: Final = "No se pudo descifrar el token."
_INVALID_TOKEN_ERROR: Final = "Token inválido."
_INVALID_TOKEN_LOG: Final = (
    "Token de descifrado inválido. Puede que la clave haya cambiado."
)


def _get_cipher_suite() -> Fernet:
    """Retorna una instancia de Fernet, cacheada para eficiencia."""
    # Usamos un atributo de función como caché para evitar el estado global.
    if not hasattr(_get_cipher_suite, "cache"):
        key: str | None = None
        try:
            if current_app:
                key = current_app.config.get("ENCRYPTION_KEY")
        except RuntimeError:
            logger.info("No se está en un contexto de aplicación Flask.")

        if not key:
            key = os.environ.get("ENCRYPTION_KEY")

        if not key:
            logger.error(
                "ENCRYPTION_KEY no encontrada en config ni en variables de entorno."
            )
            raise ValueError(_KEY_NOT_FOUND_ERROR)

        _get_cipher_suite.cache = Fernet(key.encode())

    return _get_cipher_suite.cache


def encrypt_token(token: str) -> str:
    """Cifra un token usando la clave de la aplicación."""
    if not token:
        return ""
    try:
        cipher = _get_cipher_suite()
        encrypted_token_bytes = cipher.encrypt(token.encode())
        return encrypted_token_bytes.decode()
    except Exception as e:
        logger.exception("Error inesperado al cifrar el token.")
        raise RuntimeError(_ENCRYPT_ERROR) from e


def decrypt_token(encrypted_token_str: str) -> str:
    """Descifra un token usando la clave de la aplicación."""
    if not encrypted_token_str:
        return ""
    try:
        cipher = _get_cipher_suite()
        decrypted_token_bytes = cipher.decrypt(encrypted_token_str.encode())
        return decrypted_token_bytes.decode()
    except InvalidToken as e:
        logger.exception(_INVALID_TOKEN_LOG)
        raise ValueError(_INVALID_TOKEN_ERROR) from e
    except Exception as e:
        logger.exception("Error inesperado al descifrar el token.")
        raise RuntimeError(_DECRYPT_ERROR) from e


def generate_fernet_key() -> str:
    """Genera una nueva clave Fernet segura."""
    return Fernet.generate_key().decode()


if __name__ == "__main__":
    # --- Bloque de prueba ---
    # Configuración básica de logging para la salida del script. El logger del módulo
    # (`__main__` en este caso) propagará los mensajes al root logger configurado aquí.
    logging.basicConfig(
        level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler()]
    )

    # 1. Generar una clave: python -m utils.security
    # 2. Exportar la clave: export ENCRYPTION_KEY='la_clave_generada'
    # 3. Ejecutar de nuevo para probar: python -m utils.security

    if "ENCRYPTION_KEY" not in os.environ:
        logger.info("Generando nueva clave Fernet...")
        logger.info(generate_fernet_key())
        logger.info(
            "\nPara probar, exporta esta clave a la variable de entorno ENCRYPTION_KEY."
        )
    else:
        logger.info("Probando cifrado y descifrado con la clave existente...")
        # El siguiente token es solo para fines de prueba y demostración.
        sample_token = "my_super_secret_discord_bot_token"  # noqa: S105
        logger.info("Token original: %s", sample_token)

        encrypted = encrypt_token(sample_token)
        logger.info("Token cifrado: %s", encrypted)

        decrypted = decrypt_token(encrypted)
        logger.info("Token descifrado: %s", decrypted)

        assert sample_token == decrypted
        logger.info("\n✅ Prueba de cifrado/descifrado exitosa.")
