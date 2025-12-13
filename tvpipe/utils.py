import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from time import sleep
from types import TracebackType
from typing import Optional, Type, Union

import filetype
import requests

from tvpipe.exceptions import DownloadError, TelegramConnectionError

logger = logging.getLogger(__name__)


def normalize_windows_name(name: str) -> str:
    invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
    name = re.sub(invalid_chars, "_", name)
    name = name.rstrip(" .")
    if len(name) < 0:
        raise ValueError("Invalid name")
    return name


def sleep_progress(seconds: float):
    total = int(seconds)
    if total <= 0:
        return

    logger.info(
        f"Esperando {total // 60} minutos y {total % 60} segundos antes de continuar..."
    )

    for i in range(total, 0, -1):
        sleep(1)
        if i % 60 == 0:
            mins_left = i // 60
            logger.info(f"Faltan {mins_left} minutos...")
        elif i <= 10:  # Mostrar segundos finales
            logger.info(f"{i} segundos restantes...")


def create_md5sum_by_hashlib(path: Union[str, Path]) -> str:
    path = Path(path) if isinstance(path, str) else path
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(50 * 1024 * 1024), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_mimetype(path: Path):
    path = Path(path) if isinstance(path, str) else path
    logger.debug(f"Obteniendo el mimetype para {path=}")
    for _ in range(3):
        kind = filetype.guess(str(path))
        logger.debug(f"El mimetype para {path=} es {kind=}")
        if kind is None:
            sleep(1)
            continue
        return kind.mime


def download_thumbnail(url: Optional[str], output_path: Path) -> Path:
    if not url:
        logger.warning("No hay URL de miniatura disponible.")
        return output_path

    if output_path.exists():
        return output_path

    try:
        logger.info("Descargando miniatura...")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
    except Exception as e:
        logger.error(f"Error descargando miniatura: {e}")

    return output_path


class ReliabilityGuard:
    """
    Gestor de contexto que maneja errores, reintentos y backoff exponencial.
    """

    def __init__(self):
        self.consecutive_errors = 0

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        # Si exc_type es None, significa que NO hubo error
        if exc_type is None:
            if self.consecutive_errors > 0:
                logger.info("El sistema se ha recuperado tras errores previos.")
            self.consecutive_errors = 0
            return False

        # Si hubo error, incrementamos contador
        self.consecutive_errors += 1

        if issubclass(exc_type, TelegramConnectionError):
            wait_time = min(300 * self.consecutive_errors, 3600)
            logger.error(
                f"Error conexión Telegram (Intento {self.consecutive_errors})."
            )
        elif issubclass(exc_type, DownloadError):
            wait_time = min(60 * self.consecutive_errors, 1800)
            logger.error(f"Error descarga (Intento {self.consecutive_errors}).")
        else:
            wait_time = min(60 * self.consecutive_errors, 1800)
            logger.error(
                f"Error crítico/inesperado (Intento {self.consecutive_errors})."
            )

        logger.error(f"Detalle: {exc_val}", exc_info=True)
        logger.info(f"Pausando el sistema por {wait_time} segundos...")
        sleep_progress(wait_time)

        # Retornar True indica a Python que el error fue "manejado"
        # y NO debe romper el programa. El bucle while continuará.
        return True


def should_skip_weekends() -> bool:
    """Helper para lógica de fines de semana."""
    return datetime.now().weekday() >= 5


def wait_end_of_day():
    """Duerme hasta las 23:59:59."""
    now = datetime.now()
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)
    diff = (end_of_day - now).total_seconds()
    if diff > 0:
        logger.info("Esperando hasta el fin del día...")
        sleep_progress(diff)
