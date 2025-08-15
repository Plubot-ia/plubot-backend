import logging
import secrets


def generate_key(length: int = 32) -> str:
    """Genera una clave secreta segura en formato hexadecimal."""
    return secrets.token_hex(length)


if __name__ == "__main__":
    # Configurar logging para mostrar solo el mensaje (la clave)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    key = generate_key()
    logger.info(key)

