import logging
from time import sleep

logger = logging.getLogger(__name__)


def sleep_progress(seconds):
    if seconds <= 0:
        return
    minutes = int(seconds) // 60
    logger.info(f"Esperando {minutes} minutos antes de continuar...")
    for i in range(int(seconds), 0, -1):
        sleep(1)
        if i % 60 == 0:
            minutes -= 1
            logger.info(f"Esperando {minutes} minutos antes de continuar...")
