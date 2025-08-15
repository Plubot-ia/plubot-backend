import logging
from logging.handlers import RotatingFileHandler


def setup_logging() -> logging.Logger:
    """Configura el sistema de logging para la aplicación."""
    # Crear formateador para incluir el nombre del logger
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Configurar handler para archivo con rotación
    file_handler = RotatingFileHandler(
        "plubot.log",
        maxBytes=1_000_000,  # 1 MB por archivo
        backupCount=5,  # Mantener hasta 5 archivos de respaldo
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # Configurar handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Obtener el logger raíz y limpiar handlers existentes para evitar duplicados
    logger = logging.getLogger()
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("Sistema de logging configurado correctamente")
    return logger
